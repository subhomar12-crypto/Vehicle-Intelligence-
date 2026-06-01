"""
Guardian system models: parents, fleet managers, monitoring.
Tables: guardians, vehicle_guardians, alerts, guardian_commands,
        location_requests, consent_records, guardian_telemetry,
        driving_events
"""

from typing import Optional

from sqlalchemy import (
    String, Integer, Float, Boolean, Text, ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class Guardian(Base):
    """Guardian accounts (parents, fleet managers)."""
    __tablename__ = "guardians"

    id: Mapped[int] = mapped_column(primary_key=True)
    guardian_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(5), server_default="en")
    fcm_token: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_login: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class VehicleGuardian(Base):
    """Links vehicles to guardians (many-to-many)."""
    __tablename__ = "vehicle_guardians"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guardian_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # Legacy, kept for existing data
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NEW: links to User.id for unified auth
    relationship: Mapped[Optional[str]] = mapped_column(String(50))
    permissions: Mapped[str] = mapped_column(String(20), server_default="full")
    role: Mapped[str] = mapped_column(String(20), server_default="driver")
    linked_at: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        UniqueConstraint("profile_id", "guardian_id", name="uq_vehicle_guardian"),
    )


class Alert(Base):
    """Guardian alerts (speeding, geofence, health, etc.)."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    data_json: Mapped[Optional[str]] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, server_default="false")

    __table_args__ = (
        Index("idx_alerts_profile", "profile_id"),
        Index("idx_alerts_type", "alert_type"),
    )


class GuardianCommand(Base):
    """Commands sent from guardian to driver/vehicle."""
    __tablename__ = "guardian_commands"

    id: Mapped[int] = mapped_column(primary_key=True)
    guardian_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Legacy
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NEW: links to User.id
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    command_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), server_default="normal")
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    sent_at: Mapped[Optional[float]] = mapped_column(Float)
    delivered_at: Mapped[Optional[float]] = mapped_column(Float)
    acknowledged_at: Mapped[Optional[float]] = mapped_column(Float)
    completed_at: Mapped[Optional[float]] = mapped_column(Float)
    expires_at: Mapped[Optional[float]] = mapped_column(Float)
    response: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0")

    __table_args__ = (
        Index("idx_guardian_commands_profile", "profile_id", "status"),
    )


class LocationRequest(Base):
    """Emergency location requests from guardian."""
    __tablename__ = "location_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    guardian_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # Legacy
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NEW: links to User.id
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    requested_at: Mapped[float] = mapped_column(Float, nullable=False)
    fulfilled_at: Mapped[Optional[float]] = mapped_column(Float)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    accuracy: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")


class ConsentRecord(Base):
    """Driver consent for guardian monitoring."""
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guardian_id: Mapped[int] = mapped_column(Integer, nullable=False)
    consent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, server_default="true")
    granted_at: Mapped[Optional[float]] = mapped_column(Float)
    revoked_at: Mapped[Optional[float]] = mapped_column(Float)
    revoked_reason: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("profile_id", "guardian_id", "consent_type",
                         name="uq_consent_record"),
    )


class GuardianTelemetry(Base):
    """Real-time location/telemetry from guardian-monitored vehicles."""
    __tablename__ = "guardian_telemetry"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    speed: Mapped[Optional[float]] = mapped_column(Float)
    heading: Mapped[Optional[float]] = mapped_column(Float)
    accuracy: Mapped[Optional[float]] = mapped_column(Float)
    altitude: Mapped[Optional[float]] = mapped_column(Float)
    is_driving: Mapped[bool] = mapped_column(Boolean, server_default="false")
    battery_level: Mapped[Optional[float]] = mapped_column(Float)
    signal_strength: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("idx_guardian_telemetry_profile_ts", "profile_id", "timestamp"),
    )


class DrivingEvent(Base):
    """Driving behavior events (harsh braking, speeding, etc.)."""
    __tablename__ = "driving_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    value: Mapped[Optional[float]] = mapped_column(Float)
    threshold: Mapped[Optional[float]] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(20), server_default="low")
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    speed_limit: Mapped[Optional[float]] = mapped_column(Float)
    details: Mapped[Optional[str]] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, server_default="false")
    acknowledged_at: Mapped[Optional[float]] = mapped_column(Float)
    acknowledged_by: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("idx_driving_events_profile_ts", "profile_id", "timestamp"),
        Index("idx_driving_events_type", "event_type"),
    )
