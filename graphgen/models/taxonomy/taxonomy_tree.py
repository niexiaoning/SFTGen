"""
Pluggable Task Taxonomy Tree for DA-ToG.

Loads, validates, and provides access to hierarchical task intent trees
that can be instantiated for any domain.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)

# Domain-agnostic cognitive dimensions
COGNITIVE_DIMENSIONS = [
    "concept_explanation",      # 概念解释
    "relational_reasoning",     # 关系推理
    "rule_compliance",          # 规则遵循
    "anomaly_diagnosis",        # 异常诊断
    "comparative_analysis",     # 对比分析
    "procedural_knowledge",     # 程序性知识
]


@dataclass
class TaxonomyNode:
    """A single node in the taxonomy tree."""
    id: str
    name: str
    description: str = ""
    cognitive_dimension: Optional[str] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List["TaxonomyNode"] = field(default_factory=list)
    depth: int = 0

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }
        if self.cognitive_dimension:
            d["cognitive_dimension"] = self.cognitive_dimension
        if self.parent_id:
            d["parent_id"] = self.parent_id
        if self.metadata:
            d["metadata"] = self.metadata
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


class TaxonomyTree:
    """
    Pluggable task taxonomy tree.

    Supports loading from JSON or YAML, both flat (parent_id) and nested
    (children) formats. Provides traversal, sampling, and validation.
    """

    def __init__(
        self,
        name: str = "",
        description: str = "",
        domain: str = "",
        version: str = "1.0",
    ):
        self.name = name
        self.description = description
        self.domain = domain
        self.version = version
        self._nodes: Dict[str, TaxonomyNode] = {}
        self._roots: List[str] = []

    # ─── Loading ────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str) -> "TaxonomyTree":
        """
        Load a taxonomy tree from a JSON or YAML file.

        Supports both flat format (nodes with parent_id) and nested format
        (nodes with children arrays).

        :param path: Path to JSON or YAML file
        :return: TaxonomyTree instance
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Taxonomy file not found: {path}")

        ext = os.path.splitext(path)[1].lower()
        with open(path, "r", encoding="utf-8") as f:
            if ext in (".yaml", ".yml"):
                data = yaml.safe_load(f)
            elif ext == ".json":
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {ext}. Use .json or .yaml")

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "TaxonomyTree":
        """Build a TaxonomyTree from a dictionary."""
        tree = cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            domain=data.get("domain", ""),
            version=data.get("version", "1.0"),
        )

        raw_nodes = data.get("nodes", [])
        if not raw_nodes:
            raise ValueError("Taxonomy must contain at least one node under 'nodes'")

        # Detect format: nested (children) vs flat (parent_id)
        first_node = raw_nodes[0]
        if "children" in first_node and isinstance(first_node.get("children"), list):
            tree._load_nested(raw_nodes, parent_id=None, depth=0)
        else:
            tree._load_flat(raw_nodes)

        tree._compute_roots()
        return tree

    def _load_nested(
        self,
        nodes: List[dict],
        parent_id: Optional[str],
        depth: int,
    ) -> None:
        """Load nodes from nested format (children arrays)."""
        for nd in nodes:
            node = TaxonomyNode(
                id=nd["id"],
                name=nd["name"],
                description=nd.get("description", ""),
                cognitive_dimension=nd.get("cognitive_dimension"),
                parent_id=parent_id,
                metadata=nd.get("metadata", {}),
                depth=depth,
            )
            self._nodes[node.id] = node

            children_data = nd.get("children", [])
            if children_data:
                self._load_nested(children_data, parent_id=node.id, depth=depth + 1)

        # Wire up children references after all nodes are loaded
        # (Called once at the end by from_dict -> _compute_roots)

    def _load_flat(self, nodes: List[dict]) -> None:
        """Load nodes from flat format (parent_id references)."""
        for nd in nodes:
            node = TaxonomyNode(
                id=nd["id"],
                name=nd["name"],
                description=nd.get("description", ""),
                cognitive_dimension=nd.get("cognitive_dimension"),
                parent_id=nd.get("parent_id"),
                metadata=nd.get("metadata", {}),
            )
            self._nodes[node.id] = node

        # Compute depths
        self._compute_depths()

    def _compute_depths(self) -> None:
        """Compute depth for each node in flat-format trees."""
        for node in self._nodes.values():
            depth = 0
            current = node
            visited = set()
            while current.parent_id and current.parent_id in self._nodes:
                if current.id in visited:
                    logger.warning("Cycle detected at node %s, breaking", current.id)
                    break
                visited.add(current.id)
                current = self._nodes[current.parent_id]
                depth += 1
            node.depth = depth

    def _compute_roots(self) -> None:
        """Identify root nodes and build children references."""
        # Clear existing children
        for node in self._nodes.values():
            node.children = []

        # Wire up children
        for node in self._nodes.values():
            if node.parent_id and node.parent_id in self._nodes:
                self._nodes[node.parent_id].children.append(node)

        # Find roots
        self._roots = [
            nid for nid, node in self._nodes.items()
            if node.parent_id is None or node.parent_id not in self._nodes
        ]

    # ─── Validation ─────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """
        Validate tree integrity.

        :return: List of warning/error messages. Empty list = valid.
        """
        issues = []

        if not self._nodes:
            issues.append("ERROR: Tree has no nodes")
            return issues

        if not self._roots:
            issues.append("ERROR: No root nodes found")

        # Check for orphan parent_id references
        for node in self._nodes.values():
            if node.parent_id and node.parent_id not in self._nodes:
                issues.append(
                    f"WARNING: Node '{node.id}' references non-existent parent '{node.parent_id}'"
                )

        # Check for duplicate IDs (should not happen since we use a dict)
        # Check cognitive dimensions
        for node in self._nodes.values():
            if node.cognitive_dimension and node.cognitive_dimension not in COGNITIVE_DIMENSIONS:
                issues.append(
                    f"WARNING: Node '{node.id}' has unknown cognitive_dimension "
                    f"'{node.cognitive_dimension}'. Valid: {COGNITIVE_DIMENSIONS}"
                )

        # Check depth reasonableness
        max_depth = self.max_depth
        if max_depth > 10:
            issues.append(
                f"WARNING: Tree depth is {max_depth}, which may be too deep"
            )

        # Check for isolated subtrees
        reachable = set()
        for root_id in self._roots:
            self._collect_reachable(root_id, reachable)
        unreachable = set(self._nodes.keys()) - reachable
        if unreachable:
            issues.append(
                f"WARNING: {len(unreachable)} nodes unreachable from roots: "
                f"{list(unreachable)[:5]}..."
            )

        if issues:
            for issue in issues:
                logger.warning("Taxonomy validation: %s", issue)
        else:
            logger.info("Taxonomy validation passed: %d nodes, depth %d",
                        len(self._nodes), max_depth)

        return issues

    def _collect_reachable(self, node_id: str, reachable: set) -> None:
        if node_id in reachable:
            return
        reachable.add(node_id)
        node = self._nodes.get(node_id)
        if node:
            for child in node.children:
                self._collect_reachable(child.id, reachable)

    # ─── Accessors ──────────────────────────────────────────────────

    @property
    def size(self) -> int:
        """Total number of nodes."""
        return len(self._nodes)

    @property
    def max_depth(self) -> int:
        """Maximum depth of the tree."""
        if not self._nodes:
            return 0
        return max(n.depth for n in self._nodes.values())

    @property
    def roots(self) -> List[TaxonomyNode]:
        """Root nodes."""
        return [self._nodes[rid] for rid in self._roots if rid in self._nodes]

    @property
    def leaves(self) -> List[TaxonomyNode]:
        """Leaf nodes (no children)."""
        return [n for n in self._nodes.values() if n.is_leaf]

    def get_node(self, node_id: str) -> Optional[TaxonomyNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> List[TaxonomyNode]:
        """Get all nodes."""
        return list(self._nodes.values())

    def get_nodes_by_dimension(self, dimension: str) -> List[TaxonomyNode]:
        """Get all nodes with a specific cognitive dimension."""
        return [
            n for n in self._nodes.values()
            if n.cognitive_dimension == dimension
        ]

    def get_nodes_at_depth(self, depth: int) -> List[TaxonomyNode]:
        """Get all nodes at a specific depth level."""
        return [n for n in self._nodes.values() if n.depth == depth]

    def get_branch(self, node_id: str) -> List[TaxonomyNode]:
        """Get the path from root to the given node."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        path = [node]
        current = node
        visited = set()
        while current.parent_id and current.parent_id in self._nodes:
            if current.id in visited:
                break
            visited.add(current.id)
            current = self._nodes[current.parent_id]
            path.append(current)
        path.reverse()
        return path

    def get_subtree(self, node_id: str) -> List[TaxonomyNode]:
        """Get all descendants of a node (including the node itself)."""
        result = []
        self._collect_subtree(node_id, result)
        return result

    def _collect_subtree(self, node_id: str, result: list) -> None:
        node = self._nodes.get(node_id)
        if not node:
            return
        result.append(node)
        for child in node.children:
            self._collect_subtree(child.id, result)

    def get_siblings(self, node_id: str) -> List[TaxonomyNode]:
        """Get sibling nodes (same parent)."""
        node = self._nodes.get(node_id)
        if not node or not node.parent_id:
            return []
        parent = self._nodes.get(node.parent_id)
        if not parent:
            return []
        return [c for c in parent.children if c.id != node_id]

    # ─── Statistics ─────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics about the tree."""
        dimension_counts = {}
        for dim in COGNITIVE_DIMENSIONS:
            count = len(self.get_nodes_by_dimension(dim))
            if count > 0:
                dimension_counts[dim] = count

        depth_counts = {}
        for node in self._nodes.values():
            depth_counts[node.depth] = depth_counts.get(node.depth, 0) + 1

        return {
            "name": self.name,
            "domain": self.domain,
            "total_nodes": self.size,
            "root_count": len(self._roots),
            "leaf_count": len(self.leaves),
            "max_depth": self.max_depth,
            "dimension_distribution": dimension_counts,
            "depth_distribution": depth_counts,
        }

    # ─── Serialization ──────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to dictionary (nested format)."""
        def _build_nested(node: TaxonomyNode) -> dict:
            d = node.to_dict()
            d["children"] = [_build_nested(c) for c in node.children]
            if not d["children"]:
                del d["children"]
            return d

        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "version": self.version,
            "nodes": [_build_nested(self._nodes[rid]) for rid in self._roots],
        }

    def save(self, path: str) -> None:
        """Save taxonomy tree to JSON or YAML file."""
        data = self.to_dict()
        ext = os.path.splitext(path)[1].lower()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            if ext in (".yaml", ".yml"):
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Taxonomy saved to %s (%d nodes)", path, self.size)

    def _get_all_dimensions(self) -> List[str]:
        """Get all cognitive dimensions present in the tree."""
        dimensions = set()
        for node in self._nodes.values():
            if node.cognitive_dimension:
                dimensions.add(node.cognitive_dimension)
        return list(dimensions)

    def __repr__(self) -> str:
        return (
            f"TaxonomyTree(name='{self.name}', domain='{self.domain}', "
            f"nodes={self.size}, depth={self.max_depth})"
        )
