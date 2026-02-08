"""
Trip and driver models.
Tables: trips, trip_events, drivers, vehicle_drivers, driver_sessions,
        driver_invite_codes, driver_behavior_summary, guardian_trips
"""

from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class Trip(Base):
    """Aggregated trip data."""
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[Optional[float]] = mapped_column(Float)
    start_lat: Mapped[Optional[float]] = mapped_column(Float)
    start_lng: Mapped[Optional[float]] = mapped_column(Float)
    end_lat: Mapped[Optional[float]] = mapped_column(Float)
    end_lng: Mapped[Optional[float]] = mapped_column(Float)
    distance_km: Mapped[Optional[float]] = mapped_column(Float)
    duration_minutes: Mapped[Optional[float]] = mapped_column(Float)
    avg_speed: Mapped[Optional[float]] = mapped_column(Float)
    max_speed: Mapped[Optional[float]] = mapped_column(Float)
    violations_count: Mapped[int] = mapped_column(Integer, server_default="0")
    safety_score: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default="active")

    __table_args__ = (
        Index("idx_trips_profile", "profile_id"),
    )


class TripEvent(Base):
    """Individual trip events (speeding, harsh braking, etc.)."""
    __tablename__ = "trip_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    trip_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    speed: Mapped[Optional[float]] = mapped_column(Float)
    data_json: Mapped[Optional[str]] = mapped_column(Text)


class Driver(Base):
    """Driver profiles."""
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer)
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    license_number: Mapped[Optional[str]] = mapped_column(String(50))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    tier: Mapped[str] = mapped_column(String(20), server_default="free")
    owner_id: Mapped[Optional[int]] = mapped_column(Integer)
    is_owner_driver: Mapped[bool] = mapped_column(Integer, server_default="0")
    invite_code_used: Mapped[Optional[str]] = mapped_column(String(50))
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        Index("idx_drivers_owner", "owner_id"),
    )


class VehicleDriver(Base):
    """Vehicle-driver many-to-many link."""
    __tablename__ = "vehicle_drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    driver_id: Mapped[str] = mapped_column(String(36), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Integer, server_default="0")
    relationship: Mapped[Optional[str]] = mapped_column(String(50))
    added_at: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        UniqueConstraint("profile_id", "driver_id", name="uq_vehicle_driver"),
    )


class DriverSession(Base):
    """Track who was driving when."""
    __tablename__ = "driver_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    driver_id: Mapped[str] = mapped_column(String(36), nullable=False)
    started_at: Mapped[float] = mapped_column(Float, nullable=False)
    ended_at: Mapped[Optional[float]] = mapped_column(Float)
    distance_km: Mapped[Optional[float]] = mapped_column(Float)
    violations_count: Mapped[int] = mapped_column(Integer, server_default="0")
    safety_score: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default="active")


class DriverInviteCode(Base):
    """Invite codes for drivers to join an owner's fleet."""
    __tablename__ = "driver_invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    used_at: Mapped[Optional[float]] = mapped_column(Float)
    used_by_driver_id: Mapped[Optional[str]] = mapped_column(String(36))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        Index("idx_invite_codes_code", "invite_code"),
        Index("idx_invite_codes_owner", "owner_id"),
    )


class DriverBehaviorSummary(Base):
    """Aggregated driver behavior statistics."""
    __tablename__ = "driver_behavior_summary"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[float] = mapped_column(Float, nullable=False)
    period_end: Mapped[float] = mapped_column(Float, nullable=False)
    total_trips: Mapped[int] = mapped_column(Integer, server_default="0")
    total_distance_km: Mapped[Optional[float]] = mapped_column(Float)
    total_duration_minutes: Mapped[Optional[float]] = mapped_column(Float)
    avg_speed: Mapped[Optional[float]] = mapped_column(Float)
    max_speed: Mapped[Optional[float]] = mapped_column(Float)
    speeding_events: Mapped[int] = mapped_column(Integer, server_default="0")
    harsh_braking_events: Mapped[int] = mapped_column(Integer, server_default="0")
    harsh_accel_events: Mapped[int] = mapped_column(Integer, server_default="0")
    safety_score: Mapped[Optional[int]] = mapped_column(Integer)
    last_updated: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("driver_id", "profile_id", "period_start",
                         name="uq_behavior_summary"),
        Index("idx_behavior_driver", "driver_id"),
    )


class GuardianTrip(Base):
    """Guardian mode trip tracking (more detailed than basic trips)."""
    __tablename__ = "guardian_trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    trip_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[Optional[float]] = mapped_column(Float)
    start_latitude: Mapped[Optional[float]] = mapped_column(Float)
    start_longitude: Mapped[Optional[float]] = mapped_column(Float)
    start_address: Mapped[Optional[str]] = mapped_column(Text)
    end_latitude: Mapped[Optional[float]] = mapped_column(Float)
    end_longitude: Mapped[Optional[float]] = mapped_column(Float)
    end_address: Mapped[Optional[str]] = mapped_column(Text)
    distance_km: Mapped[Optional[float]] = mapped_column(Float)
    duration_minutes: Mapped[Optional[float]] = mapped_column(Float)
    avg_speed: Mapped[Optional[float]] = mapped_column(Float)
    max_speed: Mapped[Optional[float]] = mapped_column(Float)
    fuel_used: Mapped[Optional[float]] = mapped_column(Float)
    idle_time_minutes: Mapped[Optional[float]] = mapped_column(Float)
    hard_brakes: Mapped[int] = mapped_column(Integer, server_default="0")
    rapid_accels: Mapped[int] = mapped_column(Integer, server_default="0")
    speeding_incidents: Mapped[int] = mapped_column(Integer, server_default="0")
    score: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("idx_guardian_trips_profile", "profile_id"),
    )
