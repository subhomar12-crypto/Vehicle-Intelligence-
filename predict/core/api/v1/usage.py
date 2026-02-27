"""
Usage tracking, quota checking, and permissions API.

Handles:
- API key permissions and entitlements
- Usage tracking with Redis/DB fallback
- Rate limit checking
- Feature access verification
"""

import logging
import time
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user
from predict.core.db.models.user import User, ApiKey, Entitlement
from predict.core.config import get_config

logger = logging.getLogger(__name__)

# Main router for /usage/* endpoints
router = APIRouter()

# Separate router for /key/permissions (included with different prefix)
key_router = APIRouter()


# ===== Pydantic Models =====

class UsageTrackRequest(BaseModel):
    """Request model for tracking usage."""
    feature: str = Field(..., description="Feature being used (e.g., llm_chat, predictions)")
    count: int = Field(default=1, ge=1, description="Number of usages to track")


class UsageTrackResponse(BaseModel):
    """Response model for usage tracking."""
    success: bool
    feature: str
    usage: Dict[str, Any]
    tier: str


class UsageCheckResponse(BaseModel):
    """Response model for usage check."""
    success: bool
    allowed: bool
    reason: Optional[str]
    usage: Dict[str, Any]
    feature: str
    tier: str
    upgrade_required: bool
    message: Optional[str]


class FeatureUsage(BaseModel):
    """Usage stats for a single feature."""
    used: int
    limit: int
    remaining: int
    unlimited: bool
    has_access: bool
    period: str


class KeyPermissionsResponse(BaseModel):
    """Response model for key permissions."""
    success: bool
    permissions: Dict[str, Any]
    entitlements: Dict[str, bool]
    rate_limits: Dict[str, Dict[str, Any]]
    usage: Dict[str, FeatureUsage]
    key_info: Dict[str, Any]


class AllUsageResponse(BaseModel):
    """Response model for all usage stats."""
    success: bool
    tier: str
    usage: Dict[str, Dict[str, Any]]
    resets_at: Dict[str, float]


# ===== Tier Configuration =====

TIER_DEFAULTS = {
    "free": {
        "daily_obd_requests": -1,       # unlimited for ALL tiers
        "stored_vehicles": 1,
        "dtc_checks_total": 0,          # No DTC for free
        "predictions_per_day": 0,       # No predictions for free
        "llm_chat_per_day": 0,          # No chat for free
        "pdfs_per_week": 0,             # No PDFs for free
        "guardian_mode": False,
        "fleet_management": False,
        "ai_chat": False,
        "pdf_reports": False,
        "prediction_history_days": 0,
    },
    "pro": {
        "daily_obd_requests": -1,
        "stored_vehicles": 1,
        "dtc_checks_total": -1,         # unlimited
        "predictions_per_day": 2,
        "llm_chat_per_day": 15,
        "pdfs_per_week": 1,
        "guardian_mode": False,          # No guardian for Pro
        "fleet_management": False,
        "ai_chat": True,
        "pdf_reports": True,
        "prediction_history_days": 90,
    },
    "premium": {
        "daily_obd_requests": -1,
        "stored_vehicles": 3,           # 3 vehicles (including registered vehicle)
        "dtc_checks_total": -1,
        "predictions_per_day": 10,      # 5x pro
        "llm_chat_per_day": 75,         # 5x pro
        "pdfs_per_week": 5,             # 5x pro
        "guardian_mode": True,           # Guardian for Premium only
        "fleet_management": False,
        "ai_chat": True,
        "pdf_reports": True,
        "prediction_history_days": 365,
    },
    "admin": {
        "daily_obd_requests": -1,
        "stored_vehicles": -1,
        "dtc_checks_total": -1,
        "predictions_per_day": -1,
        "llm_chat_per_day": -1,
        "pdfs_per_week": -1,
        "guardian_mode": True,
        "fleet_management": True,
        "ai_chat": True,
        "pdf_reports": True,
        "prediction_history_days": -1,
    },
}

FEATURE_DISPLAY_NAMES = {
    "daily_obd_requests": "Daily OBD Requests",
    "predictions_per_day": "Daily Predictions",
    "llm_chat_per_day": "Daily AI Chat Messages",
    "pdfs_per_week": "Weekly PDF Reports",
    "dtc_checks_total": "DTC Checks",
}

# In-memory usage cache (fallback when Redis unavailable)
_usage_cache: Dict[str, Dict[str, Any]] = {}


# ===== Helper Functions =====

def _get_current_date_str() -> str:
    """Get current date as YYYY-MM-DD string."""
    return time.strftime("%Y-%m-%d", time.gmtime())


