"""
User, API key, and entitlement models.
Consolidates: unified_users + customers → users
              unified_api_keys → api_keys
              entitlements, rate_limits, usage_counters, tier_presets, driver_assignments
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Float, Boolean, Text, ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from predict.core.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """Core identity table. Merges unified_users + customers."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), server_default="owner")  # owner, driver, admin
    status: Mapped[str] = mapped_column(String(20), server_default="active")  # active, suspended, deleted
    registered_via: Mapped[str] = mapped_column(String(20), server_default="desktop")  # desktop, android
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    # From customers table
    car_plate: Mapped[Optional[str]] = mapped_column(String(20))
    tier: Mapped[str] = mapped_column(String(20), server_default="free")
    tier_expiry: Mapped[Optional[float]] = mapped_column(Float)
    predictions_used: Mapped[int] = mapped_column(Integer, server_default="0")
    predictions_reset_date: Mapped[Optional[float]] = mapped_column(Float)
    verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    fcm_token: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(5), server_default="en")
    profile_id: Mapped[Optional[int]] = mapped_column(Integer)

    # Legacy hash for migration (SHA-256 from old system)
    legacy_api_key_hash: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    api_keys: Mapped[List["ApiKey"]] = relationship(back_populates="user", foreign_keys="ApiKey.user_id")
    entitlements: Mapped[List["Entitlement"]] = relationship(back_populates="user")

    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
        Index("idx_users_tier", "tier"),
    )


class ApiKey(Base):
    """API keys linked to users. bcrypt hashed."""
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), server_default="Default Key")
    status: Mapped[str] = mapped_column(String(20), server_default="active")  # active, revoked
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_used_at: Mapped[Optional[float]] = mapped_column(Float)

    # Legacy SHA-256 hash for 30-day migration
    legacy_sha256_hash: Mapped[Optional[str]] = mapped_column(String(255))

    user: Mapped["User"] = relationship(back_populates="api_keys", foreign_keys=[user_id])

    __table_args__ = (
        Index("idx_api_keys_hash", "key_hash"),
        Index("idx_api_keys_user", "user_id"),
    )


class Entitlement(Base):
    """Per-user feature access flags."""
    __tablename__ = "entitlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    granted_at: Mapped[float] = mapped_column(Float, nullable=False)
    granted_by: Mapped[Optional[int]] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="entitlements")

    __table_args__ = (
        UniqueConstraint("user_id", "feature", name="uq_entitlement_user_feature"),
    )


class RateLimit(Base):
    """Per-user, per-feature rate limits."""
    __tablename__ = "rate_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    max_requests: Mapped[Optional[int]] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # minute, hour, day, month

    __table_args__ = (
        UniqueConstraint("user_id", "feature", name="uq_rate_limit_user_feature"),
    )


class UsageCounter(Base):
    """Server-side usage tracking."""
    __tablename__ = "usage_counters"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[float] = mapped_column(Float, nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, server_default="0")

    __table_args__ = (
        UniqueConstraint("user_id", "feature", "period_start", "period_type",
                         name="uq_usage_counter"),
    )


class TierPreset(Base):
    """Preset tier configurations."""
    __tablename__ = "tier_presets"

    tier_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    features: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    default_limits: Mapped[str] = mapped_column(Text, nullable=False)  # JSON object


class DriverAssignment(Base):
    """Links drivers to vehicles and owners."""
    __tablename__ = "driver_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_at: Mapped[float] = mapped_column(Float, nullable=False)


class UserFeatureOverride(Base):
    """Per-user feature toggles (NULL = use tier default)."""
    __tablename__ = "user_feature_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    obd_dashboard: Mapped[Optional[int]] = mapped_column(Integer)
    dtc_read: Mapped[Optional[int]] = mapped_column(Integer)
    dtc_clear: Mapped[Optional[int]] = mapped_column(Integer)
    ai_chat: Mapped[Optional[int]] = mapped_column(Integer)
    predictions: Mapped[Optional[int]] = mapped_column(Integer)
    guardian_mode: Mapped[Optional[int]] = mapped_column(Integer)
    desktop_sync: Mapped[Optional[int]] = mapped_column(Integer)
    pdf_reports: Mapped[Optional[int]] = mapped_column(Integer)
    push_alerts: Mapped[Optional[int]] = mapped_column(Integer)
    data_export: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[Optional[float]] = mapped_column(Float)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer)


class PricingConfig(Base):
    """Subscription tier pricing (admin-configurable)."""
    __tablename__ = "pricing_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    tier: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    price_monthly: Mapped[Optional[float]] = mapped_column(Float)
    price_yearly: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), server_default="SAR")
    features_json: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
