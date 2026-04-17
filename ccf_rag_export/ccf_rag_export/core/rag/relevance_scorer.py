"""
Context Relevance Scorer (OPT-1)

Minimal Sufficiency Principle: filter N chunks to top-K
before LLM injection using a 3-dimension scoring model.

Dimensions:
  retrieval_score (50%) — original RRF/rerank score
  scenario_match  (30%) — chunk scenario vs intent scenario
  term_overlap    (20%) — bigram overlap between query and chunk
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.core.rag.models import ScoredChunk


@dataclass
class RelevanceConfig:
    """Scoring weights and top-K setting."""

    weight_retrieval: float = 0.50
    weight_scenario: float = 0.30
    weight_overlap: float = 0.20
    top_k: int = 5


def _bigrams(text: str) -> set[str]:
    tokens = re.findall(r"\w+", text.lower())
    return {f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)} if len(tokens) >= 2 else set(tokens)


def score_relevance(
    chunks: list[ScoredChunk],
    query: str,
    intent_scenario: str | None,
    config: RelevanceConfig | None = None,
) -> list[ScoredChunk]:
    """
    Score and filter chunks by context relevance.

    Returns top-K chunks sorted by composite relevance score.
    """
    if not chunks:
        return chunks

    cfg = config or RelevanceConfig()

    if len(chunks) <= cfg.top_k:
        return chunks

    # Normalize retrieval scores to [0, 1]
    max_score = max(c.score for c in chunks) or 1.0
    query_bigrams = _bigrams(query)

    scored: list[tuple[float, ScoredChunk]] = []
    for chunk in chunks:
        # Dimension 1: retrieval score (normalized)
        d_retrieval = chunk.score / max_score

        # Dimension 2: scenario match
        d_scenario = 0.0
        if intent_scenario and chunk.scenario:
            d_scenario = 1.0 if chunk.scenario == intent_scenario else 0.0

        # Dimension 3: bigram overlap
        chunk_bigrams = _bigrams(chunk.content)
        if query_bigrams and chunk_bigrams:
            d_overlap = len(query_bigrams & chunk_bigrams) / len(query_bigrams)
        else:
            d_overlap = 0.0

        composite = (
            cfg.weight_retrieval * d_retrieval
            + cfg.weight_scenario * d_scenario
            + cfg.weight_overlap * d_overlap
        )
        scored.append((composite, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[: cfg.top_k]]
