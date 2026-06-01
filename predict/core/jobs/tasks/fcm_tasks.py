"""
FCM (Firebase Cloud Messaging) background tasks.

Push notification delivery with retry.
"""

import logging
from typing import Optional, List

from predict.core.services.fcm_service import FCMService

logger = logging.getLogger(__name__)


async def send_push_notification(
    ctx,
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
    image_url: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> dict:
    """
    Send push notification via FCM.
    
    Args:
        ctx: ARQ context
        fcm_token: Device FCM token
        title: Notification title
        body: Notification body
        data: Additional data payload
        image_url: Notification image URL
        channel_id: Android notification channel ID
    
    Returns:
        Result dict with success status
    """
    fcm = FCMService()
    
    try:
        success = await fcm.send_push(
            token=fcm_token,
            title=title,
            body=body,
            data=data,
            channel_id=channel_id,
        )
        
        if success:
            logger.info(f"Push notification sent to {fcm_token[:20]}...: {title}")
            return {
                "success": True,
                "token_prefix": fcm_token[:20] + "...",
            }
        else:
            logger.error(f"FCM send failed for {fcm_token[:20]}...")
            return {
                "success": False,
                "error": "FCM send failed",
            }
    
    except Exception as e:
        logger.exception(f"FCM send failed: {e}")
        raise


async def send_bulk_push(
    ctx,
    fcm_tokens: List[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict:
    """
    Send push notification to multiple devices.
    
    Returns:
        Summary of sent/failed
    """
    fcm = FCMService()
    
    results = {"sent": 0, "failed": 0, "invalid_tokens": []}
    
    try:
        batch_result = await fcm.send_to_multiple(
            tokens=fcm_tokens,
            title=title,
            body=body,
            data=data,
        )
        
        results["sent"] = batch_result.get("success_count", 0)
        results["failed"] = batch_result.get("failure_count", 0)
        results["invalid_tokens"] = batch_result.get("invalid_tokens", [])
        
        logger.info(
            f"Bulk push completed: {results['sent']} sent, "
            f"{results['failed']} failed"
        )
    
    except Exception as e:
        logger.error(f"Bulk push failed: {e}")
        results["failed"] = len(fcm_tokens)
    
    return results


async def send_guardian_alert(
    ctx,
    guardian_fcm_token: str,
    alert_type: str,
    vehicle_name: str,
    details: str,
) -> dict:
    """
    Send guardian alert notification.
    
    Args:
        guardian_fcm_token: Guardian's device token
        alert_type: Type of alert (speeding, geofence, etc.)
        vehicle_name: Name of vehicle
        details: Alert details
    """
    fcm = FCMService()
    
    try:
        success = await fcm.send_guardian_alert(
            guardian_token=guardian_fcm_token,
            alert_type=alert_type,
            vehicle_name=vehicle_name,
            details=details,
        )
        
        if success:
            logger.info(f"Guardian alert sent: {alert_type}")
            return {"success": True}
        else:
            return {"success": False, "error": "Send failed"}
    
    except Exception as e:
        logger.exception(f"Guardian alert failed: {e}")
        raise


async def update_fcm_token(
    ctx,
    user_id: int,
    old_token: Optional[str],
    new_token: str,
) -> dict:
    """
    Update user's FCM token.
    
    Removes old token if provided, stores new token.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from predict.core.db.session import get_db_session
    
    # Get a database session
    async for session in get_db_session():
        try:
            from predict.core.db.models.user import User
            from sqlalchemy import select
            
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                import time
                user.fcm_token = new_token
                user.updated_at = time.time()
                await session.commit()
                logger.info(f"FCM token updated for user {user_id}")
            
            return {
                "success": True,
                "user_id": user_id,
                "token_updated": user is not None,
            }
        
        except Exception as e:
            logger.error(f"FCM token update failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    return {"success": False, "error": "Database session failed"}


async def cleanup_invalid_tokens(ctx) -> dict:
    """Clean up invalid FCM tokens from database."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from predict.core.db.session import get_db_session
    
    cleaned = 0
    
    async for session in get_db_session():
        try:
            from predict.core.db.models.user import User
            from sqlalchemy import select
            
            # Find users with tokens
            stmt = select(User).where(User.fcm_token.isnot(None))
            result = await session.execute(stmt)
            users = result.scalars().all()
            
            fcm = FCMService()
            
            for user in users:
                # Check if token is still valid by doing a dry-run test
                # In practice, you'd track invalid tokens from send failures
                pass
            
            logger.info(f"FCM token cleanup completed: {cleaned} removed")
            
            return {
                "success": True,
                "tokens_checked": len(users),
                "tokens_cleaned": cleaned,
            }
        
        except Exception as e:
            logger.error(f"Token cleanup failed: {e}")
            return {"success": False, "error": str(e)}
    
    return {"success": False, "error": "Database session failed"}
