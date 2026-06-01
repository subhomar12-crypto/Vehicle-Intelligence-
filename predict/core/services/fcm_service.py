"""
FCM (Firebase Cloud Messaging) push notification service.

Handles:
- Push notification delivery to Android devices
- Notification channel management
- Circuit breaker for FCM failures
- Batch sending for multiple devices
"""

import logging
import time
from typing import Optional, Dict, Any, List

import httpx

from predict.core.config import get_config
from predict.core.monitoring.circuit_breaker import circuit_breaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)


class FCMService:
    """Firebase Cloud Messaging service with circuit breaker."""
    
    def __init__(self):
        self.config = get_config()
        self.project_id = getattr(self.config, 'FIREBASE_PROJECT_ID', None)
        self.api_key = getattr(self.config, 'FIREBASE_API_KEY', None)
        self.base_url = f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"
        
        if not self.project_id or not self.api_key:
            logger.warning("FCM not configured - push notifications will be logged only")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get FCM API headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def send_push(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        channel_id: Optional[str] = None,
    ) -> bool:
        """
        Send a push notification to a device.
        
        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Optional data payload
            channel_id: Android notification channel ID
        
        Returns:
            True if sent successfully
        """
        if not self.project_id or not self.api_key:
            logger.info(f"[FCM LOGGED - NO CONFIG] To: {token[:20]}..., Title: {title}")
            return True
        
        payload = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body,
                },
            }
        }
        
        # Add data payload if provided
        if data:
            payload["message"]["data"] = {k: str(v) for k, v in data.items()}
        
        # Add Android-specific config for channel
        if channel_id:
            payload["message"]["android"] = {
                "notification": {
                    "channel_id": channel_id,
                }
            }
        
        try:
            @circuit_breaker("fcm", failure_threshold=5, recovery_timeout=60.0)
            async def _send():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        self.base_url,
                        json=payload,
                        headers=self._get_headers(),
                    )
                    response.raise_for_status()
                    return response.json()
            
            result = await _send()
            logger.debug(f"FCM message sent: {result.get('name', 'unknown')}")
            return True
            
        except CircuitBreakerOpen:
            logger.warning("FCM circuit breaker open - skipping push notification")
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Token invalid/expired
                logger.warning(f"FCM token invalid: {token[:20]}...")
                await self.remove_invalid_token(token)
            else:
                logger.error(f"FCM HTTP error {e.response.status_code}: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"FCM send failed: {e}")
            return False
    
    async def send_to_multiple(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send notification to multiple devices.
        
        Args:
            tokens: List of FCM tokens
            title: Notification title
            body: Notification body
            data: Optional data payload
        
        Returns:
            Dict with success/failure counts
        """
        results = {"sent": 0, "failed": 0, "invalid_tokens": []}
        
        for token in tokens:
            success = await self.send_push(token, title, body, data)
            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1
        
        logger.info(f"FCM batch complete: {results['sent']} sent, {results['failed']} failed")
        return results
    
    async def send_guardian_alert(
        self,
        guardian_token: str,
        alert_type: str,
        alert_data: Dict[str, Any],
    ) -> bool:
        """
        Send guardian-specific alert notification.
        
        Args:
            guardian_token: Guardian's FCM token
            alert_type: Type of alert (speeding, geofence, etc.)
            alert_data: Alert details
        
        Returns:
            True if sent successfully
        """
        # Map alert types to notification channels
        channel_map = {
            "speeding": "guardian_alerts_critical",
            "harsh_braking": "guardian_alerts_warning",
            "harsh_acceleration": "guardian_alerts_warning",
            "geofence_exit": "guardian_alerts_critical",
            "geofence_enter": "guardian_alerts_info",
            "low_battery": "guardian_alerts_warning",
            "engine_alert": "guardian_alerts_critical",
        }
        
        title = alert_data.get("title", f"Guardian Alert: {alert_type}")
        body = alert_data.get("message", "Check your PREDICT app for details.")
        channel = channel_map.get(alert_type, "guardian_alerts")
        
        # Add alert metadata to data payload
        data = {
            "type": alert_type,
            "severity": alert_data.get("severity", "medium"),
            "vehicle_id": str(alert_data.get("vehicle_id", "")),
            "timestamp": str(time.time()),
            "click_action": "OPEN_GUARDIAN_ALERTS",
        }
        
        return await self.send_push(
            token=guardian_token,
            title=title,
            body=body,
            data=data,
            channel_id=channel,
        )
    
    async def remove_invalid_token(self, token: str) -> None:
        """
        Remove or mark an invalid FCM token from the database.
        
        Args:
            token: The invalid FCM token
        """
        logger.info(f"Marking FCM token as invalid: {token[:20]}...")
        # TODO: Update database to clear this token
        # This would typically be done via a repository call
        pass
    
    async def send_to_user(
        self,
        user_id: int,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send notification to a user by looking up their FCM token.

        Args:
            user_id: User ID to send to
            title: Notification title
            body: Notification body
            data: Optional data payload

        Returns:
            True if sent successfully
        """
        try:
            from predict.core.db.session import get_db_session
            from predict.core.db.models.user import User
            from sqlalchemy import select

            async with get_db_session() as session:
                stmt = select(User.fcm_token).where(
                    User.id == user_id,
                )
                result = await session.execute(stmt)
                fcm_token = result.scalar_one_or_none()

            if not fcm_token:
                logger.info(f"No FCM token for user {user_id} - notification skipped")
                return False

            return await self.send_push(
                token=fcm_token,
                title=title,
                body=body,
                data=data,
            )
        except Exception as e:
            logger.error(f"FCM send_to_user failed for user {user_id}: {e}")
            return False
