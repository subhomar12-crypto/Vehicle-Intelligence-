"""
API key authentication middleware.
Preserves exact Permission, Tier, AppType enums for Android compatibility.

Key changes from original:
- bcrypt primary + SHA-256 fallback (30-day migration)
- Redis cache for validated keys (<10ms)
- Async database queries instead of file reads
"""

import hashlib
import logging
import time
from enum import Enum
from typing import Optional, Dict, Any, List

from fastapi import Header, Request, Depends

from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)


class Permission(Enum):
    """Available permissions. Preserved exactly from original server."""
    VEHICLE_DATA = "vehicle_data"
    PREDICT = "predict"
    DIAGNOSTIC = "diagnostic"
    LLM_CHAT = "llm_chat"
    ADMIN = "admin"
    REPORTS = "reports"
    GUARDIAN = "guardian"


class Tier(Enum):
    """Subscription tiers. Preserved exactly from original server."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    PREMIUM = "premium"
    ADMIN = "admin"
    FLEET_DRIVER = "fleet_driver"
    FLEET_MANAGER = "fleet_manager"
    ENTERPRISE = "enterprise"


class AppType(Enum):
    """Supported mobile apps. Preserved exactly from original server."""
    OBD = "obd"
    GUARDIAN = "guardian"
    ALL = "all"


# Tier permission mappings — preserved exactly
TIER_PERMISSIONS: Dict[Tier, List[Permission]] = {
    Tier.FREE: [Permission.VEHICLE_DATA, Permission.DIAGNOSTIC],
    Tier.BASIC: [Permission.VEHICLE_DATA, Permission.DIAGNOSTIC, Permission.PREDICT],
    Tier.PRO: [Permission.VEHICLE_DATA, Permission.DIAGNOSTIC, Permission.PREDICT,
               Permission.LLM_CHAT],
    Tier.PREMIUM: [Permission.VEHICLE_DATA, Permission.DIAGNOSTIC, Permission.PREDICT,
                   Permission.LLM_CHAT, Permission.REPORTS],
    Tier.ADMIN: list(Permission),
    Tier.FLEET_DRIVER: [Permission.VEHICLE_DATA, Permission.DIAGNOSTIC, Permission.PREDICT],
    Tier.FLEET_MANAGER: [Permission.VEHICLE_DATA, Permission.DIAGNOSTIC, Permission.PREDICT,
                         Permission.LLM_CHAT, Permission.REPORTS, Permission.GUARDIAN],
    Tier.ENTERPRISE: list(Permission),
}


def hash_api_key_sha256(api_key: str) -> str:
    """Legacy SHA-256 hash for migration fallback."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def extract_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract API key from X-API-Key or Authorization: Bearer header."""
    if x_api_key:
        return x_api_key
    if authorization:
        if authorization.startswith("Bearer "):
            return authorization[7:]
        return authorization
    return None


async def validate_api_key(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency that validates the API key.

    Checks:
    1. Redis cache (fastest, <1ms)
    2. bcrypt hash in database (primary)
    3. SHA-256 hash fallback (30-day migration, auto-upgrades to bcrypt)

    Returns dict with user info (tier, permissions, profile_id, etc.)
    """
    api_key = extract_api_key(
        x_api_key=request.headers.get("X-API-Key"),
        authorization=request.headers.get("Authorization"),
    )

    if not api_key:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_MISSING_HEADER,
            message="API key required. Use X-API-Key or Authorization: Bearer header.",
        )

    if not api_key.strip():
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_EMPTY_KEY,
            message="API key cannot be empty.",
        )

    # TODO Phase 4: Check Redis cache first
    # cached = await redis_cache.get_api_key(api_key)
    # if cached: return cached

    # TODO Phase 2+: Query database for key validation
    # For now, return a placeholder that will be replaced in Phase 3
    key_data = await _lookup_api_key(api_key)

    if not key_data:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid API key.",
        )

    # Store validated key data on request state
    request.state.api_key_data = key_data
    return key_data


async def _lookup_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """
    Look up API key in database.
    Placeholder until Phase 3 wires up database queries.
    """
    # This will be implemented when auth_service.py is created
    # For now, allow admin key from environment
    import os
    admin_key = os.environ.get("ADMIN_API_KEY", "")
    if admin_key and api_key == admin_key:
        return {
            "key_id": "admin",
            "user_id": 1,
            "name": "Admin",
            "tier": Tier.ADMIN.value,
            "permissions": [p.value for p in Permission],
            "apps": [AppType.ALL.value],
            "profile_id": None,
        }
    return None


def require_permission(permission: Permission):
    """Dependency factory: require a specific permission."""

    async def checker(request: Request):
        key_data = getattr(request.state, "api_key_data", None)
        if not key_data:
            raise APIError(
                status_code=401,
                code=ErrorCode.AUTH_INVALID_KEY,
                message="Not authenticated.",
            )

        user_permissions = key_data.get("permissions", [])
        if permission.value not in user_permissions:
            raise APIError(
                status_code=403,
                code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
                message=f"Permission '{permission.value}' required.",
                details={"required": permission.value, "tier": key_data.get("tier")},
            )
        return key_data

    return Depends(checker)


def require_tier(min_tier: Tier):
    """Dependency factory: require minimum subscription tier."""
    tier_order = [Tier.FREE, Tier.BASIC, Tier.PRO, Tier.PREMIUM, Tier.ADMIN]

    async def checker(request: Request):
        key_data = getattr(request.state, "api_key_data", None)
        if not key_data:
            raise APIError(
                status_code=401,
                code=ErrorCode.AUTH_INVALID_KEY,
                message="Not authenticated.",
            )

        user_tier_str = key_data.get("tier", "free")
        try:
            user_tier = Tier(user_tier_str)
        except ValueError:
            user_tier = Tier.FREE

        if user_tier in tier_order and min_tier in tier_order:
            if tier_order.index(user_tier) < tier_order.index(min_tier):
                raise APIError(
                    status_code=403,
                    code=ErrorCode.FEATURE_NOT_AVAILABLE,
                    message=f"Tier '{min_tier.value}' or higher required.",
                    details={"current_tier": user_tier.value, "required_tier": min_tier.value},
                )

        return key_data

    return Depends(checker)
