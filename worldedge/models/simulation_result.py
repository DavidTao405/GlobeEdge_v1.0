"""SimulationResult ORM 實體。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from worldedge.db import db


class SimulationResult(db.Model):
    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    run_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | running | done | failed
    mc_runs_actual: Mapped[int | None] = mapped_column(Integer)
    timesteps: Mapped[dict | None] = mapped_column(JSONB)
    elapsed_sec: Mapped[float | None] = mapped_column(Float)
    audit_log_id: Mapped[str | None] = mapped_column(String)

    # relationships
    project = relationship("Project", back_populates="simulation_results")
    ews_alerts = relationship("EWSAlert", back_populates="result", cascade="all, delete-orphan")
