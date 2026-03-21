"""ExternalEvent ORM 實體 — 外部事件（地緣政治 / 國內 / 金融 / 天災）。"""

import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from globeedge.db import db


class ExternalEvent(db.Model):
    __tablename__ = "external_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False
    )
    domain: Mapped[str | None] = mapped_column(String)       # geopolitical | domestic | financial | natural
    source_type: Mapped[str | None] = mapped_column(String)   # ais | gdelt | usgs | adsb | news
    impact_vector: Mapped[list[float] | None] = mapped_column(ARRAY(db.Float))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_tier: Mapped[int] = mapped_column(Integer, default=2)
    gdelt_id: Mapped[str | None] = mapped_column(String)
