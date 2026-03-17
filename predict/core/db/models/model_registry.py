"""
ML model registry and training job tracking.

Tables:
- model_versions       — trained TFLite models per vehicle
- base_model_entries   — fleet-wide base models for transfer learning
- training_jobs        — training job queue and status
"""

import time
from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base, TimestampMixin


class ModelVersion(TimestampMixin, Base):
    """A trained TFLite model for a specific vehicle.

    Model files live on the filesystem (e.g.
    ``/var/predict/models/{profile_id}/{type}_v{version}.tflite``).
    This table stores only the path and metadata.
    """
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicle_profiles.profile_id"), nullable=False, index=True,
    )
    model_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'health', 'anomaly', 'context'
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    # /var/predict/models/{pid}/{type}_v{ver}.tflite
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    training_data_points: Mapped[Optional[int]] = mapped_column(Integer)
    training_trips: Mapped[Optional[int]] = mapped_column(Integer)
    validation_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    # accuracy on held-out test set
    float32_accuracy: Mapped[Optional[float]] = mapped_column(Float)
    # pre-quantization accuracy
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    # active, superseded, unverified

    __table_args__ = (
        Index("idx_mv_profile_type", "profile_id", "model_type"),
    )


class BaseModelEntry(TimestampMixin, Base):
    """Fleet-wide base model for transfer learning.

    A base model is trained across multiple vehicles of the same make
    (optionally model) so that new vehicles can start from a pre-trained
    checkpoint rather than training from scratch.
    """
    __tablename__ = "base_model_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    make: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(50))
    # null means all models for that make
    model_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'health', 'anomaly', 'context'
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    training_vehicle_count: Mapped[int] = mapped_column(
        Integer, server_default="0",
    )

    __table_args__ = (
        Index("idx_bme_make_model_type", "make", "model", "model_type"),
    )


class TrainingJob(Base):
    """Training job queue entry and status tracker.

    Jobs are created by auto-retraining triggers (trip count, accuracy
    drop, safety interval) or manual requests.  The LSTM trainer picks
    them up, trains the model, and updates status + result pointer.
    """
    __tablename__ = "training_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicle_profiles.profile_id"), nullable=False, index=True,
    )
    model_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'health', 'anomaly', 'context'
    status: Mapped[str] = mapped_column(String(20), server_default="queued")
    # queued, running, success, failed
    trigger_reason: Mapped[Optional[str]] = mapped_column(String(50))
    # '50_trips', 'accuracy_drop', '90_day_safety', 'first_model'
    queued_at: Mapped[float] = mapped_column(
        Float, nullable=False, default=time.time,
    )
    started_at: Mapped[Optional[float]] = mapped_column(Float)
    completed_at: Mapped[Optional[float]] = mapped_column(Float)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    result_model_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("model_versions.id"),
    )

    __table_args__ = (
        Index("idx_tj_profile_status", "profile_id", "status"),
    )
