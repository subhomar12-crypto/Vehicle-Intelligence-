"""
Prediction feedback and fleet learning models.
Tables: prediction_snapshots, prediction_accuracy, prediction_feedback,
        fleet_patterns, fleet_learning_adjustments
"""

import time
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, Index,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from predict.core.db.base import Base


class PredictionSnapshot(Base):
    __tablename__ = "prediction_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, nullable=False, index=True)
    component = Column(String(50), nullable=False)
    predicted_score = Column(Integer, nullable=False)
    predicted_trend = Column(String(20))
    confidence_tier = Column(String(20))          # measured/inferred/estimated
    sensor_readings = Column(JSONB)               # snapshot of relevant sensor values
    driving_context = Column(String(20))          # idle/city/highway/aggressive
    snapshot_date = Column(Float, default=lambda: time.time())
    created_at = Column(Float, default=lambda: time.time())

    __table_args__ = (
        Index("idx_snapshots_vehicle_date", "vehicle_id", "snapshot_date"),
    )


class PredictionAccuracy(Base):
    __tablename__ = "prediction_accuracy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, nullable=False, index=True)
    component = Column(String(50), nullable=False)
    prediction_date = Column(Float, nullable=False)
    validation_date = Column(Float, nullable=False)
    predicted_score = Column(Integer)
    actual_score = Column(Integer)
    trend_predicted = Column(String(20))
    trend_actual = Column(String(20))
    was_accurate = Column(Boolean)
    created_at = Column(Float, default=lambda: time.time())


class PredictionFeedback(Base):
    __tablename__ = "prediction_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, nullable=False, index=True)
    component = Column(String(50), nullable=False)
    predicted_score = Column(Integer)
    actual_outcome = Column(String(20))           # confirmed_bad / confirmed_good / unknown
    service_record_id = Column(Integer)
    feedback_date = Column(Float, nullable=False)
    make = Column(String(50))                     # denormalized for fleet learning
    model = Column(String(50))
    year = Column(Integer)
    created_at = Column(Float, default=lambda: time.time())


class FleetPattern(Base):
    __tablename__ = "fleet_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    make = Column(String(50), nullable=False)
    model = Column(String(50), nullable=False)
    component = Column(String(50), nullable=False)
    pattern_type = Column(String(50))             # sensor_trend, threshold_breach, dtc_sequence
    pattern_signature = Column(JSONB)             # sensor conditions preceding failure
    evidence_count = Column(Integer, default=1)
    confidence = Column(Float, default=0.3)
    first_seen = Column(Float)
    last_confirmed = Column(Float)
    created_at = Column(Float, default=lambda: time.time())

    __table_args__ = (
        UniqueConstraint("make", "model", "component", "pattern_type",
                         name="uq_fleet_pattern"),
    )


class FleetLearningAdjustment(Base):
    __tablename__ = "fleet_learning_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    make = Column(String(50), nullable=False)
    model = Column(String(50), nullable=False)
    component = Column(String(50), nullable=False)
    adjustment_type = Column(String(30))          # age_decay_rate, penalty_weight, threshold
    adjustment_value = Column(Float)              # multiplier or offset
    evidence_count = Column(Integer, default=0)
    last_updated = Column(Float)

    __table_args__ = (
        UniqueConstraint("make", "model", "component", "adjustment_type",
                         name="uq_fleet_adj"),
    )


class ComponentAccuracyStats(Base):
    """Per-component prediction accuracy aggregated nightly by self_validation_job."""
    __tablename__ = "component_accuracy_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component = Column(String(50), nullable=False, unique=True, index=True)
    mean_absolute_error = Column(Float, default=0.0)   # avg |predicted - actual|
    directional_accuracy = Column(Float, default=0.5)  # fraction correct direction
    sample_count = Column(Integer, default=0)
    last_updated = Column(Float, default=lambda: time.time())


class FleetPenaltyAdjustment(Base):
    """Fleet-wide penalty multipliers per component, computed by fleet_learning_job."""
    __tablename__ = "fleet_penalty_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component = Column(String(50), nullable=False, unique=True, index=True)
    penalty_multiplier = Column(Float, default=1.0)    # multiply raw penalties by this
    sample_count = Column(Integer, default=0)
    directional_accuracy = Column(Float, default=0.5)
    mean_absolute_error = Column(Float, default=0.0)
    last_updated = Column(Float, default=lambda: time.time())
