"""
ShareToken — time-limited public sharing of vehicle health data.

Mechanics / family members can view a snapshot without logging in.
Token expires after 72 hours. Rate limit: 1 share per vehicle per day.
"""

import time

from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, Index
from predict.core.db.base import Base


class ShareToken(Base):
    __tablename__ = "share_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicle_profiles.profile_id", ondelete="CASCADE"),
        nullable=False,
    )
    creator_user_id = Column(Integer, nullable=False)
    # JSON snapshot of health data at creation time
    health_data = Column(Text, nullable=False)
    created_at = Column(Float, default=lambda: time.time())
    expires_at = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_share_vehicle_created", "vehicle_id", "created_at"),
    )
