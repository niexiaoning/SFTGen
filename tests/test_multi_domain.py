"""
End-to-end validation for multi_domain ArborGraph-Intent.

Verifies that the same pipeline code can handle different domain
configurations (Finance and Cybersecurity).
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from arborgraph.intent_pipeline import IntentPipeline


class MockGraphStorage:
    def __init__(self):
        # Provide a node that matches keywords from both domains to ensure linkage
        self.node = {"description": "Market Risk, Network Security, Credit, Vulnerability, rule compliance"}

    async def get_all_nodes(self): return [("node1", self.node)]
    async def get_all_edges(self): return []
    async def get_node(self, id): return self.node
    async def get_node_edges(self, id): return []


class TestMultiDomainValidation:
    async def _test_domain(self, config_path: str):
        mock_llm = AsyncMock()
        # Mock LLM response with keywords to pass RuleCritic overlap check
        mock_llm.generate_answer = AsyncMock(
            return_value="Question: What is Market Risk?\nAnswer: Market Risk is the risk of losses in positions arising from movements in market prices."
        )
        mock_llm.query = AsyncMock(return_value='{"passed": true, "overall_score": 0.8}')
        
        graph = MockGraphStorage()
        
        # Load pipeline from config
        pipeline = IntentPipeline.from_config(
            config_path=config_path,
            llm_client=mock_llm,
            graph_storage=graph,
        )
        
        # Run small batch
        results = await pipeline.run(target_count=2, batch_size=5)
        
        assert len(results) > 0
        assert results[0]["metadata"]["pipeline"] == "intent"
        return results

    def test_finance_domain(self):
        async def _run():
            results = await self._test_domain("arborgraph/configs/intent/finance/intent_config.yaml")
            assert len(results) > 0
        asyncio.run(_run())

    def test_cybersecurity_domain(self):
        async def _run():
            results = await self._test_domain("arborgraph/configs/intent/cybersecurity/intent_config.yaml")
            assert len(results) > 0
        asyncio.run(_run())
