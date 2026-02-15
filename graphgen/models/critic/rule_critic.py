"""
Rule-based Critic for DA-ToG.

Provides a pluggable rule-based validator for domains with strong
formal rules (e.g., regulatory compliance, mathematical proofs).
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from graphgen.bases.base_critic import BaseCritic, CriticResult

logger = logging.getLogger(__name__)


class RuleCritic(BaseCritic):
    """
    Rule-based quality validator.

    Users can register custom validation functions that check QA pairs
    against domain-specific rules.
    """

    def __init__(self):
        self._rules: List[Dict[str, Any]] = []

    def add_rule(
        self,
        name: str,
        check_fn: Callable[[Dict[str, Any], Dict[str, Any]], bool],
        weight: float = 1.0,
        description: str = "",
    ) -> None:
        """
        Register a validation rule.

        :param name: Rule name for logging
        :param check_fn: Function(qa_pair, context) -> bool
        :param weight: Weight of this rule in the overall score
        :param description: Human description of what this rule checks
        """
        self._rules.append({
            "name": name,
            "check_fn": check_fn,
            "weight": weight,
            "description": description,
        })

    async def validate(
        self,
        qa_pair: Dict[str, Any],
        context: Dict[str, Any],
    ) -> CriticResult:
        """Validate QA pair against all registered rules."""
        if not self._rules:
            return CriticResult(
                passed=True, score=1.0,
                reason="No rules registered, passing by default",
            )

        total_weight = sum(r["weight"] for r in self._rules)
        weighted_score = 0.0
        failed_rules = []
        suggestions = []

        for rule in self._rules:
            try:
                passed = rule["check_fn"](qa_pair, context)
                if passed:
                    weighted_score += rule["weight"]
                else:
                    failed_rules.append(rule["name"])
                    if rule["description"]:
                        suggestions.append(
                            f"Fix rule '{rule['name']}': {rule['description']}"
                        )
            except Exception as e:
                logger.warning("Rule '%s' raised exception: %s", rule["name"], e)
                failed_rules.append(f"{rule['name']} (error)")

        score = weighted_score / total_weight if total_weight > 0 else 0.0
        passed = len(failed_rules) == 0

        reason = "All rules passed" if passed else f"Failed: {', '.join(failed_rules)}"

        return CriticResult(
            passed=passed,
            score=score,
            reason=reason,
            suggestions=suggestions,
        )


# ─── Built-in Rules ────────────────────────────────────────────────

def min_answer_length(min_chars: int = 10):
    """Rule: answer must be at least min_chars long."""
    def check(qa: dict, ctx: dict) -> bool:
        answer = qa.get("answer", "")
        return len(answer.strip()) >= min_chars
    return check


def min_question_length(min_chars: int = 5):
    """Rule: question must be at least min_chars long."""
    def check(qa: dict, ctx: dict) -> bool:
        question = qa.get("question", "")
        return len(question.strip()) >= min_chars
    return check


def answer_not_identical_to_question():
    """Rule: answer must differ from question."""
    def check(qa: dict, ctx: dict) -> bool:
        q = qa.get("question", "").strip().lower()
        a = qa.get("answer", "").strip().lower()
        return q != a
    return check


def answer_contains_keywords(min_overlap: int = 1):
    """Rule: answer should contain at least some keywords from context."""
    def check(qa: dict, ctx: dict) -> bool:
        context_text = ctx.get("subgraph_text", "") or ctx.get("text", "")
        answer = qa.get("answer", "")
        if not context_text:
            return True
        # Simple keyword overlap
        ctx_words = set(context_text.lower().split())
        ans_words = set(answer.lower().split())
        overlap = ctx_words & ans_words
        return len(overlap) >= min_overlap
    return check
