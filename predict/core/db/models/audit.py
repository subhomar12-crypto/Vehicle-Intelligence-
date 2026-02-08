"""
Audit, verification, and operational models.
Tables: audit_log, verification_codes, verification_sessions,
        idempotency_cache, failed_operations,
        login_verification_codes, data_export_config, export_history
"""

from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class AuditLog(Base):
    """Track all auth-related and admin actions."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    admin_id: Mapped[Optional[int]] = mapped_column(Integer)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    request_id: Mapped[Optional[str]] = mapped_column(String(36))
    details: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_audit_log_user", "user_id"),
        Index("idx_audit_log_timestamp", "timestamp"),
    )


class VerificationCode(Base):
    """Unified verification codes for registration, login, invites."""
    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    nonce: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, server_default="false")
    submitted_nonce: Mapped[Optional[str]] = mapped_column(String(64))

    __table_args__ = (
        Index("idx_verification_codes_user", "user_id", "type"),
        Index("idx_verification_codes_expires", "expires_at"),
    )


class VerificationSession(Base):
    """Session layer for safer verification flows."""
    __tablename__ = "verification_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, server_default="false")


class IdempotencyCache(Base):
    """Prevent duplicate operations from retries."""
    __tablename__ = "idempotency_cache"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("idx_idempotency_expires", "expires_at"),
    )


class FailedOperation(Base):
    """Dead letter queue for retryable operations."""
    __tablename__ = "failed_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, server_default="5")
    next_retry_at: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    completed_at: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")

    __table_args__ = (
        Index("idx_failed_ops_retry", "status", "next_retry_at"),
    )


class DataExportConfig(Base):
    """Export destination and schedule settings."""
    __tablename__ = "data_export_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    config_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    export_path: Mapped[str] = mapped_column(Text, nullable=False)
    export_format: Mapped[str] = mapped_column(String(10), server_default="csv")
    export_schedule: Mapped[str] = mapped_column(String(20), server_default="hourly")
    include_raw_data: Mapped[bool] = mapped_column(Boolean, server_default="false")
    include_aggregates: Mapped[bool] = mapped_column(Boolean, server_default="true")
    include_labels: Mapped[bool] = mapped_column(Boolean, server_default="true")
    last_export_time: Mapped[Optional[float]] = mapped_column(Float)
    last_export_status: Mapped[Optional[str]] = mapped_column(String(20))
    last_export_records: Mapped[Optional[int]] = mapped_column(Integer)
    last_export_error: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[Optional[float]] = mapped_column(Float)


class ExportHistory(Base):
    """Log of all export operations."""
    __tablename__ = "export_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(Integer, nullable=False)
    config_name: Mapped[str] = mapped_column(String(100), nullable=False)
    export_path: Mapped[str] = mapped_column(Text, nullable=False)
    export_format: Mapped[str] = mapped_column(String(10), nullable=False)
    started_at: Mapped[float] = mapped_column(Float, nullable=False)
    completed_at: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    records_exported: Mapped[Optional[int]] = mapped_column(Integer)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    files_created: Mapped[Optional[str]] = mapped_column(Text)
