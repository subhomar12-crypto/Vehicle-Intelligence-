"""
PID Atlas — Community-driven manufacturer PID database.

Stores Service 21/22 PIDs discovered by users, keyed by make/model.
PREDICT team curates names/units/formulas over time.
"""

import time
from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base, TimestampMixin


class PIDAtlas(TimestampMixin, Base):
    """A single manufacturer PID entry in the community atlas."""

    __tablename__ = "pid_atlas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Vehicle identification (normalized uppercase)
    make: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    year_min: Mapped[int] = mapped_column(Integer, nullable=False, default=1990)
    year_max: Mapped[int] = mapped_column(Integer, nullable=False, default=2030)

    # PID identification
    service: Mapped[int] = mapped_column(Integer, nullable=False)           # 0x21 or 0x22
    pid_hex: Mapped[str] = mapped_column(String(8), nullable=False)         # "05" or "F190"
    ecu_address: Mapped[str] = mapped_column(String(8), nullable=False, default="")

    # Discovery metadata
    data_byte_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_dynamic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    semantic_type: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    discovery_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sample_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # PREDICT team curation (null until labeled)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    formula: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    first_discovered_at: Mapped[float] = mapped_column(Float, default=time.time, nullable=False)
    last_seen_at: Mapped[float] = mapped_column(Float, default=time.time, nullable=False)

    __table_args__ = (
        UniqueConstraint("make", "model", "service", "pid_hex", "ecu_address", name="uq_pid_atlas_entry"),
        Index("idx_pid_atlas_make_model", "make", "model"),
    )
