"""
Vehicle profile, OBD data, and telemetry models.
Consolidates: profiles + vehicle_profiles → vehicle_profiles
              vehicle_data, obd_records, telemetry_records
"""

from typing import Optional

from sqlalchemy import (
    Boolean, LargeBinary, String, Integer, Float, Text, ForeignKey, Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base, TimestampMixin


def _try_encrypt(value: Optional[str]) -> Optional[str]:
    """Encrypt *value* if FIELD_ENCRYPTION_KEY is configured; otherwise return as-is.

    This graceful fallback prevents hard crashes on systems that haven't yet
    configured the encryption key (e.g. development setups without a .env).
    Production systems SHOULD always configure the key.
    """
    if value is None:
        return None
    try:
        from predict.core.security.encryption import encrypt_field
        return encrypt_field(value)
    except RuntimeError:
        # Key not configured — store plaintext (warns in logs via encryption.py)
        return value


def _try_decrypt(value: Optional[str]) -> Optional[str]:
    """Decrypt *value* if it looks like AES-GCM output; otherwise return as-is.

    This allows gradual migration: plaintext rows written before encryption was
    enabled continue to be readable without a migration step.
    """
    if value is None:
        return None
    # Heuristic: AES-GCM blobs are always longer than 40 chars when base64-encoded
    # and don't look like a raw 17-char VIN or short phone number.
    if len(value) <= 30:
        # Likely plaintext (e.g., a 17-char VIN or short phone)
        return value
    try:
        from predict.core.security.encryption import decrypt_field
        return decrypt_field(value)
    except Exception:
        # Decryption failed — value was probably already plaintext
        return value


class VehicleProfile(TimestampMixin, Base):
    """Vehicle profile. Merges server profiles + desktop vehicle_profiles.

    VIN field encryption
    --------------------
    The VIN is stored AES-256-GCM encrypted in the ``vin`` database column.
    Access via the ``vin`` Python property which transparently encrypts on write
    and decrypts on read.  A stable HMAC-SHA256 hash is stored in ``vin_hash``
    to allow exact-match DB lookups without exposing plaintext.
    """
    __tablename__ = "vehicle_profiles"

    profile_id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(255))
    make: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    year: Mapped[Optional[int]] = mapped_column(Integer)

    # Encrypted VIN — stored in the existing "vin" column; Python attribute renamed
    # to _vin_encrypted so that direct assignment is controlled via the property below.
    _vin_encrypted: Mapped[Optional[str]] = mapped_column("vin", String(512))

    # Stable HMAC-SHA256 hash for indexed equality searches (WHERE vin_hash = ?)
    vin_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)

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
    displacement: Mapped[Optional[str]] = mapped_column(String(10))  # e.g., "3.5L"
    cylinders: Mapped[Optional[int]] = mapped_column(Integer)  # e.g., 6

    # Last known location (saved on OBD disconnect)
    last_latitude: Mapped[Optional[float]] = mapped_column(Float)
    last_longitude: Mapped[Optional[float]] = mapped_column(Float)
    last_location_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    last_location_at: Mapped[Optional[float]] = mapped_column(Float)  # Unix timestamp

    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ECU info from OBD Mode 09
    calibration_id: Mapped[Optional[str]] = mapped_column(String(50))
    ecu_name: Mapped[Optional[str]] = mapped_column(String(100))
    cvn: Mapped[Optional[str]] = mapped_column(String(50))

    # Mileage + component age tracking (Intelligence Engine v2)
    mileage_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    component_ages = mapped_column(JSONB, nullable=True)  # {"battery": {"replaced_date": "2025-06-15", "replaced_km": 180000}, ...}

    # Persisted AI health explanation — one LLM call serves both OBD + Guardian
    last_explain_json: Mapped[Optional[str]] = mapped_column(Text)
    last_explain_at: Mapped[Optional[float]] = mapped_column(Float)  # Unix timestamp

    __table_args__ = (
        # Index on vin_hash replaces the plaintext vin index for lookups
        Index("idx_vehicle_profiles_vin_hash", "vin_hash"),
        Index("idx_vehicle_profiles_plate", "license_plate"),
    )

    # ------------------------------------------------------------------
    # VIN property — encrypts on write, decrypts on read
    # ------------------------------------------------------------------

    @property
    def vin(self) -> Optional[str]:
        """Return the decrypted VIN (or plaintext if key not configured)."""
        return _try_decrypt(self._vin_encrypted)

    @vin.setter
    def vin(self, value: Optional[str]) -> None:
        """Encrypt and store the VIN; also update the searchable hash."""
        if value is None:
            self._vin_encrypted = None
            self.vin_hash = None
            return
        self._vin_encrypted = _try_encrypt(value)
        try:
            from predict.core.security.encryption import hash_field
            self.vin_hash = hash_field(value)
        except RuntimeError:
            self.vin_hash = None


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

    # Odometer (km, sent from Android OdometerTracker)
    odometer: Mapped[Optional[float]] = mapped_column(Float)

    # Extended PIDs — populated when vehicle ECU supports them
    ambient_temp: Mapped[Optional[float]] = mapped_column(Float)
    boost_pressure: Mapped[Optional[float]] = mapped_column(Float)
    fuel_rate: Mapped[Optional[float]] = mapped_column(Float)
    torque: Mapped[Optional[float]] = mapped_column(Float)
    obd_odometer: Mapped[Optional[float]] = mapped_column(Float)

    # Additional extended PIDs for AI training
    intake_manifold_pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baro_pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    o2_sensor_b1s1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    o2_sensor_b1s2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    catalyst_temp_b1s1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    catalyst_temp_b1s2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    oil_pressure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # DTC event counts — injected into telemetry for AI timeline correlation
    dtc_active_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dtc_pending_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Mode 06 ECU test summary counts
    mode06_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mode06_passed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mode06_failed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Mode 06 ECU test results (stored as JSON array)
    mode06_results: Mapped[Optional[str]] = mapped_column(Text)

    # Consult-II extended sensors (Pi5 edge unit)
    injector_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fuel_trim_b2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accel_pedal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

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


