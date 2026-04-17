"""PTT 向量檢索 — 用 Ollama embedding + cosine similarity。

不用 pgvector，直接在記憶體中算 cosine similarity。
適合 < 10K 文章的場景。
"""

from __future__ import annotations

import logging
import re

import numpy as np

from globeedge.station3b.src.core.rag.models import QueryFilters, ScoredChunk

logger = logging.getLogger(__name__)

try:
    import httpx
    _OLLAMA_EMBED = "http://localhost:11434/api/embed"
    _EMBED_MODEL = "rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest"
except ImportError:
    httpx = None


def _get_embedding(text: str) -> np.ndarray:
    if httpx is None:
        return np.zeros(1536)
    try:
        r = httpx.post(_OLLAMA_EMBED, json={
            "model": _EMBED_MODEL, "input": text[:500],
        }, timeout=30)
        r.raise_for_status()
        embs = r.json().get("embeddings", [])
        if embs:
            return np.array(embs[0])
    except Exception:
        pass
    return np.zeros(1536)


class VectorRetriever:
    """PTT 向量檢索（Ollama embedding + in-memory cosine）。"""

    def retrieve(
        self, query: str, filters: QueryFilters | None = None, top_k: int = 10,
    ) -> list[ScoredChunk]:
        from globeedge.app import create_app
        from globeedge.db import db
        from globeedge.models import PttArticle

        if filters is None:
            filters = QueryFilters()

        app = create_app()
        with app.app_context():
            q = PttArticle.query
            if filters.board:
                q = q.filter(PttArticle.board == filters.board)
            if filters.keywords:
                kw_filters = [PttArticle.title.contains(kw) for kw in filters.keywords]
                q = q.filter(db.or_(*kw_filters))
            q = q.filter(
                (PttArticle.push_count + PttArticle.boo_count) >= filters.min_interactions
            )
            articles = q.limit(200).all()

        if not articles:
            return []

        # Embedding
        query_vec = _get_embedding(query)
        scored = []
        for a in articles:
            title_vec = _get_embedding(a.title)
            sim = _cosine(query_vec, title_vec)
            total_pb = (a.push_count or 0) + (a.boo_count or 0)
            push_ratio = (a.push_count or 0) / total_pb if total_pb > 0 else 0.5
            scored.append(ScoredChunk(
                chunk_id=a.url,
                content=a.title,
                score=float(sim),
                board=a.board or "",
                push_count=a.push_count or 0,
                boo_count=a.boo_count or 0,
                arrow_count=a.arrow_count or 0,
                push_boo_ratio=round(push_ratio, 3),
                metadata={"topic": filters.topic},
            ))

        scored.sort(key=lambda c: -c.score)
        return scored[:top_k]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
