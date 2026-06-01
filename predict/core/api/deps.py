"""
FastAPI dependencies for dependency injection.

These dependencies are used across all API routers for:
- Database sessions
- Current user authentication
- Permission checks
"""

import logging
from typing import Optional

from fastapi import Depends, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from predict.core.db.session import get_db
from predict.core.middleware.api_key import extract_api_key, validate_api_key
from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Re-export get_db from session module for use in routers
# Usage: db: AsyncSession = Depends(get_db)
get_db = get_db


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
) -> dict:
    """
    Get current authenticated user from API key or Pi5 device token.

    Checks device token FIRST (Pi5 edge units), then falls back to API key.
    This dependency validates credentials and returns user information.
    It should be used on protected endpoints.
    """
    # --- Device token auth (Pi5 edge units) ---
    if x_device_token:
        import time as _time
        from sqlalchemy import select
        from predict.core.db.models.pi5_device import Pi5Device
        from predict.core.db.session import get_session_maker
        async with get_session_maker()() as db:
            result = await db.execute(
                select(Pi5Device).where(
                    Pi5Device.device_token == x_device_token,
                    Pi5Device.token_expires_at > _time.time(),
                )
            )
            device = result.scalar_one_or_none()
            if device:
                # Refresh token expiry on each use (rolling 90 days)
                device.token_expires_at = _time.time() + 90 * 24 * 60 * 60
                device.last_seen = _time.time()
                await db.commit()
                request.state.user_id = device.user_id
                return {"user_id": device.user_id, "id": device.user_id, "tier": "device"}
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid or expired device token.",
        )

    # --- Standard API key / JWT auth ---
    api_key = extract_api_key(x_api_key=x_api_key, authorization=authorization, request=request)

    if not api_key:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_MISSING_HEADER,
            message="API key required. Use X-API-Key or Authorization header.",
        )

    key_data = await validate_api_key(request)

    if not key_data:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid or expired API key.",
        )

    # Store on request state for later use
    request.state.user_id = key_data.get('user_id')
    request.state.api_key_id = key_data.get('key_id')

    return key_data


async def get_optional_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Optional[dict]:
    """
    Get current user if authenticated, None otherwise.

    Use this for endpoints that work for both authenticated and unauthenticated users.
    """
    api_key = extract_api_key(x_api_key=x_api_key, authorization=authorization, request=request)
    
    if not api_key:
        return None
    
    key_data = await validate_api_key(request)
    
    if key_data:
        request.state.user_id = key_data.get('user_id')
        request.state.api_key_id = key_data.get('key_id')
    
    return key_data


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require admin role."""
    if current_user.get('tier') != 'admin':
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Admin access required.",
        )
    return current_user


def require_tier(min_tier: str):
    """Dependency factory to require minimum subscription tier."""
    tier_order = ['free', 'basic', 'pro', 'premium', 'enterprise', 'admin']
    
    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_tier = current_user.get('tier', 'free')
        
        if user_tier not in tier_order or min_tier not in tier_order:
            raise APIError(
                status_code=403,
                code=ErrorCode.FEATURE_NOT_AVAILABLE,
                message=f"Tier '{min_tier}' or higher required.",
            )
        
        if tier_order.index(user_tier) < tier_order.index(min_tier):
            raise APIError(
                status_code=403,
                code=ErrorCode.FEATURE_NOT_AVAILABLE,
                message=f"Tier '{min_tier}' or higher required.",
                details={
                    'current_tier': user_tier,
                    'required_tier': min_tier,
                },
            )
        
        return current_user
    
    return Depends(checker)


def require_permission(permission: str):
    """Dependency factory to require specific permission."""
    
    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_permissions = current_user.get('permissions', [])
        
        if permission not in user_permissions:
            raise APIError(
                status_code=403,
                code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
                message=f"Permission '{permission}' required.",
                details={
                    'required': permission,
                    'user_permissions': user_permissions,
                },
            )
        
        return current_user
    
    return Depends(checker)
