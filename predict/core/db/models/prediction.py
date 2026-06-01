"""
AI prediction and ML training models.
Tables: predictions, ml_training_labels, ml_aggregated_features,
        fleet_baselines, obd_sensor_config
"""

from typing import Optional

from sqlalchemy import String, Integer, Float, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class Prediction(Base):
    """AI failure predictions per vehicle component."""
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    component: Mapped[str] = mapped_column(String(100), nullable=False)
    failure_probability: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_days: Mapped[Optional[int]] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)
    acknowledged_at: Mapped[Optional[float]] = mapped_column(Float)
    resolved_at: Mapped[Optional[float]] = mapped_column(Float)
    data_json: Mapped[Optional[str]] = mapped_column(Text)

    @property
    def health_score(self) -> float:
        """Derived health score: inverse of failure_probability on 0-100 scale."""
        return round((1.0 - self.failure_probability) * 100, 1)

    __table_args__ = (
        Index("idx_predictions_profile", "profile_id", "status"),
    )


class MLTrainingLabel(Base):
    """Track prediction accuracy vs actual repairs."""
    __tablename__ = "ml_training_labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prediction_id: Mapped[Optional[str]] = mapped_column(String(36))
    component: Mapped[str] = mapped_column(String(100), nullable=False)
    predicted_failure_date: Mapped[Optional[str]] = mapped_column(String(20))
    actual_failure_date: Mapped[Optional[str]] = mapped_column(String(20))
    actual_outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    mileage_at_prediction: Mapped[Optional[int]] = mapped_column(Integer)
    mileage_at_outcome: Mapped[Optional[int]] = mapped_column(Integer)
    repair_cost: Mapped[Optional[float]] = mapped_column(Float)
    parts_replaced: Mapped[Optional[str]] = mapped_column(Text)
    dtc_codes: Mapped[Optional[str]] = mapped_column(Text)
    labeled_by: Mapped[Optional[str]] = mapped_column(String(100))
    labeled_at: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_ml_labels_profile", "profile_id"),
        Index("idx_ml_labels_component", "component"),
    )


class MLAggregatedFeature(Base):
    """Hourly/daily/weekly aggregated OBD data for ML training."""
    __tablename__ = "ml_aggregated_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregation_period: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[float] = mapped_column(Float, nullable=False)
    period_end: Mapped[float] = mapped_column(Float, nullable=False)
    rpm_mean: Mapped[Optional[float]] = mapped_column(Float)
    rpm_std: Mapped[Optional[float]] = mapped_column(Float)
    rpm_max: Mapped[Optional[float]] = mapped_column(Float)
    speed_mean: Mapped[Optional[float]] = mapped_column(Float)
    speed_std: Mapped[Optional[float]] = mapped_column(Float)
    speed_max: Mapped[Optional[float]] = mapped_column(Float)
    coolant_temp_mean: Mapped[Optional[float]] = mapped_column(Float)
    coolant_temp_max: Mapped[Optional[float]] = mapped_column(Float)
    battery_voltage_mean: Mapped[Optional[float]] = mapped_column(Float)
    battery_voltage_min: Mapped[Optional[float]] = mapped_column(Float)
    engine_load_mean: Mapped[Optional[float]] = mapped_column(Float)
    engine_load_max: Mapped[Optional[float]] = mapped_column(Float)
    maf_rate_mean: Mapped[Optional[float]] = mapped_column(Float)
    fuel_trim_short_mean: Mapped[Optional[float]] = mapped_column(Float)
    fuel_trim_long_mean: Mapped[Optional[float]] = mapped_column(Float)
    cold_starts: Mapped[Optional[int]] = mapped_column(Integer)
    total_runtime_minutes: Mapped[Optional[float]] = mapped_column(Float)
    idle_time_minutes: Mapped[Optional[float]] = mapped_column(Float)
    high_load_time_minutes: Mapped[Optional[float]] = mapped_column(Float)
    dtc_count: Mapped[Optional[int]] = mapped_column(Integer)
    record_count: Mapped[Optional[int]] = mapped_column(Integer)
    data_quality_score: Mapped[Optional[float]] = mapped_column(Float)
    extra_sensors: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("profile_id", "aggregation_period", "period_start",
                         name="uq_ml_features"),
        Index("idx_ml_features_profile", "profile_id"),
        Index("idx_ml_features_period", "aggregation_period", "period_start"),
    )


class FleetBaseline(Base):
    """Fleet-wide averages for comparison."""
    __tablename__ = "fleet_baselines"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_make: Mapped[str] = mapped_column(String(100), nullable=False)
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100))
    vehicle_year_range: Mapped[Optional[str]] = mapped_column(String(20))
    component: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    baseline_mean: Mapped[Optional[float]] = mapped_column(Float)
    baseline_std: Mapped[Optional[float]] = mapped_column(Float)
    baseline_p10: Mapped[Optional[float]] = mapped_column(Float)
    baseline_p90: Mapped[Optional[float]] = mapped_column(Float)
    sample_size: Mapped[Optional[int]] = mapped_column(Integer)
    last_updated: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("vehicle_make", "vehicle_model", "vehicle_year_range",
                         "component", "metric_name", name="uq_fleet_baseline"),
        Index("idx_fleet_baselines_vehicle", "vehicle_make", "vehicle_model"),
    )


class OBDSensorConfig(Base):
    """Dynamic sensor configuration for extensibility."""
    __tablename__ = "obd_sensor_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    pid_code: Mapped[Optional[str]] = mapped_column(String(10))
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    min_value: Mapped[Optional[float]] = mapped_column(Float)
    max_value: Mapped[Optional[float]] = mapped_column(Float)
    critical_threshold_low: Mapped[Optional[float]] = mapped_column(Float)
    critical_threshold_high: Mapped[Optional[float]] = mapped_column(Float)
    aggregation_method: Mapped[str] = mapped_column(String(20), server_default="mean")
    enabled: Mapped[bool] = mapped_column(Integer, server_default="1")
    priority: Mapped[int] = mapped_column(Integer, server_default="0")
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[Optional[float]] = mapped_column(Float)