def _get_current_week_str() -> str:
    """Get current week as YYYY-WW string."""
    now = time.gmtime()
    return f"{now.tm_year}-{now.tm_yday // 7:02d}"


def _get_period_key(feature: str, period: str) -> str:
    """Generate cache key for a feature/period combination."""
    if period == "day":
        date_str = _get_current_date_str()
        return f"{feature}:daily:{date_str}"
    elif period == "week":
        week_str = _get_current_week_str()
        return f"{feature}:weekly:{week_str}"
    return f"{feature}:{period}"


def _get_seconds_until_midnight() -> int:
    """Calculate seconds until next midnight UTC."""
    now = time.gmtime()
    tomorrow = time.mktime((now.tm_year, now.tm_mon, now.tm_mday + 1, 0, 0, 0, 0, 0, 0))
    return int(tomorrow - time.time())


def _get_seconds_until_sunday_midnight() -> int:
    """Calculate seconds until next Sunday midnight UTC."""
    now = time.gmtime()
    days_until_sunday = (7 - now.tm_wday) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sunday = time.mktime((now.tm_year, now.tm_mon, now.tm_mday + days_until_sunday, 0, 0, 0, 0, 0, 0))
    return int(next_sunday - time.time())


def _get_tier_limit(tier: str, feature: str, vehicle_count: int = 1) -> int:
    """Get the limit for a feature in a tier."""
    tier_config = TIER_DEFAULTS.get(tier.lower(), TIER_DEFAULTS["free"])
    limit = tier_config.get(feature, 0)
    
    # For premium tier, multiply per-vehicle limits by vehicle count
    if tier.lower() == "premium" and feature in ["predictions_per_day", "llm_chat_per_day", "pdfs_per_week"]:
        if limit > 0:
            limit = limit * max(1, min(vehicle_count, 4))  # Max 4 vehicles
    
    return limit


def _has_feature_access(tier: str, feature: str) -> bool:
    """Check if a tier has access to a feature."""
    tier_config = TIER_DEFAULTS.get(tier.lower(), TIER_DEFAULTS["free"])
    
    # Check boolean features
    if feature in ["guardian_mode", "fleet_management", "ai_chat", "pdf_reports"]:
        return tier_config.get(feature, False)
    
    # Check numeric limits
    limit = tier_config.get(feature, 0)
    return limit != 0  # -1 (unlimited) or positive number means access


def _get_usage_from_cache(user_id: int, feature: str, period: str) -> int:
    """Get usage count from in-memory cache."""
    key = f"{user_id}:{_get_period_key(feature, period)}"
    entry = _usage_cache.get(key)
    if entry:
        # Check if entry is expired
        if entry.get("expires_at", 0) > time.time():
            return entry.get("count", 0)
        else:
            # Remove expired entry
            del _usage_cache[key]
    return 0


def _set_usage_in_cache(user_id: int, feature: str, period: str, count: int) -> None:
    """Set usage count in in-memory cache with TTL."""
    key = f"{user_id}:{_get_period_key(feature, period)}"
    
    if period == "day":
        expires_at = time.time() + _get_seconds_until_midnight()
    elif period == "week":
        expires_at = time.time() + _get_seconds_until_sunday_midnight()
    else:
        expires_at = time.time() + 86400  # Default 24 hours
    
    _usage_cache[key] = {
        "count": count,
        "expires_at": expires_at,
    }


def _increment_usage_in_cache(user_id: int, feature: str, period: str, increment: int = 1) -> int:
    """Increment usage count in cache and return new count."""
    current = _get_usage_from_cache(user_id, feature, period)
    new_count = current + increment
    _set_usage_in_cache(user_id, feature, period, new_count)
    return new_count


async def _get_user_usage(
    user_id: int,
    feature: str,
    tier: str,
    vehicle_count: int = 1,
) -> Dict[str, Any]:
    """Get usage stats for a user and feature."""
    # Determine period based on feature
    if feature in ["pdfs_per_week"]:
        period = "week"
    else:
        period = "day"
    
    limit = _get_tier_limit(tier, feature, vehicle_count)
    unlimited = limit == -1
    
    # Get used count from cache
    used = _get_usage_from_cache(user_id, feature, period)
    
    # Calculate remaining
    if unlimited:
        remaining = -1
    else:
        remaining = max(0, limit - used)
    
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "unlimited": unlimited,
        "has_access": _has_feature_access(tier, feature),
        "period": period,
    }


