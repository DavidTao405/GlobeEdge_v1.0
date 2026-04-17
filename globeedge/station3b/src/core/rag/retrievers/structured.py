"""PTT 結構化檢索 — 按看板/日期/推噓比查詢。"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from globeedge.station3b.src.core.rag.models import QueryFilters, ScoredChunk

logger = logging.getLogger(__name__)


class StructuredRetriever:
    """PTT 結構化檢索（SQL WHERE）。"""

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
            q = q.order_by(
                (PttArticle.push_count + PttArticle.boo_count + PttArticle.arrow_count).desc()
            )
            articles = q.limit(top_k * 2).all()

        scored = []
        for a in articles:
            total_pb = (a.push_count or 0) + (a.boo_count or 0)
            push_ratio = (a.push_count or 0) / total_pb if total_pb > 0 else 0.5
            scored.append(ScoredChunk(
                chunk_id=a.url,
                content=a.title,
                score=1.0,
                board=a.board or "",
                push_count=a.push_count or 0,
                boo_count=a.boo_count or 0,
                arrow_count=a.arrow_count or 0,
                push_boo_ratio=round(push_ratio, 3),
                author=a.author or "",
                date=str(a.created_at) if a.created_at else "",
                metadata={"topic": filters.topic},
            ))

        return scored[:top_k]
