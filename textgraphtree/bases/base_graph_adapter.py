"""
Abstract Graph Adapter for TGT.

Provides a domain-agnostic interface for retrieving and serializing
subgraphs based on intent nodes from the taxonomy tree.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class BaseGraphAdapter(ABC):
    """
    Abstract adapter between the taxonomy intent layer and the KG storage layer.

    Implementations translate a semantic intent (from TaxonomyNode) into
    a concrete subgraph query against a specific graph backend.
    """

    @abstractmethod
    async def retrieve_subgraph(
        self,
        intent_node: Dict[str, Any],
        max_hops: int = 2,
        max_nodes: int = 20,
    ) -> Tuple[List[Tuple[str, dict]], List[Tuple[Any, Any, dict]]]:
        """
        Retrieve a relevant subgraph for the given intent.

        :param intent_node: Dict with at least 'name', 'description', and
            optionally 'keywords' from a TaxonomyNode
        :param max_hops: Maximum BFS expansion hops from seed nodes
        :param max_nodes: Maximum number of nodes to return
        :return: (nodes, edges) tuple in TextGraphTree batch format:
            nodes = [(node_id, {attr_dict}), ...]
            edges = [(source_id, target_id, {attr_dict}), ...]
        """

    @abstractmethod
    async def serialize_subgraph(
        self,
        nodes: List[Tuple[str, dict]],
        edges: List[Tuple[Any, Any, dict]],
        format: str = "natural_language",
    ) -> str:
        """
        Serialize a subgraph into a text representation for LLM prompts.

        :param nodes: List of (node_id, attributes) tuples
        :param edges: List of (source, target, attributes) tuples
        :param format: Output format: "natural_language", "markdown", "json"
        :return: Textual representation of the subgraph
        """

    async def retrieve_and_serialize(
        self,
        intent_node: Dict[str, Any],
        max_hops: int = 2,
        max_nodes: int = 20,
        format: str = "natural_language",
    ) -> Tuple[str, List[Tuple[str, dict]], List[Tuple[Any, Any, dict]]]:
        """
        Convenience: retrieve subgraph and serialize in one call.

        :return: (serialized_text, nodes, edges)
        """
        nodes, edges = await self.retrieve_subgraph(
            intent_node, max_hops=max_hops, max_nodes=max_nodes,
        )
        text = await self.serialize_subgraph(nodes, edges, format=format)
        return text, nodes, edges
