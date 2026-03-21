"""EWSAlert ORM 實體 — Early Warning Signals 警報記錄。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from worldedge.db import db


class EWSAlert(db.Model):
    __tablename__ = "ews_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_results.id"), nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    timestep: Mapped[int | None] = mapped_column(Integer)
    alert_type: Mapped[str | None] = mapped_column(String)   # lambda_max | variance | csd | convergence
    severity: Mapped[str | None] = mapped_column(String)     # low | medium | high | critical
    metric_value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    z_score: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)

    # relationships
    project = relationship("Project", back_populates="ews_alerts")
    result = relationship("SimulationResult", back_populates="ews_alerts")
