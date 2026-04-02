"""
TGT Generator for the TextGraphTree pipeline.

Extends BaseGenerator to support intent-aware, taxonomy-guided QA generation.
Uses domain-agnostic meta-prompts with cognitive dimension templates.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from textgraphtree.bases.base_generator import BaseGenerator
from textgraphtree.bases.base_llm_client import BaseLLMClient

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Cognitive Dimension Prompt Templates
# ═══════════════════════════════════════════════════════════════════

DIMENSION_PROMPTS = {
    "concept_explanation": {
        "focus": "Deep concept understanding",
        "instruction": (
            "Generate a question that tests deep understanding of a core concept. "
            "The answer should explain the concept thoroughly, including its definition, "
            "significance, and relationship to adjacent concepts."
        ),
        "example_stems": [
            "What is {topic} and why is it important?",
            "Explain the concept of {topic} in detail.",
            "How does {topic} differ from related concepts?",
        ],
    },
    "relational_reasoning": {
        "focus": "Relationship analysis",
        "instruction": (
            "Generate a question about relationships between entities. "
            "The answer should clearly explain how entities connect, influence, "
            "or depend on each other, including causal or structural relationships."
        ),
        "example_stems": [
            "How does {entity_a} relate to {entity_b}?",
            "What is the causal chain between {entity_a} and {entity_b}?",
            "Explain the interaction between {entity_a} and {entity_b}.",
        ],
    },
    "rule_compliance": {
        "focus": "Standards and regulations",
        "instruction": (
            "Generate a question about rules, standards, or compliance requirements. "
            "The answer should detail the specific rule, its applicability, "
            "conditions for compliance, and consequences of non-compliance."
        ),
        "example_stems": [
            "What are the key requirements for {topic}?",
            "How should one ensure compliance with {topic}?",
            "What are the consequences of violating {topic}?",
        ],
    },
    "anomaly_diagnosis": {
        "focus": "Problem identification and diagnosis",
        "instruction": (
            "Generate a question about identifying, diagnosing, or resolving "
            "anomalies and problems. The answer should describe symptoms, "
            "root causes, diagnostic steps, and potential solutions."
        ),
        "example_stems": [
            "What are the common signs of {topic}?",
            "How would you diagnose {topic}?",
            "What steps would you take to resolve {topic}?",
        ],
    },
    "comparative_analysis": {
        "focus": "Comparison and evaluation",
        "instruction": (
            "Generate a question comparing different entities, approaches, "
            "or alternatives. The answer should provide a structured comparison "
            "with clear criteria, advantages, disadvantages, and recommendations."
        ),
        "example_stems": [
            "Compare {entity_a} with {entity_b} across key dimensions.",
            "What are the advantages and disadvantages of each approach?",
            "When should {entity_a} be preferred over {entity_b}?",
        ],
    },
    "procedural_knowledge": {
        "focus": "Step-by-step procedures",
        "instruction": (
            "Generate a question about step-by-step procedures or processes. "
            "The answer should provide an ordered sequence of steps with "
            "clear prerequisites, actions, and expected outcomes."
        ),
        "example_stems": [
            "What is the step-by-step process for {topic}?",
            "How should one execute {topic} from start to finish?",
            "What are the critical steps in {topic} and what could go wrong?",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════
# Meta-Prompt Template
# ═══════════════════════════════════════════════════════════════════

META_PROMPT_TEMPLATE = """You are a domain expert generating high-quality training data.

## Knowledge Context
The following knowledge graph data provides the factual basis for your question-answer pair:

{subgraph_text}

## Task Intent
Topic Area: {intent_name}
Description: {intent_description}
Cognitive Focus: {dimension_focus}

## Generation Instruction
{dimension_instruction}

## Requirements
1. The question MUST be answerable from the knowledge context above
2. The answer MUST be grounded in facts from the context (no hallucination)
3. The answer should be detailed, well-structured, and comprehensive
4. Use the same language as the source context
5. DO NOT simply copy-paste from the context; synthesize and explain

## Output Format
Provide your output in exactly this format:

Question: <your question>

