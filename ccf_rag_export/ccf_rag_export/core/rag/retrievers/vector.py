"""
Vector Retriever
向量檢索層

使用 pgvector <=> 運算子執行餘弦距離搜尋。
從 CCFHybridSearch._dense_search 提取，符合 Retriever Protocol。
"""

from __future__ import annotations

from src.core.rag.models import QueryFilters, ScoredChunk
from src.domain.entities.kb_entry import AgeGroup, Scenario
from src.domain.interfaces.providers.embedding_provider import EmbeddingProvider
from src.domain.interfaces.repositories.kb_repository import KBRepository
from src.shared.observability import get_logger

logger = get_logger(__name__)


class VectorRetriever:
    """
    pgvector cosine similarity retriever.

    Delegates to KBRepository.search_by_embedding() which uses
    the pgvector <=> operator for DB-level vector search.
    """

    def __init__(
        self,
        kb_repository: KBRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._repo = kb_repository
        self._embedding = embedding_provider

    async def retrieve(
        self,
        query: str,
        filters: QueryFilters,
        top_k: int,
    ) -> list[ScoredChunk]:
        # Generate query embedding
        query_embedding = await self._embedding.embed_query(query)

        # Map filter strings → domain enums
        scenario = Scenario(filters.scenario) if filters.scenario else None
        age_group = AgeGroup(filters.age_group) if filters.age_group else None

        # DB-level pgvector cosine search
        results = await self._repo.search_by_embedding(
            query_embedding,
            limit=top_k,
            scenario=scenario,
            age_group=age_group,
        )

        return [
            ScoredChunk(
                chunk_id=entry.id,
                content=entry.body,
                score=score,
                source="vector",
                metadata=entry.metadata,
                scenario=entry.scenario.value if entry.scenario else None,
                age_groups=[ag.value for ag in entry.age_groups],
                risk_level=entry.risk_level.value if entry.risk_level else None,
            )
            for entry, score in results
        ]
