"""
Hindsight Learning Models for Retrospective Label Propagation.

Stores observations of DTC occurrences and AI predictions for future training.
"""

import time
from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class HindsightObservation(Base):
    """
    Stores a single DTC occurrence with preceding sensor data.
    
    Used for retrospective learning - when AI misses a prediction,
    this data becomes the most valuable training example.
    """
    
    __tablename__ = "hindsight_observations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Vehicle and DTC info
    vehicle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vehicle_profiles.id"),
        nullable=False,
        index=True,
    )
    dtc_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    
    # When the DTC was detected (Unix timestamp)
    detected_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    
    # Was this DTC predicted by the AI in advance?
    was_predicted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # What the AI was predicting at the time (JSON)
    prediction_at_time: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Sensor data before the DTC (JSON array of sensor readings)
    sensor_window_before: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # How many data points in the window
    window_size: Mapped[int] = mapped_column(Integer, default=0)
    
    # Vehicle mileage at detection
    mileage_at_detection: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Credibility score based on DTC type (0.0-1.0)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.6)
    
    # Status: collected | validated | used_for_training | rejected
    status: Mapped[str] = mapped_column(String(20), default="collected", index=True)
    
    # Repair information
    repair_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repair_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Sensor data after repair (to capture "healthy" state)
    post_repair_window: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Did the same DTC recur within 30 days? (indicates bad repair)
    dtc_recurred: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Notes for human reviewers
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps (Unix epoch)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(
        Float,
        default=time.time,
        onupdate=time.time,
    )
    
    def __repr__(self) -> str:
        return (
            f"<HindsightObservation(id={self.id}, vehicle={self.vehicle_id}, "
            f"dtc={self.dtc_code}, status={self.status})>"
        )


class PredictionAuditLog(Base):
    """
    Audit log of every prediction made by the AI system.
    
    Used for:
    - Debugging missed predictions
    - Calibration of uncertainty estimates
    - Regulatory compliance
    - Model performance tracking
    """
    
    __tablename__ = "prediction_audit_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Vehicle being assessed
    vehicle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vehicle_profiles.id"),
        nullable=False,
        index=True,
    )
    
    # Component being predicted
    component: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Risk scores
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)  # Smoothed
    raw_risk_score: Mapped[float] = mapped_column(Float, nullable=False)  # Before smoothing
    
    # Uncertainty estimate
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Which models contributed
    models_used: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list
    
    # Individual model predictions
    model_predictions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON dict
    
    # Abstention info
    abstained: Mapped[bool] = mapped_column(Boolean, default=False)
    abstention_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Sensor snapshot at prediction time
    sensor_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    
    # Vehicle mileage at prediction
    mileage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Additional metadata
    additional_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    
    # When the prediction was made (Unix timestamp)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    
    def __repr__(self) -> str:
        return (
            f"<PredictionAuditLog(id={self.id}, vehicle={self.vehicle_id}, "
            f"component={self.component}, risk={self.risk_score:.3f})>"
        )


class ModelRetrainingEvent(Base):
    """
    Tracks model retraining events for governance.
    
    Every time a model is retrained, we record:
    - What data was used
    - Performance metrics
    - Who approved it
    """
    
    __tablename__ = "model_retraining_events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Model info
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Parent model (if any)
    parent_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Training data info
    training_data_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    hindsight_samples_used: Mapped[int] = mapped_column(Integer, default=0)
    total_training_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Performance metrics
    validation_auc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    validation_accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    validation_f1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Who approved this retraining
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status: pending | approved | deployed | rejected | rolled_back
    status: Mapped[str] = mapped_column(String(20), default="pending")
    
    # Timestamps
    trained_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    approved_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deployed_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(
        Float,
        default=time.time,
        onupdate=time.time,
    )
    
    def __repr__(self) -> str:
        return (
            f"<ModelRetrainingEvent(id={self.id}, model={self.model_name}, "
            f"version={self.model_version}, status={self.status})>"
        )
