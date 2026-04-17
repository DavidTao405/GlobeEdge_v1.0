"""PttArticle ORM 實體 — PTT 文章原始資料 + 立場標記。

用途：
  - 真實資料驗證的 ground truth
  - calibrate_psychology.py 的立場時間序列
  - predictive_validation.py 的即時 PTT 資料
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from globeedge.db import db


class PttArticle(db.Model):
    __tablename__ = "ptt_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    board: Mapped[str] = mapped_column(String, nullable=False)       # Gossiping | HatePolitics | ...
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    author: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    date_str: Mapped[str | None] = mapped_column(String)             # PTT 原始日期字串
    push_count: Mapped[int] = mapped_column(Integer, default=0)
    boo_count: Mapped[int] = mapped_column(Integer, default=0)
    arrow_count: Mapped[int] = mapped_column(Integer, default=0)
    net_score: Mapped[int] = mapped_column(Integer, default=0)       # push - boo

    # 立場標記（由 Qwen3.5 標記，初始為 None）
    stance_score: Mapped[float | None] = mapped_column(Float)        # -1.0 到 1.0
    stance_topic: Mapped[str | None] = mapped_column(String)         # 標記時的議題
    stance_tagged: Mapped[bool] = mapped_column(Boolean, default=False)

    # 情緒性（由 message_analyzer 標記）
    emotionality: Mapped[float | None] = mapped_column(Float)        # 0.0 到 1.0

    # 文章內文 + 推文串（backfill_content.py 補抓）
    content: Mapped[str | None] = mapped_column(Text)                # 文章本文
    push_comments: Mapped[dict | None] = mapped_column(JSONB)        # [{type, author, content, time}]
    content_crawled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
