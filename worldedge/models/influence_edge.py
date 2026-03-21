"""InfluenceEdge ORM 實體 — W 矩陣的邊。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from worldedge.db import db


class InfluenceEdge(db.Model):
    __tablename__ = "influence_edges"
    __table_args__ = (
        # 部分索引：只索引目前有效的邊 (valid_until IS NULL)
        Index(
            "idx_edges_valid",
            "project_id",
            "valid_until",
            postgresql_where=db.text("valid_until IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    weight_type: Mapped[str | None] = mapped_column(String)  # structural | behavioral | semantic
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    valid_from: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        db.DateTime(timezone=True), nullable=True
    )
    decay_rate: Mapped[float] = mapped_column(Float, default=0.1)

    # relationships
    project = relationship("Project", back_populates="edges")
    source = relationship("Agent", foreign_keys=[source_id])
    target = relationship("Agent", foreign_keys=[target_id])