class DailyVehicleStats(Base):
    """Daily aggregated vehicle statistics for charts and PDF reports."""
    __tablename__ = "daily_vehicle_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # "2026-02-14"
    max_speed_kmh: Mapped[float] = mapped_column(Float, server_default="0.0")
    max_coolant_temp_c: Mapped[float] = mapped_column(Float, server_default="0.0")
    avg_speed_kmh: Mapped[float] = mapped_column(Float, server_default="0.0")
    total_distance_km: Mapped[float] = mapped_column(Float, server_default="0.0")
    total_fuel_consumed_l: Mapped[float] = mapped_column(Float, server_default="0.0")
    data_points: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("profile_id", "date", name="uq_daily_stats_vehicle_date"),
        Index("idx_daily_stats_profile", "profile_id"),
    )


class VehicleResearch(TimestampMixin, Base):
    """Vehicle research data from LLM + web search.

    Stores common problems, recalls, failure-prone parts, and AI features
    for a vehicle make/model/year. Populated automatically after vehicle
    registration via background research task.
    """
    __tablename__ = "vehicle_research"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicle_profiles.profile_id"), unique=True,
    )

    # Status: pending, researching, completed, failed, stale
    research_status: Mapped[str] = mapped_column(String(20), server_default="pending")

    # Research results (stored as JSON strings)
    common_problems: Mapped[Optional[str]] = mapped_column(Text)
    failure_prone_parts: Mapped[Optional[str]] = mapped_column(Text)
    recalls: Mapped[Optional[str]] = mapped_column(Text)
    tsbs: Mapped[Optional[str]] = mapped_column(Text)
    owner_reviews_summary: Mapped[Optional[str]] = mapped_column(Text)

    # Scores
    reliability_score: Mapped[Optional[float]] = mapped_column(Float)  # 0-10
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)  # 0-1

    # AI features for prediction engine integration
    ai_features: Mapped[Optional[str]] = mapped_column(Text)

    # Raw data for debugging
    raw_search_results: Mapped[Optional[str]] = mapped_column(Text)
    sources: Mapped[Optional[str]] = mapped_column(Text)

    # VIN status: unknown, detected, missing, manual
    vin_status: Mapped[str] = mapped_column(String(20), server_default="unknown")

    # When research was last completed
    researched_at: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        Index("idx_vehicle_research_profile", "profile_id"),
        Index("idx_vehicle_research_status", "research_status"),
    )


class VehicleBaseline(Base):
    """Per-vehicle AI baseline — learned 'normal' for THIS specific car.

    Progresses through phases as data accumulates:
      - collecting:        < 500 data points, just accumulating stats
      - baseline_ready:    500+ points, mean/std/trends available
      - autoencoder_ready: 2000+ points, autoencoder trained, anomaly detection active
    """
    __tablename__ = "vehicle_baselines"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicle_profiles.profile_id"), unique=True, index=True,
    )
    trip_count: Mapped[int] = mapped_column(Integer, server_default="0")
    data_points: Mapped[int] = mapped_column(Integer, server_default="0")

    # Per-sensor running stats: {"rpm": {"mean": 2400, "std": 300, "min": 700, "max": 6200}, ...}
    sensor_stats: Mapped[Optional[str]] = mapped_column(Text)

    # Weekly trend data: {"coolant_temp": [91.2, 91.5, 91.8, 92.3], ...}
    weekly_trends: Mapped[Optional[str]] = mapped_column(Text)

    # Autoencoder model weights (~50KB per vehicle, binary)
    autoencoder_weights: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    autoencoder_trained_at: Mapped[Optional[float]] = mapped_column(Float)
    autoencoder_loss: Mapped[Optional[float]] = mapped_column(Float)

    # Phase: collecting / baseline_ready / autoencoder_ready
    phase: Mapped[str] = mapped_column(String(20), server_default="collecting")

    updated_at: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        Index("idx_vehicle_baselines_profile", "profile_id"),
    )


class VehiclePhoto(TimestampMixin, Base):
    """Pre-uploaded vehicle photos for matching on registration."""
    __tablename__ = "vehicle_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    vin: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    license_plate: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500))
    original_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(20), server_default="admin")  # admin/owner/driver
    assigned_to_profile_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class FailureEvent(TimestampMixin, Base):
    """Confirmed vehicle failure/repair event for AI training."""
    __tablename__ = "failure_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("vehicle_profiles.profile_id"))

    # Event details
    event_type: Mapped[str] = mapped_column(String(50))
    # Values: component_failure, dtc_confirmed, repair_completed, recall_service, preventive_maintenance
    component: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), server_default="medium")
    # Values: low, medium, high, critical

    # Linked data
    dtc_code: Mapped[Optional[str]] = mapped_column(String(10))
    mileage_at_failure: Mapped[Optional[int]] = mapped_column(Integer)
    cost: Mapped[Optional[float]] = mapped_column(Float)  # QAR

    # OBD snapshot at time of failure (JSON sensor values)
    obd_snapshot: Mapped[Optional[str]] = mapped_column(Text)

    # AI training metadata
    training_label: Mapped[Optional[str]] = mapped_column(String(50))
    training_exported: Mapped[bool] = mapped_column(Boolean, server_default="false")

    event_timestamp: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        Index("idx_failure_events_profile", "profile_id"),
        Index("idx_failure_events_type", "event_type"),
        Index("idx_failure_events_component", "component"),
    )
