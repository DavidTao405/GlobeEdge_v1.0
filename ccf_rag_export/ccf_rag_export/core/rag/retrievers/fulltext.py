"""
Fulltext Retriever
全文檢索層

使用 BM25 近似評分進行關鍵字搜尋。
從 CCFHybridSearch._sparse_search 提取，符合 Retriever Protocol。
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.rag.models import QueryFilters, ScoredChunk
from src.domain.entities.kb_entry import AgeGroup, KBEntryStatus, Scenario
from src.infrastructure.database.models import KBEntryModel
from src.shared.observability import get_logger

logger = get_logger(__name__)


class FullTextRetriever:
    """
    BM25 approximation fulltext retriever.

    Tokenizes query into keywords and computes a simplified BM25 score
    against title + body + keywords of KB entries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def retrieve(
        self,
        query: str,
        filters: QueryFilters,
        top_k: int,
    ) -> list[ScoredChunk]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Build query
        stmt = select(
            KBEntryModel.id,
            KBEntryModel.title,
            KBEntryModel.body,
            KBEntryModel.keywords,
            KBEntryModel.scenario,
            KBEntryModel.age_groups,
            KBEntryModel.risk_level,
            KBEntryModel.metadata_json,
        ).where(KBEntryModel.status == KBEntryStatus.APPROVED)

        if filters.scenario:
            stmt = stmt.where(KBEntryModel.scenario == Scenario(filters.scenario))
        if filters.age_group:
            stmt = stmt.where(
                KBEntryModel.age_groups.contains([filters.age_group])
            )

        result = await self._session.execute(stmt)
        rows = result.all()

        # Score each row
        scored: list[tuple[object, float]] = []
        for row in rows:
            search_text = f"{row.title} {row.body}"
            if row.keywords:
                search_text += " " + " ".join(row.keywords)
            score = self._bm25_score(query_tokens, search_text)
            if score > 0:
                scored.append((row, score))

        if not scored:
            return []

        # Normalize scores to 0-1
        max_score = max(s for _, s in scored)
        if max_score > 0:
            scored = [(row, s / max_score) for row, s in scored]

        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            ScoredChunk(
                chunk_id=row.id,
                content=row.body,
                score=score,
                source="fulltext",
                metadata=row.metadata_json or {},
                scenario=row.scenario.value if row.scenario else None,
                age_groups=list(row.age_groups) if row.age_groups else [],
                risk_level=row.risk_level.value if row.risk_level else None,
            )
            for row, score in scored[:top_k]
        ]

    def _tokenize(self, text: str) -> set[str]:
        """Simple Chinese+English tokenizer."""
        tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+|[0-9]+", text.lower())
        result: set[str] = set()
        for token in tokens:
            if re.match(r"[\u4e00-\u9fff]+", token):
                result.update(list(token))
            else:
                result.add(token)
        return result

    def _bm25_score(
        self,
        query_tokens: set[str],
        document: str,
        k1: float = 1.5,
    ) -> float:
        """Simplified BM25 score."""
        doc_tokens = self._tokenize(document)
        if not doc_tokens:
            return 0.0
        score = 0.0
        for token in query_tokens:
            if token in doc_tokens:
                tf = 1.0
                score += (tf * (k1 + 1)) / (tf + k1)
        return score
