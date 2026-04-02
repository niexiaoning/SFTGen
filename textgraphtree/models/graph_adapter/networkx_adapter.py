"""
NetworkX Graph Adapter for TGT.

Implements the BaseGraphAdapter interface using the existing NetworkXStorage
backend. Retrieves subgraphs via BFS expansion from intent-linked seed nodes,
and serializes using HierarchySerializer.
"""

import logging
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from textgraphtree.bases.base_graph_adapter import BaseGraphAdapter
from textgraphtree.models.graph_adapter.intent_graph_linker import IntentGraphLinker

logger = logging.getLogger(__name__)


class NetworkXGraphAdapter(BaseGraphAdapter):
    """
    Graph adapter backed by NetworkXStorage.

    Uses IntentGraphLinker to find seed nodes, then BFS-expands to build
    a context-rich subgraph for QA generation prompts.
    """

    def __init__(
        self,
        graph_storage,
        linker: Optional[IntentGraphLinker] = None,
        hierarchy_serializer=None,
    ):
        """
        :param graph_storage: BaseGraphStorage (typically NetworkXStorage)
        :param linker: IntentGraphLinker instance (created if None)
        :param hierarchy_serializer: Optional HierarchySerializer for formatting
        """
        self.graph_storage = graph_storage
        self.linker = linker or IntentGraphLinker()
        self._hierarchy_serializer = hierarchy_serializer

    async def retrieve_subgraph(
        self,
        intent_node: Dict[str, Any],
        max_hops: int = 2,
        max_nodes: int = 20,
    ) -> Tuple[List[Tuple[str, dict]], List[Tuple[Any, Any, dict]]]:
        """
        Retrieve subgraph relevant to intent via seed + BFS expansion.
        """
        # Step 1: Find seed nodes via linker
        seed_results = await self.linker.link(
            intent_node, self.graph_storage, max_seeds=5,
        )

        if not seed_results:
            logger.warning(
                "No seed nodes found for intent '%s', falling back to random nodes",
                intent_node.get("name", "unknown"),
            )
            return await self._fallback_random_subgraph(max_nodes)

        seed_ids = [r["node_id"] for r in seed_results]

        # Step 2: BFS expand from seeds
        nodes, edges = await self._bfs_expand(seed_ids, max_hops, max_nodes)

        logger.debug(
            "Retrieved subgraph for intent '%s': %d nodes, %d edges (seeds: %s)",
            intent_node.get("name", "unknown"),
            len(nodes), len(edges),
            seed_ids[:3],
        )
        return nodes, edges

    async def serialize_subgraph(
        self,
        nodes: List[Tuple[str, dict]],
        edges: List[Tuple[Any, Any, dict]],
        format: str = "natural_language",
    ) -> str:
        """
        Serialize subgraph to text.

        Formats:
        - "natural_language": Bullet-point text
        - "markdown": Uses HierarchySerializer if available
        - "json": Structured JSON representation
        """
        if format == "markdown" and self._hierarchy_serializer:
            return self._serialize_with_hierarchy(nodes, edges)
        elif format == "json":
            return self._serialize_json(nodes, edges)
        else:
            return self._serialize_natural_language(nodes, edges)

    # ─── Internal Methods ───────────────────────────────────────────

    async def _bfs_expand(
        self,
        seed_ids: List[str],
        max_hops: int,
        max_nodes: int,
    ) -> Tuple[List[Tuple[str, dict]], List[Tuple[Any, Any, dict]]]:
        """BFS expand from seed nodes up to max_hops and max_nodes."""
        visited_nodes: Dict[str, dict] = {}
        collected_edges: List[Tuple[str, str, dict]] = []
        edge_set: set = set()

        queue: deque = deque()

        # Initialize with seeds
        for sid in seed_ids:
            if len(visited_nodes) >= max_nodes:
                break
            node_data = await self.graph_storage.get_node(sid)
            if node_data is not None:
                visited_nodes[sid] = node_data
                queue.append((sid, 0))

        # BFS
        while queue and len(visited_nodes) < max_nodes:
            current_id, depth = queue.popleft()

            if depth >= max_hops:
                continue

            # Get edges from current node
            node_edges = await self.graph_storage.get_node_edges(current_id)
            if not node_edges:
                continue

            for source_id, target_id in node_edges:
                # Add edge
                edge_key = (source_id, target_id)
                if edge_key not in edge_set:
                    edge_data = await self.graph_storage.get_edge(
                        source_id, target_id,
                    )
                    if edge_data is not None:
                        collected_edges.append((source_id, target_id, edge_data))
                        edge_set.add(edge_key)

                # Add neighbor to queue if not visited
                neighbor_id = (
                    target_id if source_id == current_id else source_id
                )
                if neighbor_id not in visited_nodes:
                    if len(visited_nodes) >= max_nodes:
                        break
                    neighbor_data = await self.graph_storage.get_node(neighbor_id)
                    if neighbor_data is not None:
                        visited_nodes[neighbor_id] = neighbor_data
                        queue.append((neighbor_id, depth + 1))

        nodes = [(nid, ndata) for nid, ndata in visited_nodes.items()]
        return nodes, collected_edges

    async def _fallback_random_subgraph(
        self,
        max_nodes: int,
    ) -> Tuple[List[Tuple[str, dict]], List[Tuple[Any, Any, dict]]]:
        """Fallback: return a random subset of the graph."""
        all_nodes = await self.graph_storage.get_all_nodes()
        all_edges = await self.graph_storage.get_all_edges()

        nodes = (all_nodes or [])[:max_nodes]
        node_ids = {n[0] for n in nodes}

        edges = []
        for edge in (all_edges or []):
            src, tgt = edge[0], edge[1]
            if src in node_ids and tgt in node_ids:
                edges.append(edge)

        return nodes, edges

    def _serialize_natural_language(
        self,
        nodes: List[Tuple[str, dict]],
        edges: List[Tuple[Any, Any, dict]],
    ) -> str:
        """Serialize as natural language bullet points."""
        lines = []

        if nodes:
            lines.append("### Entities")
            for node_id, node_data in nodes:
                desc = node_data.get("description", "")
                entity_type = node_data.get("entity_type", "")
                parts = [f"- **{node_id}**"]
                if entity_type:
                    parts.append(f"({entity_type})")
                if desc:
                    parts.append(f": {desc}")
                lines.append(" ".join(parts))

        if edges:
            lines.append("\n### Relationships")
            for edge in edges:
                src, tgt = edge[0], edge[1]
                edge_data = edge[2] if len(edge) > 2 else {}
                desc = edge_data.get("description", "")
                rel_type = edge_data.get("relation_type", "related_to")
                line = f"- {src} —[{rel_type}]→ {tgt}"
                if desc:
                    line += f": {desc}"
                lines.append(line)

        return "\n".join(lines)

    def _serialize_json(
        self,
        nodes: List[Tuple[str, dict]],
        edges: List[Tuple[Any, Any, dict]],
    ) -> str:
        """Serialize as JSON string."""
        import json
        data = {
            "entities": [
                {"id": nid, **ndata} for nid, ndata in nodes
            ],
            "relationships": [
                {
                    "source": e[0],
                    "target": e[1],
                    **(e[2] if len(e) > 2 else {}),
                }
                for e in edges
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _serialize_with_hierarchy(
        self,
        nodes: List[Tuple[str, dict]],
        edges: List[Tuple[Any, Any, dict]],
    ) -> str:
        """Serialize using HierarchySerializer (markdown format)."""
        try:
            return self._hierarchy_serializer.serialize(
                nodes, edges, format="markdown",
            )
        except Exception as e:
            logger.warning("HierarchySerializer failed: %s, falling back", e)
            return self._serialize_natural_language(nodes, edges)
