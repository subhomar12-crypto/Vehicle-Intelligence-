"""
FCM (Firebase Cloud Messaging) push notification service.

Handles:
- Push notification delivery to Android devices
- Notification channel management
- Circuit breaker for FCM failures
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class FCMService:
    """Firebase Cloud Messaging service with circuit breaker."""

    async def send_notification(
        self,
        fcm_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        channel: str = "default",
    ) -> bool:
        """Send a push notification to a device."""
        # TODO Phase 5: Implement FCM via ARQ background job
        logger.info(f"FCM notification queued: {title}")
        return True

    async def send_to_user(
        self,
        user_id: int,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send notification to a user by looking up their FCM token."""
        # TODO Phase 5: Look up FCM token from users table
        logger.info(f"FCM notification queued for user {user_id}: {title}")
        return True
