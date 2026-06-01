"""
Subscription, fleet, geofence, and audit models.
Tables: fleet_invites, geofences, geofence_events, tier_upgrade_requests,
        subscription_audit_log
"""

from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class FleetInvite(Base):
    """Fleet management invite codes."""
    __tablename__ = "fleet_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    fleet_manager_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[Optional[float]] = mapped_column(Float)
    used_by: Mapped[Optional[int]] = mapped_column(Integer)
    used_at: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Geofence(Base):
    """Geographic boundaries for guardian alerts."""
    __tablename__ = "geofences"

    id: Mapped[int] = mapped_column(primary_key=True)
    geofence_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guardian_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lng: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String(20), server_default="safe_zone")
    alert_on_entry: Mapped[bool] = mapped_column(Boolean, server_default="false")
    alert_on_exit: Mapped[bool] = mapped_column(Boolean, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (
        Index("idx_geofences_profile", "profile_id"),
    )


class GeofenceEvent(Base):
    """Geofence entry/exit tracking."""
    __tablename__ = "geofence_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    geofence_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    driver_id: Mapped[Optional[str]] = mapped_column(String(36))
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[Optional[float]] = mapped_column(Float)
    notified: Mapped[bool] = mapped_column(Boolean, server_default="false")


class TierUpgradeRequest(Base):
    """Tier upgrade requests requiring admin approval."""
    __tablename__ = "tier_upgrade_requests"

    request_id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(String(100))
    current_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    requested_at: Mapped[float] = mapped_column(Float, nullable=False)
    processed_at: Mapped[Optional[float]] = mapped_column(Float)
    processed_by: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    new_api_key_hash: Mapped[Optional[str]] = mapped_column(String(255))
    owner_name: Mapped[Optional[str]] = mapped_column(String(255))
    owner_email: Mapped[Optional[str]] = mapped_column(String(255))
    tier_price: Mapped[Optional[str]] = mapped_column(String(50))
    tier_features: Mapped[Optional[str]] = mapped_column(Text)
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    fleet_size: Mapped[Optional[str]] = mapped_column(String(50))

    __table_args__ = (
        Index("idx_upgrade_requests_status", "status"),
        Index("idx_upgrade_requests_owner", "owner_id"),
    )


class Subscription(Base):
    """User subscriptions via Google Play Billing or PayPal."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    # Payment source: "google" or "paypal"
    payment_source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Google Play fields
    google_purchase_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    google_product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    google_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # PayPal fields
    paypal_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    paypal_plan_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    started_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cancelled_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)


class SubscriptionAuditLog(Base):
    """Track all subscription/permission changes."""
    __tablename__ = "subscription_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[Optional[str]] = mapped_column(String(100))
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)


class Fleet(Base):
    """Fleet groups for fleet management."""
    __tablename__ = "fleets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[Optional[float]] = mapped_column(Float)


class FleetMember(Base):
    """Fleet membership linking users to fleets."""
    __tablename__ = "fleet_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), server_default="driver")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    joined_at: Mapped[float] = mapped_column(Float, nullable=False)
