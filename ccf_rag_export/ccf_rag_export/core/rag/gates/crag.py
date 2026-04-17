"""
CRAG Quality Gate
CRAG 品質閘門

包裝 CRAGEvaluator（規則引擎）作為品質閘門。
Grade A → CONTINUE, Grade B → DEGRADE, Grade C → DEGRADE (LLM_FALLBACK)
作為第一道品質閘門（快速，不需要 LLM call）。
"""

from __future__ import annotations

from typing import Any

from src.core.rag.models import GateAction, GateResult, ScoredChunk
from src.domain.shared.crag_evaluator import (
    CRAGEvaluator,
    CRAGGrade,
    SearchResult as CRAGSearchResult,
)
from src.shared.observability import get_logger

logger = get_logger(__name__)

# Grade → GateAction mapping
_GRADE_ACTION = {
    CRAGGrade.A: GateAction.CONTINUE,
    CRAGGrade.B: GateAction.DEGRADE,
    CRAGGrade.C: GateAction.DEGRADE,
}

# Grade → strategy mapping
_GRADE_STRATEGY = {
    CRAGGrade.A: "NORMAL",
    CRAGGrade.B: "CAUTIOUS",
    CRAGGrade.C: "LLM_FALLBACK",
}


class CRAGQualityGate:
    """
    Rule-based CRAG quality gate.

    Fast path (no LLM call):
    - Computes confidence from similarity + metadata + text_overlap
    - Grade A (>=0.7) → CONTINUE
    - Grade B (0.3-0.7) → DEGRADE
    - Grade C (<0.3) → DEGRADE with LLM_FALLBACK strategy
    """

    def __init__(self, crag_evaluator: CRAGEvaluator) -> None:
        self._evaluator = crag_evaluator

    async def evaluate(
        self,
        query: str,
        chunks: list[ScoredChunk],
        context: dict[str, Any] | None = None,
    ) -> GateResult:
        context = context or {}

        # Convert ScoredChunk → CRAGSearchResult
        search_results = [
            CRAGSearchResult(
                id=chunk.chunk_id,
                content=chunk.content,
                score=chunk.score,
                scenario=chunk.scenario,
                age_groups=chunk.age_groups,
                risk_level=chunk.risk_level or "normal",
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]

        # Run CRAG evaluation (synchronous, rule-based)
        crag_result = self._evaluator.evaluate(
            query,
            search_results,
            expected_scenario=context.get("scenario"),
            expected_age_group=context.get("age_group"),
        )

        referral_needed = (
            crag_result.referral is not None
            and crag_result.referral.should_refer
        )

        return GateResult(
            action=_GRADE_ACTION[crag_result.grade],
            grade=crag_result.grade.value,
            confidence=crag_result.confidence,
            strategy=_GRADE_STRATEGY[crag_result.grade],
            reasoning=crag_result.decision,
            referral_needed=referral_needed,
        )
