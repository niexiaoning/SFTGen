"""
Abstract Critic (Logic-Critic layer) for ArborGraph-Intent.

Provides a pluggable interface for validating generated QA pairs
against their source context.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CriticResult:
    """Result of a critic validation."""
    passed: bool
    score: float  # 0.0 ~ 1.0
    reason: str = ""
    suggestions: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


class BaseCritic(ABC):
    """
    Abstract base class for QA pair quality validators.

    Implementations check whether generated QA pairs are:
    - Factually accurate relative to the source context
    - Logically coherent
    - Appropriately difficult
    - Complete and well-formed
    """

    @abstractmethod
    async def validate(
        self,
        qa_pair: Dict[str, Any],
        context: Dict[str, Any],
    ) -> CriticResult:
        """
        Validate a single QA pair against its source context.

        :param qa_pair: Dict with 'question' and 'answer' keys
        :param context: Dict with 'subgraph_text', 'intent', etc.
        :return: CriticResult with pass/fail, score, and reason
        """

    async def batch_validate(
        self,
        qa_pairs: List[Dict[str, Any]],
        contexts: List[Dict[str, Any]],
    ) -> List[CriticResult]:
        """
        Validate a batch of QA pairs.

        Default: sequential validation. Override for batch optimization.
        """
        results = []
        for qa, ctx in zip(qa_pairs, contexts):
            result = await self.validate(qa, ctx)
            results.append(result)
        return results

    async def filter_qa_pairs(
        self,
        qa_pairs: List[Dict[str, Any]],
        contexts: List[Dict[str, Any]],
        min_score: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Filter QA pairs, keeping only those that pass validation.

        :param qa_pairs: List of QA pair dicts
        :param contexts: Corresponding contexts
        :param min_score: Minimum score to pass
        :return: Filtered list of QA pairs
        """
        results = await self.batch_validate(qa_pairs, contexts)
        filtered = []
        for qa, result in zip(qa_pairs, results):
            if result.passed and result.score >= min_score:
                filtered.append(qa)
        return filtered
