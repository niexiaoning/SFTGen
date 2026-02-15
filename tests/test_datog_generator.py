"""
Tests for DA-ToG Phase 4: Meta-Prompt Template and DAToGGenerator.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from graphgen.models.generator.datog_generator import DAToGGenerator, DIMENSION_PROMPTS


class TestDAToGGenerator:
    def test_build_intent_prompt(self):
        mock_llm = AsyncMock()
        generator = DAToGGenerator(mock_llm)
        
        intent = {
            "name": "Credit Risk",
            "description": "Understanding borrower default probability.",
            "cognitive_dimension": "concept_explanation"
        }
        subgraph_text = "Node: Borrower A, Debt: 1000"
        
        prompt = generator._build_intent_prompt(intent, subgraph_text)
        
        assert "Borrower A" in prompt
        assert "Credit Risk" in prompt
        assert DIMENSION_PROMPTS["concept_explanation"]["focus"] in prompt

    def test_parse_response_english(self):
        mock_llm = AsyncMock()
        generator = DAToGGenerator(mock_llm)
        
        response = "Question: What is credit risk?\nAnswer: It is the risk of default."
        results = generator.parse_response(response)
        
        assert len(results) == 1
        key = list(results.keys())[0]
        assert results[key]["question"] == "What is credit risk?"
        assert results[key]["answer"] == "It is the risk of default."

    def test_parse_response_chinese(self):
        mock_llm = AsyncMock()
        generator = DAToGGenerator(mock_llm)
        
        response = "问题：信用风险是什么？\n答案：信用风险是指借款人违约的可能性。"
        results = generator.parse_response(response)
        
        assert len(results) == 1
        key = list(results.keys())[0]
        assert "信用风险" in results[key]["question"]
        assert "违约" in results[key]["answer"]

    def test_parse_response_fallback(self):
        mock_llm = AsyncMock()
        generator = DAToGGenerator(mock_llm)
        
        response = "Only one line"
        results = generator.parse_response(response)
        assert len(results) == 0

        response_two = "First line\n\nSecond line"
        results = generator.parse_response(response_two)
        assert len(results) == 1

    def test_generate_with_intent(self):
        async def _run():
            mock_llm = AsyncMock()
            mock_llm.generate_answer = AsyncMock(return_value="Question: Q?\nAnswer: A.")
            generator = DAToGGenerator(mock_llm)
            
            intent = {"name": "Topic"}
            results = await generator.generate_with_intent(intent, "Ctx", [], [])
            
            assert len(results) == 1
            key = list(results.keys())[0]
            assert results[key]["metadata"]["generation_mode"] == "datog"
        
        asyncio.run(_run())
        
    def test_all_dimensions_have_prompts(self):
        from graphgen.models.taxonomy.taxonomy_tree import COGNITIVE_DIMENSIONS
        for dim in COGNITIVE_DIMENSIONS:
            assert dim in DIMENSION_PROMPTS
