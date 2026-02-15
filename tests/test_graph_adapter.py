"""
Tests for DA-ToG Graph Adapter: IntentGraphLinker and NetworkXGraphAdapter.

Tests cover:
- IntentGraphLinker: keyword extraction, scoring, entity linking
- NetworkXGraphAdapter: subgraph retrieval, BFS expansion, serialization
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from graphgen.models.graph_adapter.intent_graph_linker import IntentGraphLinker
from graphgen.models.graph_adapter.networkx_adapter import NetworkXGraphAdapter


# ═══════════════════════════════════════════════════════════════════
# Mock Graph Storage
# ═══════════════════════════════════════════════════════════════════

class MockGraphStorage:
    """Mock graph storage with a small finance-themed knowledge graph."""

    def __init__(self):
        self._nodes = {
            "credit_risk": {
                "description": "Assessment of creditworthiness and default probability",
                "entity_type": "concept",
            },
            "market_risk": {
                "description": "Risk of losses from market price movements",
                "entity_type": "concept",
            },
            "loan_default": {
                "description": "Failure to repay a loan according to terms",
                "entity_type": "event",
            },
            "interest_rate": {
                "description": "The cost of borrowing money",
                "entity_type": "indicator",
            },
            "collateral": {
                "description": "Asset pledged as security for a loan",
                "entity_type": "asset",
            },
            "basel_iii": {
                "description": "International regulatory framework for banks",
                "entity_type": "regulation",
            },
        }
        self._edges = {
            ("credit_risk", "loan_default"): {
                "description": "Credit risk can lead to loan default",
                "relation_type": "causes",
            },
            ("credit_risk", "collateral"): {
                "description": "Collateral mitigates credit risk",
                "relation_type": "mitigated_by",
            },
            ("market_risk", "interest_rate"): {
                "description": "Interest rate changes affect market risk",
                "relation_type": "influenced_by",
            },
            ("basel_iii", "credit_risk"): {
                "description": "Basel III regulates credit risk management",
                "relation_type": "regulates",
            },
        }

    async def get_all_nodes(self):
        return [(nid, ndata) for nid, ndata in self._nodes.items()]

    async def get_all_edges(self):
        return [(src, tgt, edata) for (src, tgt), edata in self._edges.items()]

    async def get_node(self, node_id):
        return self._nodes.get(node_id)

    async def get_node_edges(self, node_id):
        result = []
        for (src, tgt) in self._edges:
            if src == node_id or tgt == node_id:
                result.append((src, tgt))
        return result or None

    async def get_edge(self, source_id, target_id):
        return self._edges.get((source_id, target_id))


# ═══════════════════════════════════════════════════════════════════
# IntentGraphLinker Tests
# ═══════════════════════════════════════════════════════════════════

class TestIntentGraphLinker:
    """Test keyword extraction and entity linking."""

    def test_extract_keywords_from_name_description(self):
        linker = IntentGraphLinker()
        intent = {
            "name": "Credit Risk Assessment",
            "description": "Evaluating loan default probability",
        }
        keywords = linker._extract_keywords(intent)
        assert len(keywords) > 0
        assert "credit" in keywords
        assert "risk" in keywords

    def test_extract_keywords_explicit(self):
        linker = IntentGraphLinker()
        intent = {
            "name": "Something",
            "keywords": ["credit", "risk", "default"],
        }
        keywords = linker._extract_keywords(intent)
        assert keywords == ["credit", "risk", "default"]

    def test_extract_keywords_chinese(self):
        linker = IntentGraphLinker()
        intent = {
            "name": "信用风险评估",
            "description": "评估贷款违约概率",
        }
        keywords = linker._extract_keywords(intent)
        assert len(keywords) > 0
        # Should include Chinese characters/bigrams
        assert "信用" in keywords or "风险" in keywords

    def test_compute_relevance_score(self):
        linker = IntentGraphLinker()
        keywords = ["credit", "risk", "default"]

        # High relevance
        score_high = linker._compute_relevance_score(
            keywords, "credit_risk",
            {"description": "Assessment of credit default risk"},
        )
        # Low relevance
        score_low = linker._compute_relevance_score(
            keywords, "interest_rate",
            {"description": "The cost of borrowing money"},
        )
        assert score_high > score_low

    def test_link_finds_relevant_nodes(self):
        async def _run():
            linker = IntentGraphLinker(min_score=0.1)
            graph = MockGraphStorage()

            intent = {
                "name": "Credit Risk",
                "description": "Credit risk assessment and management",
            }
            results = await linker.link(intent, graph, max_seeds=3)

            assert len(results) > 0
            # credit_risk node should be highest scored
            top_node = results[0]
            assert top_node["node_id"] == "credit_risk"
            assert top_node["score"] > 0

        asyncio.run(_run())

    def test_link_returns_empty_for_unrelated(self):
        async def _run():
            linker = IntentGraphLinker(min_score=0.5)
            graph = MockGraphStorage()

            intent = {
                "name": "Quantum Computing",
                "description": "Qubit entanglement algorithms",
            }
            results = await linker.link(intent, graph, max_seeds=3)
            # No financial nodes should match quantum computing
            assert len(results) == 0

        asyncio.run(_run())

    def test_link_empty_graph(self):
        async def _run():
            linker = IntentGraphLinker()
            empty_graph = AsyncMock()
            empty_graph.get_all_nodes = AsyncMock(return_value=[])

            intent = {"name": "Test", "description": "Test"}
            results = await linker.link(intent, empty_graph)
            assert len(results) == 0

        asyncio.run(_run())

    def test_link_max_seeds_limit(self):
        async def _run():
            linker = IntentGraphLinker(min_score=0.01)
            graph = MockGraphStorage()

            intent = {
                "name": "Risk",
                "description": "Financial risk management overview",
            }
            results = await linker.link(intent, graph, max_seeds=2)
            assert len(results) <= 2

        asyncio.run(_run())


# ═══════════════════════════════════════════════════════════════════
# NetworkXGraphAdapter Tests
# ═══════════════════════════════════════════════════════════════════

class TestNetworkXGraphAdapter:
    """Test subgraph retrieval and serialization."""

    def _make_adapter(self):
        return NetworkXGraphAdapter(graph_storage=MockGraphStorage())

    def test_retrieve_subgraph(self):
        async def _run():
            adapter = self._make_adapter()
            intent = {
                "name": "Credit Risk",
                "description": "Credit risk assessment",
            }
            nodes, edges = await adapter.retrieve_subgraph(
                intent, max_hops=2, max_nodes=10,
            )
            assert len(nodes) > 0
            node_ids = {n[0] for n in nodes}
            assert "credit_risk" in node_ids

        asyncio.run(_run())

    def test_retrieve_includes_neighbors(self):
        async def _run():
            adapter = self._make_adapter()
            intent = {
                "name": "Credit Risk",
                "description": "Credit risk and loan defaults",
            }
            nodes, edges = await adapter.retrieve_subgraph(
                intent, max_hops=2, max_nodes=20,
            )
            node_ids = {n[0] for n in nodes}
            # Should include credit_risk and its neighbors
            assert "credit_risk" in node_ids
            # loan_default and collateral are direct neighbors
            assert len(nodes) > 1

        asyncio.run(_run())

    def test_retrieve_respects_max_nodes(self):
        async def _run():
            adapter = self._make_adapter()
            intent = {
                "name": "Risk",
                "description": "All types of risk",
            }
            nodes, edges = await adapter.retrieve_subgraph(
                intent, max_hops=5, max_nodes=3,
            )
            assert len(nodes) <= 3

        asyncio.run(_run())

    def test_serialize_natural_language(self):
        async def _run():
            adapter = self._make_adapter()
            nodes = [
                ("credit_risk", {"description": "Credit risk", "entity_type": "concept"}),
                ("loan_default", {"description": "Loan default", "entity_type": "event"}),
            ]
            edges = [
                ("credit_risk", "loan_default", {"description": "causes", "relation_type": "causes"}),
            ]
            text = await adapter.serialize_subgraph(nodes, edges, format="natural_language")
            assert "credit_risk" in text
            assert "loan_default" in text
            assert "causes" in text

        asyncio.run(_run())

    def test_serialize_json(self):
        async def _run():
            adapter = self._make_adapter()
            nodes = [
                ("credit_risk", {"description": "Credit risk"}),
            ]
            edges = []
            text = await adapter.serialize_subgraph(nodes, edges, format="json")
            data = json.loads(text)
            assert "entities" in data
            assert len(data["entities"]) == 1

        asyncio.run(_run())

    def test_retrieve_and_serialize_combined(self):
        async def _run():
            adapter = self._make_adapter()
            intent = {
                "name": "Credit Risk",
                "description": "Credit risk assessment",
            }
            text, nodes, edges = await adapter.retrieve_and_serialize(
                intent, max_hops=2, max_nodes=10,
            )
            assert len(text) > 0
            assert len(nodes) > 0

        asyncio.run(_run())

    def test_fallback_on_no_seeds(self):
        """When no seeds match, adapter should fallback to random subgraph."""
        async def _run():
            adapter = self._make_adapter()
            intent = {
                "name": "Quantum Entanglement",
                "description": "Subatomic particle states",
            }
            # Even with unrelated intent, should still return something
            nodes, edges = await adapter.retrieve_subgraph(
                intent, max_hops=2, max_nodes=5,
            )
            # Fallback returns random nodes
            assert len(nodes) > 0

        asyncio.run(_run())