async def _track_usage(
    user_id: int,
    feature: str,
    tier: str,
    count: int = 1,
    vehicle_count: int = 1,
) -> Dict[str, Any]:
    """Track usage for a feature."""
    # Determine period based on feature
    if feature in ["pdfs_per_week"]:
        period = "week"
    else:
        period = "day"
    
    limit = _get_tier_limit(tier, feature, vehicle_count)
    unlimited = limit == -1
    
    # Increment usage in cache
    new_used = _increment_usage_in_cache(user_id, feature, period, count)
    
    # Calculate remaining
    if unlimited:
        remaining = -1
    else:
        remaining = max(0, limit - new_used)
    
    return {
        "used": new_used,
        "limit": limit,
        "remaining": remaining,
        "unlimited": unlimited,
        "has_access": _has_feature_access(tier, feature),
        "period": period,
    }


async def _check_entitlement_override(
    session: AsyncSession,
    user_id: int,
    feature: str,
) -> Optional[bool]:
    """Check if user has a per-feature entitlement override."""
    stmt = select(Entitlement).where(
        Entitlement.user_id == user_id,
        Entitlement.feature == feature,
    )
    result = await session.execute(stmt)
    entitlement = result.scalar_one_or_none()
    
    if entitlement:
        return entitlement.enabled
    return None


# ===== API Endpoints =====

@key_router.get("/permissions", response_model=KeyPermissionsResponse)
async def get_key_permissions(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Get full permissions, entitlements, rate limits, and usage for current API key.
    
    Returns comprehensive access information for the Android app.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    tier = current_user.get("tier", "free")
    key_db_id = current_user.get("key_id")

    # Get user info
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get API key info by database ID
    api_key = None
    if key_db_id:
        result = await session.execute(
            select(ApiKey).where(ApiKey.id == key_db_id)
        )
        api_key = result.scalar_one_or_none()
    
    # Get vehicle count for premium calculations
    stmt = select(ApiKey).where(
        ApiKey.user_id == user_id,
        ApiKey.status == "active",
    )
    result = await session.execute(stmt)
    api_keys = result.scalars().all()
    vehicle_count = len(set(k.profile_id for k in api_keys if k.profile_id)) or 1
    
    # Build permissions
    permissions = {
        "has_driver_access": user.role == "driver" or user.role == "owner",
        "has_guardian_access": _has_feature_access(tier, "guardian_mode"),
        "max_vehicles": _get_tier_limit(tier, "stored_vehicles"),
        "subscription_tier": tier,
        "role": user.role,
        "features": [],
    }
    
    # Add features based on tier
    features = ["obd_reading", "dtc_reading"]
    if _has_feature_access(tier, "ai_chat"):
        features.append("ai_chat")
    if _has_feature_access(tier, "guardian_mode"):
        features.append("guardian_mode")
    if _has_feature_access(tier, "pdf_reports"):
        features.append("pdf_reports")
    permissions["features"] = features
    
    # Build entitlements
    entitlements = {
        "obd_reading": True,  # All tiers have OBD
        "dtc_reading": True,  # All tiers have DTC
        "ai_chat": _has_feature_access(tier, "ai_chat"),
        "guardian_mode": _has_feature_access(tier, "guardian_mode"),
        "pdf_reports": _has_feature_access(tier, "pdf_reports"),
        "fleet_management": _has_feature_access(tier, "fleet_management"),
    }
    
    # Build rate limits
    rate_limits = {
        "daily_obd_requests": {"max": -1 if _get_tier_limit(tier, "daily_obd_requests") == -1 else 2000, "period": "day"},
        "predictions_per_day": {"max": _get_tier_limit(tier, "predictions_per_day", vehicle_count), "period": "day"},
        "llm_chat_per_day": {"max": _get_tier_limit(tier, "llm_chat_per_day", vehicle_count), "period": "day"},
        "pdfs_per_week": {"max": _get_tier_limit(tier, "pdfs_per_week", vehicle_count), "period": "week"},
    }
    
    # Build usage stats
    usage = {}
    for feature in ["daily_obd_requests", "predictions_per_day", "llm_chat_per_day"]:
        usage[feature] = FeatureUsage(
            **await _get_user_usage(user_id, feature, tier, vehicle_count)
        )
    
    # Key info
    key_info = {
        "key_id": key_db_id or 0,
        "name": api_key.name if api_key else "default",
        "profile_id": api_key.profile_id if api_key else user.profile_id,
        "profile_name": "My Vehicle",  # Could be fetched from vehicle profile
    }
    
    return KeyPermissionsResponse(
        success=True,
        permissions=permissions,
        entitlements=entitlements,
        rate_limits=rate_limits,
        usage=usage,
        key_info=key_info,
    )


@router.post("/track", response_model=UsageTrackResponse)
async def track_usage(
    request: UsageTrackRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Track usage for a feature.
    
    Increments the usage counter and returns updated usage stats.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    tier = current_user.get("tier", "free")
    
    # Get vehicle count for premium calculations
    stmt = select(ApiKey).where(
        ApiKey.user_id == user_id,
        ApiKey.status == "active",
    )
    result = await session.execute(stmt)
    api_keys = result.scalars().all()
    vehicle_count = len(set(k.profile_id for k in api_keys if k.profile_id)) or 1
    
    # Check if feature is available for tier
    if not _has_feature_access(tier, request.feature):
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "error": "feature_not_available",
                "upgrade_required": True,
                "message": f"Feature '{request.feature}' not available for your tier",
            }
        )
    
    # Get current usage before incrementing
    usage_stats = await _get_user_usage(user_id, request.feature, tier, vehicle_count)
    
    # Check if limit exceeded (unless unlimited)
    if not usage_stats["unlimited"] and usage_stats["remaining"] < request.count:
        feature_display = FEATURE_DISPLAY_NAMES.get(request.feature, request.feature)
        raise HTTPException(
            status_code=429,
            detail={
                "success": False,
                "error": "limit_exceeded",
                "upgrade_required": True,
                "message": f"You have reached your {feature_display} limit",
                "usage": usage_stats,
            }
        )
    
    # Track usage
    updated_usage = await _track_usage(user_id, request.feature, tier, request.count, vehicle_count)
    
    return UsageTrackResponse(
        success=True,
        feature=request.feature,
        usage=updated_usage,
        tier=tier,
    )