Answer: <your detailed answer>"""


class TGTGenerator(BaseGenerator):
    """
    Generator that produces QA pairs guided by taxonomy intents
    and cognitive dimension templates.

    Unlike other generators that take raw batches, this generator
    accepts pre-serialized subgraph text and intent metadata.
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        data_format: str = "ChatML",
        default_dimension: str = "concept_explanation",
    ):
        super().__init__(llm_client)
        self.data_format = data_format
        self.default_dimension = default_dimension
        self._generation_mode = "tgt"

    def build_prompt(
        self,
        batch: Tuple[List[Tuple[str, dict]], List[Tuple[Any, Any, dict]]],
        intent: Optional[Dict[str, Any]] = None,
        subgraph_text: Optional[str] = None,
    ) -> str:
        """
        Build a TGT prompt.

        Can work in two modes:
        1. Standard mode (batch only): falls back to basic serialization
        2. Intent-aware mode (batch + intent + subgraph_text): full TGT prompting
        """
        if intent and subgraph_text:
            return self._build_intent_prompt(intent, subgraph_text)
        else:
            return self._build_fallback_prompt(batch)

    def _build_intent_prompt(
        self,
        intent: Dict[str, Any],
        subgraph_text: str,
    ) -> str:
        """Build prompt using intent and cognitive dimension templates."""
        dimension = intent.get("cognitive_dimension", self.default_dimension)
        dim_config = DIMENSION_PROMPTS.get(
            dimension,
            DIMENSION_PROMPTS[self.default_dimension],
        )

        return META_PROMPT_TEMPLATE.format(
            subgraph_text=subgraph_text,
            intent_name=intent.get("name", "General"),
            intent_description=intent.get("description", ""),
            dimension_focus=dim_config["focus"],
            dimension_instruction=dim_config["instruction"],
        )

    def _build_fallback_prompt(
        self,
        batch: Tuple[List[Tuple[str, dict]], List[Tuple[Any, Any, dict]]],
    ) -> str:
        """Fallback: serialize batch into simple context + prompt."""
        nodes, edges = batch
        lines = []

        for node_id, node_data in nodes:
            desc = node_data.get("description", "")
            lines.append(f"- {node_id}: {desc}")

        for edge in edges:
            src, tgt = edge[0], edge[1]
            edge_data = edge[2] if len(edge) > 2 else {}
            rel = edge_data.get("description", "relates to")
            lines.append(f"- {src} → {tgt}: {rel}")

        context = "\n".join(lines)
        return (
            f"Based on the following knowledge:\n\n{context}\n\n"
            "Generate a high-quality Question-Answer pair.\n\n"
            "Question: <your question>\n\nAnswer: <your answer>"
        )

    @staticmethod
    def parse_response(response: str) -> dict:
        """
        Parse LLM response into QA pair dict.

        Supports "Question: ... Answer: ..." format in both English and Chinese.
        """
        response = response.strip()
        result = {}

        # Try multiple marker patterns
        q_patterns = [
            r"Question:\s*(.*?)(?=\n\s*(?:Answer|答案)[：:])",
            r"问题[：:]\s*(.*?)(?=\n\s*(?:Answer|答案)[：:])",
            r"Q:\s*(.*?)(?=\n\s*A:)",
        ]
        a_patterns = [
            r"(?:Answer|答案)[：:]\s*([\s\S]*?)$",
            r"A:\s*([\s\S]*?)$",
        ]

        question = ""
        answer = ""

        for qp in q_patterns:
            match = re.search(qp, response, re.DOTALL | re.IGNORECASE)
            if match:
                question = match.group(1).strip()
                break

        for ap in a_patterns:
            match = re.search(ap, response, re.DOTALL | re.IGNORECASE)
            if match:
                answer = match.group(1).strip()
                break

        if not question or not answer:
            # Fallback: split by first double newline
            parts = response.split("\n\n", 1)
            if len(parts) >= 2:
                question = parts[0].strip()
                answer = parts[1].strip()
            elif response:
                lines = response.split("\n")
                if len(lines) >= 2:
                    question = lines[0].strip()
                    answer = "\n".join(lines[1:]).strip()

        if question and answer:
            key = f"tgt_{hash(question) % 10000:04d}"
            result[key] = {
                "question": question,
                "answer": answer,
                "mode": "tgt",
            }

        return result

    async def generate_with_intent(
        self,
        intent: Dict[str, Any],
        subgraph_text: str,
        nodes: List[Tuple[str, dict]],
        edges: List[Tuple[Any, Any, dict]],
    ) -> Dict[str, Any]:
        """
        Generate using intent-aware prompting.

        :param intent: Intent dict with name, description, cognitive_dimension
        :param subgraph_text: Pre-serialized subgraph text
        :param nodes: Raw nodes for metadata
        :param edges: Raw edges for metadata
        :return: Generated QA pair dict
        """
        prompt = self._build_intent_prompt(intent, subgraph_text)
        response = await self.llm_client.generate_answer(prompt)
        qa_pairs = self.parse_response(response)

        # Add TGT metadata to each pair
        for key, qa in qa_pairs.items():
            qa["metadata"] = {
                "intent_name": intent.get("name", ""),
                "cognitive_dimension": intent.get("cognitive_dimension", ""),
                "generation_mode": "tgt",
                "source_node_count": len(nodes),
                "source_edge_count": len(edges),
            }

        return qa_pairs
