"""
Vehicle profile, OBD data, and telemetry models.
Consolidates: profiles + vehicle_profiles → vehicle_profiles
              vehicle_data, obd_records, telemetry_records
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Integer, Float, Text, Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base, TimestampMixin


class VehicleProfile(TimestampMixin, Base):
    """Vehicle profile. Merges server profiles + desktop vehicle_profiles."""
    __tablename__ = "vehicle_profiles"

    profile_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    make: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    year: Mapped[Optional[int]] = mapped_column(Integer)
    vin: Mapped[Optional[str]] = mapped_column(String(17))
    license_plate: Mapped[Optional[str]] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(50), server_default="Personal")
    engine_type: Mapped[Optional[str]] = mapped_column(String(50))
    transmission: Mapped[Optional[str]] = mapped_column(String(50))
    fuel_type: Mapped[Optional[str]] = mapped_column(String(50))
    drivetrain: Mapped[Optional[str]] = mapped_column(String(50))
    color: Mapped[Optional[str]] = mapped_column(String(50))
    purchase_date: Mapped[Optional[str]] = mapped_column(String(20))
    last_service_date: Mapped[Optional[str]] = mapped_column(String(20))
    dealer_info: Mapped[Optional[str]] = mapped_column(Text)
    warranty_info: Mapped[Optional[str]] = mapped_column(Text)
    insurance_details: Mapped[Optional[str]] = mapped_column(Text)
    obd_device_mac: Mapped[Optional[str]] = mapped_column(String(17))

    __table_args__ = (
        Index("idx_vehicle_profiles_vin", "vin"),
        Index("idx_vehicle_profiles_plate", "license_plate"),
    )


class VehicleData(Base):
    """Complete OBD data payloads from Android/Desktop."""
    __tablename__ = "vehicle_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_id: Mapped[Optional[str]] = mapped_column(String(100))
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)

    # OBD Data
    rpm: Mapped[Optional[float]] = mapped_column(Float)
    speed: Mapped[Optional[float]] = mapped_column(Float)
    coolant_temp: Mapped[Optional[float]] = mapped_column(Float)
    battery_voltage: Mapped[Optional[float]] = mapped_column(Float)
    engine_load: Mapped[Optional[float]] = mapped_column(Float)
    throttle_pos: Mapped[Optional[float]] = mapped_column(Float)
    fuel_level: Mapped[Optional[float]] = mapped_column(Float)
    fuel_pressure: Mapped[Optional[float]] = mapped_column(Float)
    intake_temp: Mapped[Optional[float]] = mapped_column(Float)
    maf_rate: Mapped[Optional[float]] = mapped_column(Float)
    oil_temp: Mapped[Optional[float]] = mapped_column(Float)
    short_term_fuel_trim: Mapped[Optional[float]] = mapped_column(Float)
    long_term_fuel_trim: Mapped[Optional[float]] = mapped_column(Float)
    timing_advance: Mapped[Optional[float]] = mapped_column(Float)

    # GPS Data
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)

    # Vibration/Accelerometer
    acceleration_x: Mapped[Optional[float]] = mapped_column(Float)
    acceleration_y: Mapped[Optional[float]] = mapped_column(Float)
    acceleration_z: Mapped[Optional[float]] = mapped_column(Float)
    vibration_rms: Mapped[Optional[float]] = mapped_column(Float)
    vibration_peak: Mapped[Optional[float]] = mapped_column(Float)
    vibration_crest_factor: Mapped[Optional[float]] = mapped_column(Float)

    # Metadata
    source: Mapped[Optional[str]] = mapped_column(String(20))
    raw_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        Index("idx_vehicle_data_profile_ts", "profile_id", "timestamp"),
        Index("idx_vehicle_data_timestamp", "timestamp"),
    )


class OBDRecord(Base):
    """Individual OBD PID readings."""
    __tablename__ = "obd_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(100))
    ts: Mapped[Optional[float]] = mapped_column(Float)
    pid: Mapped[Optional[str]] = mapped_column(String(10))
    name: Mapped[Optional[str]] = mapped_column(String(100))
    value: Mapped[Optional[float]] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(20))


class TelemetryRecord(Base):
    """Telemetry snapshots with VIN and mileage."""
    __tablename__ = "telemetry_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(100))
    ts: Mapped[Optional[float]] = mapped_column(Float)
    vin: Mapped[Optional[str]] = mapped_column(String(17))
    mileage_km: Mapped[Optional[float]] = mapped_column(Float)
    fuel_level: Mapped[Optional[float]] = mapped_column(Float)
    raw_json: Mapped[Optional[str]] = mapped_column(Text)


class ServiceRecord(Base):
    """Vehicle service/maintenance history."""
    __tablename__ = "service_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    component_type: Mapped[str] = mapped_column(String(100), nullable=False)
    service_date: Mapped[str] = mapped_column(String(20), nullable=False)
    service_km: Mapped[int] = mapped_column(Integer, nullable=False)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    part_brand: Mapped[Optional[str]] = mapped_column(String(100))
    part_spec: Mapped[Optional[str]] = mapped_column(String(255))
    expected_lifespan_km: Mapped[Optional[int]] = mapped_column(Integer)
    expected_lifespan_months: Mapped[Optional[int]] = mapped_column(Integer)
    actual_usage_km: Mapped[Optional[int]] = mapped_column(Integer)
    actual_usage_months: Mapped[Optional[int]] = mapped_column(Integer)
    condition_at_replacement: Mapped[Optional[str]] = mapped_column(String(50))
    cost: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    technician: Mapped[Optional[str]] = mapped_column(String(100))
    confirmed_fix: Mapped[bool] = mapped_column(Integer, server_default="0")
    resolution_status: Mapped[Optional[str]] = mapped_column(String(50))
    synced_from: Mapped[str] = mapped_column(String(20), server_default="desktop")
    created_at: Mapped[Optional[str]] = mapped_column(String(30))
    updated_at: Mapped[Optional[str]] = mapped_column(String(30))

    __table_args__ = (
        Index("idx_service_records_profile", "profile_id"),
        Index("idx_service_records_date", "profile_id", "service_date"),
    )
