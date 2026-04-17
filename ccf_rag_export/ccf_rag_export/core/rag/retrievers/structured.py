"""
Structured Retriever
結構化檢索層

使用 SQL WHERE + tsvector 進行情境/年齡/關鍵字精確匹配。
從 StructuredRetrievalService 提取，符合 Retriever Protocol。
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.rag.models import QueryFilters, ScoredChunk
from src.domain.entities.kb_entry import KBEntryStatus, Scenario
from src.infrastructure.database.models import KBEntryModel
from src.shared.observability import get_logger

logger = get_logger(__name__)


class StructuredRetriever:
    """
    SQL-first structured retriever.

    Primary path: scenario + age_group WHERE clause.
    Fallback: tsvector fulltext → ILIKE if tsvector fails.
    Score is based on filter precision (1.0 for exact, 0.7 for fallback).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def retrieve(
        self,
        query: str,
        filters: QueryFilters,
        top_k: int,
    ) -> list[ScoredChunk]:
        # Primary: structured SQL search
        results = await self._structured_search(filters, top_k * 2)

        # Fallback: if results too few and keywords available
        if len(results) < 3 and filters.keywords:
            fallback = await self._keyword_fallback(filters.keywords, top_k)
            # Merge and dedupe, primary results first
            seen = {r.chunk_id for r in results}
            for chunk in fallback:
                if chunk.chunk_id not in seen:
                    results.append(chunk)
                    seen.add(chunk.chunk_id)

        return results[:top_k]

    async def _structured_search(
        self,
        filters: QueryFilters,
        limit: int,
    ) -> list[ScoredChunk]:
        stmt = select(KBEntryModel).where(
            KBEntryModel.status == KBEntryStatus.APPROVED
        )

        if filters.scenario:
            stmt = stmt.where(KBEntryModel.scenario == Scenario(filters.scenario))
        if filters.age_group:
            stmt = stmt.where(
                KBEntryModel.age_groups.contains([filters.age_group])
            )

        stmt = stmt.order_by(KBEntryModel.updated_at.desc()).limit(limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [
            ScoredChunk(
                chunk_id=m.id,
                content=m.body,
                score=1.0,  # Exact structural match
                source="structured",
                metadata=m.metadata_json or {},
                scenario=m.scenario.value if m.scenario else None,
                age_groups=[ag for ag in m.age_groups] if m.age_groups else [],
                risk_level=m.risk_level.value if m.risk_level else None,
            )
            for m in models
        ]

    async def _keyword_fallback(
        self,
        keywords: list[str],
        limit: int,
    ) -> list[ScoredChunk]:
        """Fallback: tsvector → ILIKE."""
        if not keywords:
            return []

        # Try tsvector first
        try:
            stmt = (
                select(KBEntryModel)
                .where(KBEntryModel.status == KBEntryStatus.APPROVED)
                .where(
                    func.to_tsvector("simple", KBEntryModel.body).op("@@")(
                        func.plainto_tsquery("simple", " ".join(keywords))
                    )
                )
                .order_by(KBEntryModel.updated_at.desc())
                .limit(limit)
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()
        except Exception:
            # tsvector failed, fall back to ILIKE
            like_conditions = []
            for kw in keywords:
                like_conditions.append(KBEntryModel.body.ilike(f"%{kw}%"))
                like_conditions.append(KBEntryModel.title.ilike(f"%{kw}%"))

            stmt = (
                select(KBEntryModel)
                .where(KBEntryModel.status == KBEntryStatus.APPROVED)
                .where(or_(*like_conditions))
                .order_by(KBEntryModel.updated_at.desc())
                .limit(limit)
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()

        return [
            ScoredChunk(
                chunk_id=m.id,
                content=m.body,
                score=0.7,  # Fallback match
                source="structured",
                metadata=m.metadata_json or {},
                scenario=m.scenario.value if m.scenario else None,
                age_groups=[ag for ag in m.age_groups] if m.age_groups else [],
                risk_level=m.risk_level.value if m.risk_level else None,
            )
            for m in models
        ]
