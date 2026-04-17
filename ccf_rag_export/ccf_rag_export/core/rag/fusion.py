"""
Result Fusion — RRF (Reciprocal Rank Fusion)
結果融合

將多個 Retriever 的結果透過 RRF 融合為統一排序。
從 CCFHybridSearch._reciprocal_rank_fusion 提取。
"""

from __future__ import annotations

from collections import defaultdict

from src.core.rag.models import ScoredChunk


def rrf_fuse(
    results: list[list[ScoredChunk]],
    weights: list[float],
    k: int = 60,
) -> list[ScoredChunk]:
    """
    Reciprocal Rank Fusion.

    RRF Score = Σ weight_i / (k + rank_i)

    Args:
        results: List of ranked result lists from each retriever.
        weights: Weight for each retriever (same order as results).
        k: RRF constant (default 60).

    Returns:
        Fused and re-sorted list of ScoredChunks.
    """
    if len(results) == 1:
        return results[0]

    # Accumulate RRF scores
    scores: dict[str, float] = defaultdict(float)
    chunk_map: dict[str, ScoredChunk] = {}

    for layer_results, weight in zip(results, weights):
        for rank, chunk in enumerate(layer_results, 1):
            rrf_score = weight / (k + rank)
            scores[chunk.chunk_id] += rrf_score
            # Keep chunk with highest original score
            if chunk.chunk_id not in chunk_map or chunk.score > chunk_map[chunk.chunk_id].score:
                chunk_map[chunk.chunk_id] = chunk

    # Sort by fused score
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    # Return chunks with fused scores
    fused: list[ScoredChunk] = []
    for chunk_id in sorted_ids:
        chunk = chunk_map[chunk_id]
        # Replace score with fused score
        fused.append(
            ScoredChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=scores[chunk_id],
                source=chunk.source,
                metadata=chunk.metadata,
                scenario=chunk.scenario,
                age_groups=chunk.age_groups,
                risk_level=chunk.risk_level,
            )
        )

    return fused
