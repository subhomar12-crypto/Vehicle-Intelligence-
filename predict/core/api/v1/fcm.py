"""
FCM (Firebase Cloud Messaging) token registration API.

Handles:
- Device token registration for push notifications
- Token updates
- Platform-specific handling
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user, get_optional_user
from predict.core.db.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ===== Pydantic Models =====

class FCMRegisterRequest(BaseModel):
    """Request model for FCM token registration."""
    fcm_token: str = Field(..., description="Firebase Cloud Messaging token")
    device_id: str = Field(..., description="Unique device identifier")
    platform: str = Field(default="android", description="Device platform (android, ios)")
    app_name: str = Field(default="PredictOBD", description="App name")
    language: Optional[str] = Field(default=None, description="User language preference")


class FCMRegisterResponse(BaseModel):
    """Response model for FCM registration."""
    success: bool
    message: str
    device_id: Optional[str] = None


# ===== API Endpoints =====

@router.post("/register", response_model=FCMRegisterResponse)
async def register_fcm_token(
    request: FCMRegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Register or update FCM token for push notifications.
    
    Can be called with or without authentication.
    If authenticated, stores token in the user's record.
    If not authenticated, logs the token for potential future use.
    
    Args:
        request: FCM registration data including token and device info
        
    Returns:
        Success confirmation
    """
    try:
        if current_user:
            # Authenticated user - store in user record
            user_id = current_user.get("user_id") or current_user.get("id")
            
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                # Update FCM token
                user.fcm_token = request.fcm_token
                
                # Update language if provided
                if request.language:
                    user.language = request.language
                
                await session.flush()
                
                logger.info(f"FCM token registered for user {user_id}, device {request.device_id}")
                
                return FCMRegisterResponse(
                    success=True,
                    message="FCM token registered successfully",
                    device_id=request.device_id,
                )
            else:
                logger.warning(f"User {user_id} not found for FCM registration")
                # Still return success to not break the app flow
                return FCMRegisterResponse(
                    success=True,
                    message="Token logged (user not found)",
                    device_id=request.device_id,
                )
        else:
            # Anonymous user - just log for now
            # In production, you might want to store in a separate fcm_tokens table
            logger.info(
                f"Anonymous FCM token registration: device={request.device_id}, "
                f"platform={request.platform}, app={request.app_name}"
            )
            
            return FCMRegisterResponse(
                success=True,
                message="FCM token logged (anonymous)",
                device_id=request.device_id,
            )
            
    except Exception as e:
        logger.error(f"FCM registration error: {e}")
        # Return success anyway to not break the app
        return FCMRegisterResponse(
            success=True,
            message="Token registration processed",
            device_id=request.device_id,
        )


@router.post("/unregister", response_model=FCMRegisterResponse)
async def unregister_fcm_token(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Unregister FCM token (clear from user record).
    
    Removes the FCM token from the authenticated user's record.
    
    Returns:
        Success confirmation
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user:
        user.fcm_token = None
        await session.flush()
        
        logger.info(f"FCM token unregistered for user {user_id}")
        
        return FCMRegisterResponse(
            success=True,
            message="FCM token unregistered successfully",
        )
    
    raise HTTPException(status_code=404, detail="User not found")
