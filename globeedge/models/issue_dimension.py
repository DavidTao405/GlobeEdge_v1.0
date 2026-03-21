"""IssueDimension ORM 實體 — 議題維度定義。"""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from globeedge.db import db


class IssueDimension(db.Model):
    __tablename__ = "issue_dimensions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True  # NULL = 通用維度
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    range_min: Mapped[float] = mapped_column(Float, default=-1.0)
    range_max: Mapped[float] = mapped_column(Float, default=1.0)
    layer: Mapped[str] = mapped_column(String, default="universal")

    # relationships
    project = relationship("Project", back_populates="dimensions")
