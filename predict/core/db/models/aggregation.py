"""
Aggregation models for GDPR-safe data retention.

DailySensorSummary: Per-vehicle per-sensor per-day statistics.
  Allows 3+ year trend visibility even after raw telemetry is deleted.

PredictionOutcome: Tracks whether predictions matched actual service events.
  Used for accuracy tracking and dynamic pattern weight adjustment.
"""

from typing import Optional

from sqlalchemy import String, Integer, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class DailySensorSummary(Base):
    """Aggregated daily sensor statistics per vehicle."""
    __tablename__ = "daily_sensor_summary"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    sensor: Mapped[str] = mapped_column(String(50), nullable=False)
    min_value: Mapped[Optional[float]] = mapped_column(Float)
    max_value: Mapped[Optional[float]] = mapped_column(Float)
    avg_value: Mapped[Optional[float]] = mapped_column(Float)
    reading_count: Mapped[Optional[int]] = mapped_column(Integer)
    quality_score: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("vehicle_id", "date", "sensor", name="uq_daily_sensor"),
    )


class PredictionOutcome(Base):
    """Tracks prediction accuracy: did the prediction match a service event?"""
    __tablename__ = "prediction_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    component: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern_name: Mapped[Optional[str]] = mapped_column(String(100))
    predicted_health_pct: Mapped[Optional[float]] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # confirmed, false_positive, missed
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    service_record_id: Mapped[Optional[int]] = mapped_column(Integer)
