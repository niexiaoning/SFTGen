"""
Auto-generate taxonomy trees from domain documents using LLM.

Given a domain whitepaper or specification document, this module uses
Few-shot prompting to map its content onto a universal cognitive dimension
framework and produce a domain-specific taxonomy tree.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from arborgraph.bases.base_llm_client import BaseLLMClient
from arborgraph.models.taxonomy.taxonomy_tree import (
    COGNITIVE_DIMENSIONS,
    TaxonomyNode,
    TaxonomyTree,
)

logger = logging.getLogger(__name__)

# ─── Prompt Templates ──────────────────────────────────────────────

_AUTO_TAXONOMY_SYSTEM_PROMPT = """You are an expert at constructing hierarchical task taxonomies for any knowledge domain.

Your job: Given a domain document, produce a structured JSON taxonomy tree that organizes the domain's key concepts, tasks, and knowledge areas into a tree structure.

Each node in the tree MUST have:
- "id": unique kebab-case identifier (e.g., "credit-risk-assessment")
- "name": human-readable name
- "description": 1-2 sentence description
- "cognitive_dimension": one of the following:
  - "concept_explanation" — defining core concepts
  - "relational_reasoning" — understanding relationships between entities
  - "rule_compliance" — checking compliance with rules/regulations
  - "anomaly_diagnosis" — identifying and diagnosing problems
  - "comparative_analysis" — comparing alternatives or entities
  - "procedural_knowledge" — step-by-step procedures
- "children": list of child nodes (can be empty for leaf nodes)

