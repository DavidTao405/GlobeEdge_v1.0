"""PTT 全文檢索 — 用 jieba 分詞 + BM25 近似。

替代 CCF-ORG 的 regex tokenizer，用 jieba 做中文分詞。
查詢 ptt_articles 表（非 kb_entries）。
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter

from globeedge.station3b.src.core.rag.models import QueryFilters, ScoredChunk

logger = logging.getLogger(__name__)

try:
    import jieba
    jieba.setLogLevel(logging.WARNING)
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False


class FullTextRetriever:
    """PTT 全文檢索（BM25 + jieba）。"""

    def __init__(self, app_context_fn=None):
        """app_context_fn: 回傳 Flask app context 的 callable。"""
        self._app_context_fn = app_context_fn

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

            # 看板過濾
            if filters.board:
                q = q.filter(PttArticle.board == filters.board)

            # 關鍵字過濾（OR）
            if filters.keywords:
                kw_filters = [PttArticle.title.contains(kw) for kw in filters.keywords]
                q = q.filter(db.or_(*kw_filters))

            # 最少互動數
            q = q.filter(
                (PttArticle.push_count + PttArticle.boo_count) >= filters.min_interactions
            )

            articles = q.all()

        # BM25 評分
        query_tokens = self._tokenize(query)
        scored = []
        for a in articles:
            title_tokens = self._tokenize(a.title)
            score = self._bm25_score(query_tokens, title_tokens)
            if score <= 0:
                continue
            total_pb = (a.push_count or 0) + (a.boo_count or 0)
            push_ratio = (a.push_count or 0) / total_pb if total_pb > 0 else 0.5
            scored.append(ScoredChunk(
                chunk_id=a.url,
                content=a.title,
                score=score,
                board=a.board or "",
                push_count=a.push_count or 0,
                boo_count=a.boo_count or 0,
                arrow_count=a.arrow_count or 0,
                push_boo_ratio=round(push_ratio, 3),
                author=a.author or "",
                date=str(a.created_at) if a.created_at else "",
                metadata={"topic": filters.topic},
            ))

        scored.sort(key=lambda c: -c.score)
        return scored[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        if _HAS_JIEBA:
            return list(jieba.cut(text))
        return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())

    def _bm25_score(
        self, query_tokens: list[str], doc_tokens: list[str], k1: float = 1.5,
    ) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0
        doc_freq = Counter(doc_tokens)
        doc_len = len(doc_tokens)
        score = 0.0
        for qt in query_tokens:
            tf = doc_freq.get(qt, 0)
            if tf > 0:
                score += (tf * (k1 + 1)) / (tf + k1 * (doc_len / max(doc_len, 1)))
        return score
