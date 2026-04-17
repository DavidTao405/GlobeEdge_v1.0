"""
Confidence Quality Gate
LLM 信心評估閘門

包裝 ConfidenceEvaluator（LLM 引擎）作為品質閘門。
作為第二道品質閘門（可選，CRAG Grade B 時觸發）。
"""

from __future__ import annotations

from typing import Any

from src.core.rag.models import GateAction, GateResult, ScoredChunk
from src.domain.entities.kb_entry import (
    AgeGroup,
    ConfidenceLevel,
    IntentAnalysis,
    KBEntry,
    KBEntryStatus,
    Scenario,
)
from src.domain.shared.confidence_evaluator import ConfidenceEvaluator
from src.shared.observability import get_logger

logger = get_logger(__name__)

# ConfidenceLevel → GateAction mapping
_LEVEL_ACTION = {
    ConfidenceLevel.HIGH: GateAction.CONTINUE,
    ConfidenceLevel.MEDIUM: GateAction.DEGRADE,
    ConfidenceLevel.LOW: GateAction.REFER,
}

_LEVEL_STRATEGY = {
    ConfidenceLevel.HIGH: "NORMAL",
    ConfidenceLevel.MEDIUM: "CAUTIOUS",
    ConfidenceLevel.LOW: "REFER",
}


class ConfidenceQualityGate:
    """
    LLM-based confidence quality gate.

    More accurate but slower than CRAG — requires an LLM call.
    Converts ScoredChunks to KBEntry format for ConfidenceEvaluator.
    """

    def __init__(self, confidence_evaluator: ConfidenceEvaluator) -> None:
        self._evaluator = confidence_evaluator

    async def evaluate(
        self,
        query: str,
        chunks: list[ScoredChunk],
        context: dict[str, Any] | None = None,
    ) -> GateResult:
        context = context or {}

        # Build IntentAnalysis from context
        intent = IntentAnalysis(
            scenario=Scenario(context["scenario"]) if context.get("scenario") else None,
            age_group=AgeGroup(context["age_group"]) if context.get("age_group") else None,
            keywords=context.get("keywords", []),
            confidence=ConfidenceLevel(context.get("intent_confidence", "medium")),
            reasoning=context.get("intent_reasoning", ""),
            retrieval_path=context.get("retrieval_path", ""),
            original_query=query,
        )

        # Convert ScoredChunks → KBEntry (simplified)
        kb_entries = [self._chunk_to_kb_entry(chunk) for chunk in chunks]

        # LLM evaluation
        result = await self._evaluator.evaluate(query, intent, kb_entries)

        return GateResult(
            action=_LEVEL_ACTION[result.level],
            grade=result.level.value,
            confidence={"high": 0.9, "medium": 0.5, "low": 0.1}[result.level.value],
            strategy=_LEVEL_STRATEGY[result.level],
            reasoning=result.reasoning,
            referral_needed=result.should_refer,
        )

    @staticmethod
    def _chunk_to_kb_entry(chunk: ScoredChunk) -> KBEntry:
        """Convert ScoredChunk back to KBEntry for ConfidenceEvaluator."""
        return KBEntry(
            id=chunk.chunk_id,
            kb_group_id="",
            title=chunk.content[:100],
            body=chunk.content,
            scenario=Scenario(chunk.scenario) if chunk.scenario else Scenario.EMOTION_REGULATION,
            age_groups=[AgeGroup(ag) for ag in chunk.age_groups] if chunk.age_groups else [],
            risk_level=chunk.risk_level or "normal",
            keywords=chunk.metadata.get("keywords", []),
            status=KBEntryStatus.APPROVED,
        )
