"""Project ORM 實體。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from globeedge.db import db


class Project(db.Model):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    alpha: Mapped[float] = mapped_column(Float, default=0.6)
    mc_runs: Mapped[int] = mapped_column(Integer, default=10_000)
    noise_level: Mapped[float] = mapped_column(Float, default=0.05)
    sim_horizon: Mapped[int] = mapped_column(Integer, default=30)
    time_step: Mapped[str] = mapped_column(String, default="day")
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # relationships
    agents = relationship("Agent", back_populates="project", cascade="all, delete-orphan")
    edges = relationship("InfluenceEdge", back_populates="project", cascade="all, delete-orphan")
    dimensions = relationship("IssueDimension", back_populates="project", cascade="all, delete-orphan")
    simulation_results = relationship("SimulationResult", back_populates="project", cascade="all, delete-orphan")
    ews_alerts = relationship("EWSAlert", back_populates="project", cascade="all, delete-orphan")
