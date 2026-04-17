"""
RAG Pipeline Engine
RAG 管線執行引擎

固定的五階段管線，行為由 PipelineProfile 決定。
這個 class 裡不應該出現任何 CCF 或行業特定邏輯。

Stages:
0. Safety Gate — can short-circuit entire pipeline
1. Intent Analysis — LLM-based intent extraction → QueryFilters
2. Layered Retrieval + RRF Fusion
3. Quality Gates — serial evaluation (CRAG → Confidence)
4. Post-safety — filter KB content before injection
5. Build citation context string
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from src.core.rag.fusion import rrf_fuse
from src.core.rag.models import (
    GateAction,
    GateResult,
    PipelineProfile,
    SafetyResult,
    ScoredChunk,
)
from src.core.rag.profiles.registry import ProfileRegistry
from src.core.rag.relevance_scorer import score_relevance
from src.shared.observability import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """RAG Pipeline 執行結果"""

    # Content
    chunks: list[ScoredChunk] = field(default_factory=list)
    context_string: str = ""

    # Quality
    gate_result: GateResult | None = None
    strategy: str | None = None

    # Safety
    short_circuited: bool = False
    safety_response: str | None = None
    safety_result: SafetyResult | None = None

    # Referral
    referral_needed: bool = False
    emergency_resources: list[str] = field(default_factory=list)

    # Intent
    intent_result: dict[str, Any] = field(default_factory=dict)

    # Debug
    metadata: dict[str, Any] = field(default_factory=dict)


class RAGPipelineEngine:
    """
    Generic RAG Pipeline Engine.

    Drives a five-stage pipeline based on PipelineProfile configuration.
    No domain-specific logic — all behavior comes from the profile.
    """

    def __init__(self, profile_registry: ProfileRegistry) -> None:
        self._registry = profile_registry

    async def execute(
        self,
        query: str,
        profile_name: str,
        *,
        conversation_context: dict[str, Any] | None = None,
        intent_analyzer: Any | None = None,
        skip_safety: bool = False,
    ) -> PipelineResult:
        """
        Execute the full RAG pipeline.

        Args:
            query: User query.
            profile_name: Which profile to use (e.g. "ccf_parenting").
            conversation_context: Optional conversation context dict.
            intent_analyzer: Optional IntentAnalyzer instance for Stage 1.
            skip_safety: Skip Stage 0 Safety Gate (for agent tool calls
                         where safety was already checked at chat entrance).

        Returns:
            PipelineResult with chunks, context, strategy, referral info.
        """
        profile = self._registry.get(profile_name)
        context = conversation_context or {}

        # ── Stage 0: Safety Gate ──────────────────────────────────
        if skip_safety:
            safety = SafetyResult(action=GateAction.CONTINUE)
            logger.debug("pipeline_safety_skipped")
        else:
            safety = await profile.safety_gate.check(query, context)
        if safety.action == GateAction.SHORT_CIRCUIT:
            logger.info("pipeline_safety_short_circuit", query_len=len(query))
            return PipelineResult(
                short_circuited=True,
                safety_response=safety.message,
                safety_result=safety,
                referral_needed=safety.referral_needed,
                emergency_resources=safety.emergency_resources,
            )

        # ── Stage 1: Intent Analysis ─────────────────────────────
        intent_result = await self._analyze_intent(
            profile, query, context, intent_analyzer
        )
        filters = profile.intent.extract_filters(intent_result)

        # Enrich context with intent for downstream gates
        context.update({
            "scenario": intent_result.get("scenario"),
            "age_group": intent_result.get("age_group"),
            "keywords": intent_result.get("keywords", []),
            "intent_confidence": intent_result.get("confidence", "medium"),
            "intent_reasoning": intent_result.get("reasoning", ""),
            "retrieval_path": intent_result.get("retrieval_path", ""),
        })

        # ── Stage 2: Layered Retrieval + RRF Fusion + Rerank ─────
        chunks = await self._retrieve_and_rerank(profile, query, filters)
        logger.info("pipeline_retrieval_done", chunks=len(chunks))

        # ── Stage 3: Quality Gates (serial) ──────────────────────
        gate_result = await self._run_quality_gates(
            profile, query, chunks, context
        )

        # ── Stage 4: Post-safety — filter KB content ─────────────
        chunks = await self._post_safety_filter(profile, chunks)

        # ── Stage 4.5: Context Relevance Scoring ──────────────────
        chunks = score_relevance(
            chunks,
            query=query,
            intent_scenario=context.get("scenario"),
        )
        logger.info("pipeline_relevance_scored", chunks=len(chunks))

        # ── Stage 5: Build citation context ──────────────────────
        context_string = profile.citation.format(chunks)

        return PipelineResult(
            chunks=chunks,
            context_string=context_string,
            gate_result=gate_result,
            strategy=gate_result.strategy if gate_result else None,
            safety_result=safety,
            referral_needed=(
                (gate_result.referral_needed if gate_result else False)
                or safety.referral_needed
            ),
            intent_result=intent_result,
        )

    async def _analyze_intent(
        self,
        profile: PipelineProfile,
        query: str,
        context: dict[str, Any],
        intent_analyzer: Any | None,
    ) -> dict[str, Any]:
        """
        Stage 1: Intent analysis.

        If an IntentAnalyzer is provided, use it for LLM-based analysis.
        Otherwise, return a minimal intent dict from context.
        """
        if intent_analyzer is not None:
            try:
                conv_context = context.get("conversation_history", "")
                intent = await intent_analyzer.analyze(query, conv_context)
                return {
                    "scenario": intent.scenario.value if intent.scenario else None,
                    "age_group": intent.age_group.value if intent.age_group else None,
                    "keywords": intent.keywords,
                    "confidence": intent.confidence.value,
                    "reasoning": intent.reasoning,
                    "retrieval_path": intent.retrieval_path,
                }
            except Exception as e:
                logger.warning("intent_analysis_fallback", error=str(e))

        # Fallback: extract from context if available
        return {
            "scenario": context.get("scenario"),
            "age_group": context.get("age_group"),
            "keywords": context.get("keywords", []),
            "confidence": "low",
            "reasoning": "No intent analyzer available",
            "retrieval_path": "fallback",
        }

    async def _retrieve_and_rerank(
        self,
        profile: PipelineProfile,
        query: str,
        filters: Any,
    ) -> list[ScoredChunk]:
        """
        Stage 2: Parallel retrieval + RRF fusion + optional rerank.
        """
        if not profile.retrieval_layers:
            return []

        # Run all retrievers in parallel
        tasks = [
            layer.retriever.retrieve(query, filters, filters.top_k)
            for layer in profile.retrieval_layers
        ]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results: list[list[ScoredChunk]] = []
        valid_weights: list[float] = []
        for i, result in enumerate(all_results):
            if isinstance(result, Exception):
                logger.warning(
                    "retriever_failed",
                    name=profile.retrieval_layers[i].name,
                    error=str(result),
                )
            else:
                valid_results.append(result)
                valid_weights.append(profile.retrieval_layers[i].weight)

        if not valid_results:
            return []

        fused = rrf_fuse(valid_results, valid_weights)

        # Optional rerank
        if profile.reranker is not None:
            try:
                fused = await profile.reranker.rerank(query, fused)
                logger.info("pipeline_rerank_done", chunks=len(fused))
            except Exception as e:
                logger.warning("reranker_failed", error=str(e))

        return fused

    async def _post_safety_filter(
        self,
        profile: PipelineProfile,
        chunks: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        """
        Stage 4: Post-safety — check KB content before injection.

        If post_safety_gate is None, pass through unchanged.
        Otherwise, check each chunk and redact unsafe content.
        """
        if profile.post_safety_gate is None or not chunks:
            return chunks

        filtered: list[ScoredChunk] = []
        redacted_count = 0

        for chunk in chunks:
            result = await profile.post_safety_gate.check(chunk.content)
            if result.action == GateAction.SHORT_CIRCUIT:
                # Redact unsafe KB content
                filtered.append(ScoredChunk(
                    chunk_id=chunk.chunk_id,
                    content="[內容已過濾]",
                    score=0.0,
                    source=chunk.source,
                    metadata=chunk.metadata,
                    scenario=chunk.scenario,
                    age_groups=chunk.age_groups,
                    risk_level=chunk.risk_level,
                ))
                redacted_count += 1
            else:
                filtered.append(chunk)

        if redacted_count > 0:
            logger.warning(
                "pipeline_post_safety_redacted",
                redacted=redacted_count,
                total=len(chunks),
            )

        return filtered

    async def _run_quality_gates(
        self,
        profile: PipelineProfile,
        query: str,
        chunks: list[ScoredChunk],
        context: dict[str, Any],
    ) -> GateResult | None:
        """
        Stage 3: Serial quality gate evaluation.

        Optimization: if first gate returns CONTINUE (Grade A),
        skip subsequent gates to save LLM calls.
        """
        if not profile.quality_gates:
            return GateResult(
                action=GateAction.CONTINUE,
                strategy="NORMAL",
            )

        final_result: GateResult | None = None
        for gate in profile.quality_gates:
            result = await gate.evaluate(query, chunks, context)
            final_result = result

            # CONTINUE (Grade A) → no need for further evaluation
            if result.action == GateAction.CONTINUE:
                break
            # SHORT_CIRCUIT / REFER → stop immediately
            if result.action in (GateAction.SHORT_CIRCUIT, GateAction.REFER):
                break
            # DEGRADE → continue to next gate for more precise evaluation

        return final_result