Guidelines:
1. Create 3-5 top-level categories
2. Each category should have 2-4 subcategories
3. Leaf nodes should be specific enough to generate focused QA pairs
4. Distribute cognitive dimensions across the tree (don't use only one)
5. Tree depth should be 2-4 levels
6. Total nodes should be 15-40"""

_AUTO_TAXONOMY_USER_PROMPT = """Domain: {domain_name}

Document content:
---
{document_text}
---

Generate a taxonomy tree for this domain in the following JSON format:
{{
  "name": "<domain_name>_taxonomy",
  "description": "<brief description>",
  "domain": "{domain_name}",
  "version": "1.0",
  "nodes": [
    {{
      "id": "<root-id>",
      "name": "<root name>",
      "description": "<description>",
      "cognitive_dimension": "<dimension>",
      "children": [
        {{
          "id": "<child-id>",
          "name": "<child name>",
          "description": "<description>",
          "cognitive_dimension": "<dimension>",
          "children": []
        }}
      ]
    }}
  ]
}}

Output ONLY the JSON, no explanations."""

_FEW_SHOT_EXAMPLE = """Example for a "Network Security" domain:
{
  "name": "network_security_taxonomy",
  "description": "Taxonomy for network security knowledge and tasks",
  "domain": "network_security",
  "version": "1.0",
  "nodes": [
    {
      "id": "threat-analysis",
      "name": "Threat Analysis",
      "description": "Understanding and analyzing security threats",
      "cognitive_dimension": "concept_explanation",
      "children": [
        {
          "id": "vulnerability-assessment",
          "name": "Vulnerability Assessment",
          "description": "Identifying and evaluating security vulnerabilities in systems",
          "cognitive_dimension": "anomaly_diagnosis",
          "children": []
        },
        {
          "id": "attack-vector-analysis",
          "name": "Attack Vector Analysis",
          "description": "Analyzing potential attack paths and methods",
          "cognitive_dimension": "relational_reasoning",
          "children": []
        }
      ]
    },
    {
      "id": "security-compliance",
      "name": "Security Compliance",
      "description": "Ensuring adherence to security standards and regulations",
      "cognitive_dimension": "rule_compliance",
      "children": [
        {
          "id": "policy-audit",
          "name": "Policy Audit",
          "description": "Auditing security policies against standards",
          "cognitive_dimension": "rule_compliance",
          "children": []
        }
      ]
    }
  ]
}
"""


class AutoTaxonomy:
    """
    Automatically generate taxonomy trees from domain documents via LLM.
    """

    def __init__(self, llm_client: BaseLLMClient):
        self.llm_client = llm_client

    async def generate_from_document(
        self,
        document_text: str,
        domain_name: str = "general",
        max_retries: int = 3,
    ) -> TaxonomyTree:
        """
        Generate a taxonomy tree from a domain document.

        :param document_text: The domain document/whitepaper text
        :param domain_name: Name of the domain
        :param max_retries: Max attempts if LLM response is unparsable
        :return: TaxonomyTree instance
        """
        # Truncate very long documents to avoid exceeding context window
        if len(document_text) > 15000:
            logger.warning(
                "Document too long (%d chars), truncating to 15000",
                len(document_text),
            )
            document_text = document_text[:15000] + "\n... [truncated]"

        prompt = self._build_prompt(document_text, domain_name)

        for attempt in range(max_retries):
            try:
                response = await self.llm_client.query(prompt)
                tree_data = self._parse_response(response)
                tree = TaxonomyTree.from_dict(tree_data)

                # Validate
                issues = tree.validate()
                errors = [i for i in issues if i.startswith("ERROR")]
                if errors:
                    logger.warning(
                        "Generated tree has errors (attempt %d/%d): %s",
                        attempt + 1, max_retries, errors,
                    )
                    if attempt < max_retries - 1:
                        continue
                    raise ValueError(f"Failed to generate valid taxonomy: {errors}")

                logger.info(
                    "Auto-generated taxonomy: %s (%d nodes, depth %d)",
                    tree.name, tree.size, tree.max_depth,
                )
                return tree

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(
                    "Failed to parse LLM response (attempt %d/%d): %s",
                    attempt + 1, max_retries, str(e),
                )
                if attempt >= max_retries - 1:
                    raise ValueError(
                        f"Failed to generate taxonomy after {max_retries} attempts: {e}"
                    ) from e

        # Should not reach here, but just in case
        raise ValueError("Failed to generate taxonomy")

    async def enrich_tree(
        self,
        tree: TaxonomyTree,
        document_text: str,
    ) -> TaxonomyTree:
        """
        Enrich an existing tree with better descriptions using domain doc.

        :param tree: Existing taxonomy tree
        :param document_text: Domain document for context
        :return: Enriched TaxonomyTree
        """
        enrich_prompt = (
            f"Given this domain document:\n---\n{document_text[:8000]}\n---\n\n"
            f"And this existing taxonomy:\n{json.dumps(tree.to_dict(), indent=2, ensure_ascii=False)}\n\n"
            f"Improve the descriptions of each node to be more specific and "
            f"grounded in the document content. Output the full improved JSON taxonomy."
        )
        try:
            response = await self.llm_client.query(enrich_prompt)
            enriched_data = self._parse_response(response)
            return TaxonomyTree.from_dict(enriched_data)
        except Exception as e:
            logger.warning("Failed to enrich taxonomy: %s. Returning original.", e)
            return tree

    def _build_prompt(self, document_text: str, domain_name: str) -> str:
        """Build the full prompt with system context, few-shot, and user query."""
        user_prompt = _AUTO_TAXONOMY_USER_PROMPT.format(
            domain_name=domain_name,
            document_text=document_text,
        )
        # Combine system prompt, few-shot example, and user query
        full_prompt = (
            f"{_AUTO_TAXONOMY_SYSTEM_PROMPT}\n\n"
            f"Here is an example:\n{_FEW_SHOT_EXAMPLE}\n\n"
            f"Now generate for the following:\n\n{user_prompt}"
        )
        return full_prompt

    def _parse_response(self, response: str) -> dict:
        """Extract JSON from LLM response."""
        response = response.strip()

        # Try to find JSON block in response
        # Case 1: Response is pure JSON
        if response.startswith("{"):
            return json.loads(response)

        # Case 2: JSON wrapped in markdown code block
        if "```json" in response:
            start = response.index("```json") + 7
            end = response.index("```", start)
            return json.loads(response[start:end].strip())

        if "```" in response:
            start = response.index("```") + 3
            # Skip optional language tag on same line
            newline = response.index("\n", start)
            start = newline + 1
            end = response.index("```", start)
            return json.loads(response[start:end].strip())

        # Case 3: Try to find first { ... last }
        first_brace = response.find("{")
        last_brace = response.rfind("}")
        if first_brace >= 0 and last_brace > first_brace:
            return json.loads(response[first_brace : last_brace + 1])

        raise json.JSONDecodeError(
            "No JSON found in response",
            response[:200],
            0,
        )
