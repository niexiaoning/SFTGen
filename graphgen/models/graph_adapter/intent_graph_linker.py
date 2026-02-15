"""
Intent-to-Graph Linker for DA-ToG.

Links taxonomy intent nodes to seed entities in the knowledge graph
using keyword matching and optional LLM-based query expansion.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class IntentGraphLinker:
    """
    Links taxonomy intent nodes to graph entities.

    Uses keyword extraction from intent description + node name to find
    matching entities in the knowledge graph via text overlap scoring.
    """

    def __init__(
        self,
        stopwords: Optional[Set[str]] = None,
        min_score: float = 0.1,
    ):
        """
        :param stopwords: Set of words to exclude from keyword matching
        :param min_score: Minimum relevance score to include a node
        """
        self.min_score = min_score
        self.stopwords = stopwords or self._default_stopwords()

    async def link(
        self,
        intent_node: Dict[str, Any],
        graph_storage,
        max_seeds: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find graph entities that match the given intent node.

        :param intent_node: Dict with 'name', 'description', optional 'keywords'
        :param graph_storage: BaseGraphStorage instance
        :param max_seeds: Maximum number of seed entities to return
        :return: List of dicts with 'node_id', 'node_data', 'score'
        """
        # Extract keywords from intent
        keywords = self._extract_keywords(intent_node)
        if not keywords:
            logger.warning(
                "No keywords extracted from intent '%s'",
                intent_node.get("name", "unknown"),
            )
            return []

        # Get all graph nodes
        all_nodes = await graph_storage.get_all_nodes()
        if not all_nodes:
            logger.warning("Graph storage has no nodes")
            return []

        # Score each node against keywords
        scored_nodes = []
        for node_id, node_data in all_nodes:
            score = self._compute_relevance_score(keywords, node_id, node_data)
            if score >= self.min_score:
                scored_nodes.append({
                    "node_id": node_id,
                    "node_data": node_data,
                    "score": score,
                })

        # Sort by score descending
        scored_nodes.sort(key=lambda x: x["score"], reverse=True)

        results = scored_nodes[:max_seeds]
        logger.debug(
            "Intent '%s' linked to %d seed entities (from %d candidates, %d keywords)",
            intent_node.get("name", "unknown"),
            len(results),
            len(all_nodes),
            len(keywords),
        )
        return results

    def _extract_keywords(self, intent_node: Dict[str, Any]) -> List[str]:
        """
        Extract keywords from an intent node.

        Sources (in priority order):
        1. Explicit 'keywords' field
        2. Tokenized name + description
        """
        # Use explicit keywords if provided
        explicit_kw = intent_node.get("keywords", [])
        if explicit_kw:
            return [kw.lower().strip() for kw in explicit_kw if kw.strip()]

        # Extract from name and description
        text_parts = []
        if intent_node.get("name"):
            text_parts.append(intent_node["name"])
        if intent_node.get("description"):
            text_parts.append(intent_node["description"])

        combined = " ".join(text_parts)
        return self._tokenize(combined)

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: split on non-alphanumeric, remove stopwords."""
        # Handle both English and Chinese text
        # For Chinese: each character can be a token
        # For English: split on whitespace/punctuation
        tokens = set()

        # English tokens
        words = re.findall(r"[a-zA-Z]+", text.lower())
        for w in words:
            if len(w) > 1 and w not in self.stopwords:
                tokens.add(w)

        # Chinese character bigrams
        chinese_chars = re.findall(r"[\u4e00-\u9fff]+", text)
        for segment in chinese_chars:
            # Add each character
            for ch in segment:
                tokens.add(ch)
            # Add bigrams
            for i in range(len(segment) - 1):
                tokens.add(segment[i : i + 2])

        return list(tokens)

    def _compute_relevance_score(
        self,
        keywords: List[str],
        node_id: str,
        node_data: Dict[str, Any],
    ) -> float:
        """
        Compute relevance score between keywords and a graph node.

        Score is based on keyword overlap with node_id, node name,
        description, and entity_type.
        """
        if not keywords:
            return 0.0

        # Build searchable text from node
        search_parts = [node_id.lower()]
        for field in ("description", "entity_type", "name", "label"):
            val = node_data.get(field, "")
            if val:
                search_parts.append(str(val).lower())
        search_text = " ".join(search_parts)

        # Count keyword matches
        matches = 0
        for kw in keywords:
            if kw in search_text:
                matches += 1

        return matches / len(keywords) if keywords else 0.0

    @staticmethod
    def _default_stopwords() -> Set[str]:
        """Common stopwords for English + Chinese."""
        return {
            # English
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "not", "no", "if", "then", "else", "than",
            "that", "this", "these", "those", "it", "its", "he", "she",
            "we", "they", "them", "their", "my", "your", "our", "his",
            "her", "all", "each", "every", "any", "some", "most",
            # Chinese common
            "的", "了", "在", "是", "我", "你", "他", "她", "它", "们",
            "这", "那", "和", "与", "或", "也", "都", "就", "而", "及",
            "把", "被", "让", "给", "从", "到", "对", "向", "以", "于",
        }
