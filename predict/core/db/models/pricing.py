"""
Parts and service pricing models for Qatar market.

Prices come from three sources:
  - admin:             manually entered by fleet/desktop admin
  - web_search:        LLM-driven web scraping (Taiseer, Woqood, etc.)
  - mechanic_feedback: reported by drivers when logging service records

Used by the cold-start prediction engine to attach real QAR cost
estimates to maintenance recommendations.
"""

from typing import Optional

from sqlalchemy import (
    Boolean, Date, Float, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base, TimestampMixin


class PartsPrice(TimestampMixin, Base):
    """Individual auto part price record (Qatar market)."""
    __tablename__ = "parts_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'oil', 'filter', 'brake_pad', 'spark_plug', 'battery', 'coolant', etc.
    component_id: Mapped[Optional[str]] = mapped_column(String(50))
    # Maps to COMPONENT_IDS: engine_oil, battery, brakes, spark_plugs, etc.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # e.g. 'Mobil 1 5W-30 Full Synthetic 4L'
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    # 'Mobil', 'Castrol', 'Toyota Genuine'
    part_number: Mapped[Optional[str]] = mapped_column(String(100))
    # OEM or aftermarket part number

    # Vehicle fitment (nullable = universal / any vehicle)
    vehicle_make: Mapped[Optional[str]] = mapped_column(String(50))
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(50))
    year_min: Mapped[Optional[int]] = mapped_column(Integer)
    year_max: Mapped[Optional[int]] = mapped_column(Integer)

    # Pricing
    price_qar: Mapped[float] = mapped_column(Float, nullable=False)
    price_type: Mapped[str] = mapped_column(String(20), server_default="retail")
    # 'retail', 'wholesale', 'service_included'

    # Source tracking
    supplier: Mapped[Optional[str]] = mapped_column(String(200))
    # 'Taiseer Auto Parts', 'Woqood', 'AutoZone Qatar'
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'admin', 'web_search', 'mechanic_feedback'
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(Float, server_default="1.0")
    # 1.0 admin, 0.7 web_search, 0.9 mechanic_feedback
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")

    price_date: Mapped[str] = mapped_column(Date, nullable=False)
    # When the price was observed / entered

    __table_args__ = (
        UniqueConstraint(
            "category", "name", "supplier", "vehicle_make", "vehicle_model",
            name="uq_parts_price",
        ),
        Index("idx_parts_component", "component_id"),
        Index("idx_parts_vehicle", "vehicle_make", "vehicle_model"),
    )


class ServicePrice(TimestampMixin, Base):
    """Service / labor price record (Qatar market)."""
    __tablename__ = "service_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # 'oil_change', 'brake_replacement', 'battery_replacement', etc.
    component_id: Mapped[Optional[str]] = mapped_column(String(50))
    # Maps to COMPONENT_IDS
    description: Mapped[Optional[str]] = mapped_column(String(500))

    # Cost breakdown
    labor_qar: Mapped[Optional[float]] = mapped_column(Float)
    parts_qar: Mapped[Optional[float]] = mapped_column(Float)
    total_qar: Mapped[float] = mapped_column(Float, nullable=False)

    # Vehicle fitment
    vehicle_make: Mapped[Optional[str]] = mapped_column(String(50))
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(50))
    year_min: Mapped[Optional[int]] = mapped_column(Integer)
    year_max: Mapped[Optional[int]] = mapped_column(Integer)

    # Provider info
    provider: Mapped[Optional[str]] = mapped_column(String(200))
    # 'Taiseer Service Center', 'Petromin Express'
    location: Mapped[Optional[str]] = mapped_column(String(200))
    # 'Al Wakra', 'Doha Industrial Area'

    # Source tracking
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(Float, server_default="1.0")
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")

    price_date: Mapped[str] = mapped_column(Date, nullable=False)

    __table_args__ = (
        Index("idx_service_component", "component_id"),
        Index("idx_service_vehicle", "vehicle_make", "vehicle_model"),
    )
