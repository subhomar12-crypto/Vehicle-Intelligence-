"""
DTC (Diagnostic Trouble Code) models.
Tables: dtc_codes, dtc_history
"""

from typing import Optional

from sqlalchemy import String, Integer, Float, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class DTCCode(Base):
    """Active/stored DTC codes per vehicle."""
    __tablename__ = "dtc_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20), server_default="info")
    is_pending: Mapped[bool] = mapped_column(Integer, server_default="0")
    first_seen: Mapped[float] = mapped_column(Float, nullable=False)
    last_seen: Mapped[float] = mapped_column(Float, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, server_default="1")
    is_active: Mapped[bool] = mapped_column(Integer, server_default="1")
    cleared_at: Mapped[Optional[float]] = mapped_column(Float)
    freeze_frame_json: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("profile_id", "code", "is_pending", name="uq_dtc_profile_code"),
        Index("idx_dtc_codes_profile_active", "profile_id", "is_active"),
    )


class DTCHistory(Base):
    """DTC event log (detected, cleared, etc.)."""
    __tablename__ = "dtc_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    mileage_km: Mapped[Optional[float]] = mapped_column(Float)
    details_json: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_dtc_history_profile_ts", "profile_id", "timestamp"),
    )