@router.get("/check/{feature}", response_model=UsageCheckResponse)
async def check_usage(
    feature: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Check if user can use a feature right now.
    
    Returns whether the feature is allowed and current usage stats.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    tier = current_user.get("tier", "free")
    
    # Get vehicle count for premium calculations
    stmt = select(ApiKey).where(
        ApiKey.user_id == user_id,
        ApiKey.status == "active",
    )
    result = await session.execute(stmt)
    api_keys = result.scalars().all()
    vehicle_count = len(set(k.profile_id for k in api_keys if k.profile_id)) or 1
    
    # Check if feature is available for tier
    has_access = _has_feature_access(tier, feature)
    
    # Get usage stats
    usage_stats = await _get_user_usage(user_id, feature, tier, vehicle_count)
    
    # Determine if allowed
    allowed = has_access and (usage_stats["unlimited"] or usage_stats["remaining"] > 0)
    
    reason = None
    message = None
    upgrade_required = False
    
    if not allowed:
        if not has_access:
            reason = "tier_restricted"
            upgrade_required = True
            feature_display = FEATURE_DISPLAY_NAMES.get(feature, feature)
            message = f"Upgrade to Pro for {feature_display} access"
        else:
            reason = "limit_exceeded"
            upgrade_required = True
            message = "You have reached your usage limit"
    
    return UsageCheckResponse(
        success=True,
        allowed=allowed,
        reason=reason,
        usage=usage_stats,
        feature=feature,
        tier=tier,
        upgrade_required=upgrade_required,
        message=message,
    )


@router.get("/all", response_model=AllUsageResponse)
async def get_all_usage(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Get all usage stats for current user.
    
    Returns comprehensive usage information for all tracked features.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    tier = current_user.get("tier", "free")
    
    # Get vehicle count for premium calculations
    stmt = select(ApiKey).where(
        ApiKey.user_id == user_id,
        ApiKey.status == "active",
    )
    result = await session.execute(stmt)
    api_keys = result.scalars().all()
    vehicle_count = len(set(k.profile_id for k in api_keys if k.profile_id)) or 1
    
    # Build usage stats for all features
    usage = {}
    
    for feature in ["daily_obd_requests", "predictions_per_day", "llm_chat_per_day", "pdfs_per_week", "dtc_checks_total"]:
        stats = await _get_user_usage(user_id, feature, tier, vehicle_count)
        usage[feature] = {
            "used": stats["used"],
            "limit": stats["limit"],
            "remaining": stats["remaining"],
            "unlimited": stats["unlimited"],
        }
    
    # Calculate reset times
    now = time.time()
    gm = time.gmtime(now)
    
    # Next midnight
    tomorrow = time.mktime((gm.tm_year, gm.tm_mon, gm.tm_mday + 1, 0, 0, 0, 0, 0, 0))
    
    # Next Sunday midnight
    days_until_sunday = (7 - gm.tm_wday) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sunday = time.mktime((gm.tm_year, gm.tm_mon, gm.tm_mday + days_until_sunday, 0, 0, 0, 0, 0, 0))
    
    return AllUsageResponse(
        success=True,
        tier=tier,
        usage=usage,
        resets_at={
            "daily": tomorrow,
            "weekly": next_sunday,
        },
    )
