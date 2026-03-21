"""Agent ORM 實體。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from globeedge.db import db


class Agent(db.Model):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str | None] = mapped_column(String)    # media | forum | kol | demographic | institution
    domain: Mapped[str | None] = mapped_column(String)  # news | social | financial | government
    belief_init: Mapped[list[float] | None] = mapped_column(ARRAY(db.Float))
    issue_involvement: Mapped[float] = mapped_column(Float, default=0.5)  # ELM: 0=不關心, 1=核心關切
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # relationships
    project = relationship("Project", back_populates="agents")
