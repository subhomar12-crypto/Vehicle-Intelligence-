"""
HealthSnapshot — periodic health assessment snapshots for trend charts.

Max 1 snapshot per vehicle per 6 hours. 365-day retention.
"""

import time

from sqlalchemy import Column, Integer, Float, String, Text, Index, ForeignKey
from predict.core.db.base import Base


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicle_profiles.profile_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    health_score = Column(Integer, nullable=False, default=0)
    # JSON dict of {component_id: score} e.g. {"engine_oil": 85, "battery": 72}
    components = Column(Text, nullable=True)
    intelligence_level = Column(String(20), default="basic")
    anomaly_count = Column(Integer, default=0)
    pattern_count = Column(Integer, default=0)
    created_at = Column(Float, default=lambda: time.time())

    __table_args__ = (
        Index("ix_health_snap_vehicle_date", "vehicle_id", "created_at"),
    )
