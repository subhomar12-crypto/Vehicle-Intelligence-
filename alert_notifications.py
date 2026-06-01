"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Alert Notifications

Alert Notification System
Multi-channel notification delivery for alerts and critical events.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod

from config import get_config

# Import audit logging for LLM context
try:
    from notification_audit import NotificationAuditLog, create_prediction_audit_entry, TriggerType
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

CONFIG = get_config()
logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Available notification channels"""
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationPriority(Enum):
    """Notification priority levels"""
    CRITICAL = "critical"  # Immediate delivery, all channels
    HIGH = "high"          # Fast delivery, primary channels
    MEDIUM = "medium"      # Normal delivery
    LOW = "low"            # Batch/digest delivery


class AlertType(Enum):
    """Types of alerts that can trigger notifications"""
    VEHICLE_CRITICAL = "vehicle_critical"
    VEHICLE_WARNING = "vehicle_warning"
    PREDICTION_HIGH_RISK = "prediction_high_risk"
    DEVICE_OFFLINE = "device_offline"
    DEVICE_ONLINE = "device_online"
    SERVICE_DUE = "service_due"
    DTC_DETECTED = "dtc_detected"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SYSTEM_ERROR = "system_error"
    BACKUP_FAILED = "backup_failed"
    AI_TRAINING_COMPLETE = "ai_training_complete"


class NotificationPriorityCalculator:
    """
    Automatically calculates notification priority based on multiple factors.

    Factors considered:
    - Alert type severity
    - Component criticality (engine > brakes > transmission > other)
    - Risk/confidence level from predictions
    - Time sensitivity (how soon action is needed)
    - Vehicle usage patterns (daily driver vs. occasional)
    - Historical accuracy of similar predictions
    """

    # Base priority by alert type
    ALERT_TYPE_PRIORITY = {
        AlertType.VEHICLE_CRITICAL: NotificationPriority.CRITICAL,
        AlertType.SYSTEM_ERROR: NotificationPriority.CRITICAL,
        AlertType.PREDICTION_HIGH_RISK: NotificationPriority.HIGH,
        AlertType.DTC_DETECTED: NotificationPriority.HIGH,
        AlertType.VEHICLE_WARNING: NotificationPriority.MEDIUM,
        AlertType.DEVICE_OFFLINE: NotificationPriority.MEDIUM,
        AlertType.SERVICE_DUE: NotificationPriority.MEDIUM,
        AlertType.BACKUP_FAILED: NotificationPriority.MEDIUM,
        AlertType.SUBSCRIPTION_EXPIRING: NotificationPriority.LOW,
        AlertType.DEVICE_ONLINE: NotificationPriority.LOW,
        AlertType.AI_TRAINING_COMPLETE: NotificationPriority.LOW,
        AlertType.SUBSCRIPTION_EXPIRED: NotificationPriority.HIGH,
    }

    # Component criticality scores (higher = more critical)
    COMPONENT_CRITICALITY = {
        'engine': 100,
        'brakes': 95,
        'brake': 95,
        'transmission': 90,
        'steering': 85,
        'fuel_system': 80,
        'fuel': 80,
        'cooling': 75,
        'coolant': 75,
        'battery': 70,
        'electrical': 65,
        'suspension': 60,
        'exhaust': 55,
        'oil': 50,
        'tire': 45,
        'filter': 40,
        'wiper': 20,
        'light': 15,
    }

    @classmethod
    def calculate_priority(
        cls,
        alert_type: AlertType,
        data: Dict[str, Any] = None
    ) -> NotificationPriority:
        """
        Calculate the appropriate priority for a notification.

        Args:
            alert_type: The type of alert
            data: Additional data containing:
                - component: The vehicle component affected
                - risk_level: Float 0-1 indicating risk
                - confidence: Float 0-1 prediction confidence
                - days_until_failure: Estimated days until failure
                - dtc_severity: DTC code severity level
                - is_safety_related: Boolean for safety issues

        Returns:
            Calculated NotificationPriority
        """
        if data is None:
            data = {}

        # Start with base priority
        base_priority = cls.ALERT_TYPE_PRIORITY.get(alert_type, NotificationPriority.MEDIUM)
        priority_score = cls._priority_to_score(base_priority)

        # Adjust for component criticality
        component = data.get('component', '').lower()
        for comp_key, criticality in cls.COMPONENT_CRITICALITY.items():
            if comp_key in component:
                # Add up to 20 points for critical components
                priority_score += (criticality / 100) * 20
                break

        # Adjust for risk level
        risk_level = data.get('risk_level', 0)
        if risk_level >= 0.9:
            priority_score += 25  # Very high risk
        elif risk_level >= 0.75:
            priority_score += 15
        elif risk_level >= 0.5:
            priority_score += 5

        # Adjust for time sensitivity
        days_until = data.get('days_until_failure')
        if days_until is not None:
            if days_until <= 1:
                priority_score += 30  # Immediate attention needed
            elif days_until <= 7:
                priority_score += 15
            elif days_until <= 14:
                priority_score += 5

        # Safety-related issues always get boost
        if data.get('is_safety_related', False):
            priority_score += 25

        # DTC severity
        dtc_severity = data.get('dtc_severity', '').lower()
        if dtc_severity == 'critical':
            priority_score += 20
        elif dtc_severity == 'serious':
            priority_score += 10

        # Confidence adjustment (lower confidence = slightly lower priority)
        confidence = data.get('confidence', 1.0)
        if confidence < 0.7:
            priority_score -= 10

        # Convert score back to priority
        return cls._score_to_priority(priority_score)

    @classmethod
    def _priority_to_score(cls, priority: NotificationPriority) -> int:
        """Convert priority to numeric score"""
        scores = {
            NotificationPriority.CRITICAL: 100,
            NotificationPriority.HIGH: 70,
            NotificationPriority.MEDIUM: 40,
            NotificationPriority.LOW: 10,
        }
        return scores.get(priority, 40)

    @classmethod
    def _score_to_priority(cls, score: int) -> NotificationPriority:
        """Convert numeric score to priority"""
        if score >= 85:
            return NotificationPriority.CRITICAL
        elif score >= 55:
            return NotificationPriority.HIGH
        elif score >= 25:
            return NotificationPriority.MEDIUM
        else:
            return NotificationPriority.LOW


class NotificationBatcher:
    """
    Batches low-priority notifications to reduce notification fatigue.

    - CRITICAL: Sent immediately, no batching
    - HIGH: Sent within 5 minutes
    - MEDIUM: Batched every 30 minutes
    - LOW: Batched into daily digest
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            app_data = Path.home() / ".predict"
            app_data.mkdir(exist_ok=True)
            db_path = str(app_data / "notification_batch.db")

        self.db_path = db_path
        self._pending_batches: Dict[str, List[Notification]] = {}
        self._batch_timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._send_callback: Optional[Callable[[List[Notification]], None]] = None

        self._init_database()

        # Batch intervals in seconds
        self.batch_intervals = {
            NotificationPriority.CRITICAL: 0,      # Immediate
            NotificationPriority.HIGH: 300,        # 5 minutes
            NotificationPriority.MEDIUM: 1800,     # 30 minutes
            NotificationPriority.LOW: 86400,       # 24 hours (daily digest)
        }

    def _init_database(self):
        """Initialize batch database for persistence"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS pending_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id TEXT UNIQUE,
                recipient_id INTEGER,
                priority TEXT,
                alert_type TEXT,
                title TEXT,
                message TEXT,
                data TEXT,
                channels TEXT,
                created_at TEXT,
                batch_key TEXT
            )
        ''')

        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_batch_key
            ON pending_notifications(batch_key)
        ''')

        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_batch_priority
            ON pending_notifications(priority)
        ''')

        conn.commit()
        conn.close()

    def set_send_callback(self, callback: Callable[[List[Notification]], None]):
        """Set callback to send batched notifications"""
        self._send_callback = callback

    def add_notification(self, notification: Notification) -> bool:
        """
        Add notification to batch or send immediately.

        Returns True if sent immediately, False if batched.
        """
        priority = notification.priority
        interval = self.batch_intervals.get(priority, 0)

        # Critical notifications are never batched
        if interval == 0 or priority == NotificationPriority.CRITICAL:
            return True  # Send immediately

        # Create batch key (recipient + priority)
        batch_key = f"{notification.recipient_id}_{priority.value}"

        with self._lock:
            # Add to pending batch
            if batch_key not in self._pending_batches:
                self._pending_batches[batch_key] = []

            self._pending_batches[batch_key].append(notification)

            # Persist to database
            self._persist_notification(notification, batch_key)

            # Start or reset batch timer
            self._schedule_batch(batch_key, interval)

        logger.debug(f"Notification batched: {notification.notification_id} (batch: {batch_key})")
        return False

    def _persist_notification(self, notification: Notification, batch_key: str):
        """Persist notification to database for crash recovery"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            c.execute('''
                INSERT OR REPLACE INTO pending_notifications
                (notification_id, recipient_id, priority, alert_type, title, message, data, channels, created_at, batch_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                notification.notification_id,
                notification.recipient_id,
                notification.priority.value,
                notification.alert_type.value,
                notification.title,
                notification.message,
                json.dumps(notification.data),
                json.dumps([c.value for c in notification.channels]),
                notification.created_at.isoformat(),
                batch_key
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error persisting notification: {e}")

    def _schedule_batch(self, batch_key: str, interval: int):
        """Schedule batch delivery"""
        # Cancel existing timer if any
        if batch_key in self._batch_timers:
            self._batch_timers[batch_key].cancel()

        # Schedule new timer
        timer = threading.Timer(interval, self._flush_batch, args=[batch_key])
        timer.daemon = True
        timer.start()
        self._batch_timers[batch_key] = timer

    def _flush_batch(self, batch_key: str):
        """Send all notifications in a batch"""
        with self._lock:
            notifications = self._pending_batches.pop(batch_key, [])
            self._batch_timers.pop(batch_key, None)

        if not notifications:
            return

        # Combine into digest if multiple notifications
        if len(notifications) > 1:
            digest = self._create_digest(notifications)
            notifications = [digest]

        # Send via callback
        if self._send_callback:
            try:
                self._send_callback(notifications)
            except Exception as e:
                logger.error(f"Error sending batched notifications: {e}")

        # Clear from database
        self._clear_batch_from_db(batch_key)

    def _create_digest(self, notifications: List[Notification]) -> Notification:
        """Create a digest notification from multiple notifications"""
        import uuid

        recipient_id = notifications[0].recipient_id
        priorities = [n.priority for n in notifications]
        highest_priority = min(priorities, key=lambda p: list(NotificationPriority).index(p))

        # Build digest message
        title = f"PREDICT Summary: {len(notifications)} Notifications"

        messages = []
        for n in notifications:
            messages.append(f"- {n.title}: {n.message}")

        message = "\n".join(messages)

        # Combine all data
        combined_data = {
            'is_digest': True,
            'notification_count': len(notifications),
            'notification_ids': [n.notification_id for n in notifications],
            'notifications': [
                {
                    'id': n.notification_id,
                    'type': n.alert_type.value,
                    'title': n.title,
                    'message': n.message
                }
                for n in notifications
            ]
        }

        # Get all unique channels
        all_channels = set()
        for n in notifications:
            all_channels.update(n.channels)

        return Notification(
            notification_id=str(uuid.uuid4()),
            alert_type=AlertType.VEHICLE_WARNING,  # Generic type for digest
            priority=highest_priority,
            title=title,
            message=message,
            data=combined_data,
            recipient_id=recipient_id,
            channels=list(all_channels),
            created_at=datetime.now()
        )

    def _clear_batch_from_db(self, batch_key: str):
        """Clear sent notifications from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('DELETE FROM pending_notifications WHERE batch_key = ?', (batch_key,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error clearing batch from database: {e}")

    def flush_all(self):
        """Flush all pending batches immediately"""
        with self._lock:
            batch_keys = list(self._pending_batches.keys())

        for batch_key in batch_keys:
            self._flush_batch(batch_key)

    def get_pending_count(self, recipient_id: int = None) -> int:
        """Get count of pending notifications"""
        with self._lock:
            if recipient_id is None:
                return sum(len(batch) for batch in self._pending_batches.values())
            else:
                count = 0
                for key, batch in self._pending_batches.items():
                    if key.startswith(f"{recipient_id}_"):
                        count += len(batch)
                return count

    def recover_pending(self):
        """Recover pending notifications from database after restart"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('SELECT * FROM pending_notifications ORDER BY created_at')
            rows = c.fetchall()
            conn.close()

            for row in rows:
                notification = Notification(
                    notification_id=row['notification_id'],
                    alert_type=AlertType(row['alert_type']),
                    priority=NotificationPriority(row['priority']),
                    title=row['title'],
                    message=row['message'],
                    data=json.loads(row['data']) if row['data'] else {},
                    recipient_id=row['recipient_id'],
                    channels=[NotificationChannel(c) for c in json.loads(row['channels'])],
                    created_at=datetime.fromisoformat(row['created_at'])
                )

                batch_key = row['batch_key']
                with self._lock:
                    if batch_key not in self._pending_batches:
                        self._pending_batches[batch_key] = []
                    self._pending_batches[batch_key].append(notification)

            logger.info(f"Recovered {len(rows)} pending notifications from database")

        except Exception as e:
            logger.error(f"Error recovering pending notifications: {e}")


@dataclass
class Notification:
    """Notification data structure"""
    notification_id: str
    alert_type: AlertType
    priority: NotificationPriority
    title: str
    message: str
    data: Dict[str, Any]
    recipient_id: int  # User or customer ID
    channels: List[NotificationChannel]
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered: bool = False
    error: Optional[str] = None


class NotificationProvider(ABC):
    """Base class for notification providers"""

    @abstractmethod
    def send(self, notification: Notification, config: Dict[str, Any]) -> bool:
        """Send notification via this provider"""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider is properly configured"""
        pass


class EmailProvider(NotificationProvider):
    """Email notification provider"""

    def __init__(self, smtp_config: Dict[str, Any] = None):
        self.config = smtp_config or {}

    def is_configured(self) -> bool:
        required = ['smtp_server', 'smtp_port', 'username', 'password', 'from_address']
        return all(key in self.config for key in required)

    def send(self, notification: Notification, recipient_config: Dict[str, Any]) -> bool:
        if not self.is_configured():
            logger.warning("Email provider not configured")
            return False

        email = recipient_config.get('email')
        if not email:
            logger.warning("No email address for recipient")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[PredictOBD] {notification.title}"
            msg['From'] = self.config['from_address']
            msg['To'] = email

            # Plain text version
            text_content = f"{notification.title}\n\n{notification.message}"

            # HTML version
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #333;">{notification.title}</h2>
                <p style="color: #666; font-size: 14px;">{notification.message}</p>
                <hr style="border: 1px solid #eee;">
                <p style="color: #999; font-size: 12px;">
                    This is an automated notification from PredictOBD.
                </p>
            </body>
            </html>
            """

            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            # Send via SMTP
            with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                server.starttls()
                server.login(self.config['username'], self.config['password'])
                server.send_message(msg)

            logger.info(f"Email sent to {email}: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"Error sending email to {email}: {e}")
            return False


class PushProvider(NotificationProvider):
    """Push notification provider using Firebase Cloud Messaging (FCM)"""

    def __init__(self, push_config: Dict[str, Any] = None):
        self.config = push_config or {}
        self._firebase_app = None
        self._initialized = False

    def is_configured(self) -> bool:
        """Check if Firebase is properly configured"""
        return 'credentials_path' in self.config or 'server_key' in self.config

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        if self._initialized:
            return

        try:
            import firebase_admin
            from firebase_admin import credentials, messaging

            # Initialize Firebase with credentials file
            if 'credentials_path' in self.config:
                cred_path = self.config['credentials_path']
                if Path(cred_path).exists():
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    self._initialized = True
                    logger.info(f"Firebase initialized with credentials: {cred_path}")
                else:
                    logger.warning(f"Firebase credentials file not found: {cred_path}")

        except ImportError:
            logger.warning("firebase-admin not installed. Install with: pip install firebase-admin")
        except Exception as e:
            logger.error(f"Error initializing Firebase: {e}")

    def send(self, notification: Notification, recipient_config: Dict[str, Any]) -> bool:
        """Send push notification via FCM"""
        if not self.is_configured():
            logger.debug("Push provider not configured")
            return False

        push_token = recipient_config.get('push_token')
        if not push_token:
            logger.debug("No push token for recipient")
            return False

        try:
            # Try Firebase Admin SDK first
            import firebase_admin
            from firebase_admin import messaging

            if not self._initialized:
                self._initialize_firebase()

            if not self._initialized:
                # Fallback to legacy FCM API with server key
                return self._send_via_fcm_legacy(notification, push_token)

            # Send via Firebase Admin SDK
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification.title,
                    body=notification.message
                ),
                data=notification.data or {},
                token=push_token,
                android=messaging.AndroidConfig(
                    priority='high' if notification.priority == NotificationPriority.CRITICAL else 'normal',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        priority='high' if notification.priority == NotificationPriority.CRITICAL else 'normal'
                    )
                )
            )

            response = messaging.send(message)
            logger.info(f"Push notification sent: {notification.title} (ID: {response})")
            return True

        except ImportError:
            logger.warning("firebase-admin not installed. Install with: pip install firebase-admin")
            return False
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            return False

    def _send_via_fcm_legacy(self, notification: Notification, push_token: str) -> bool:
        """Send via legacy FCM HTTP API (fallback)"""
        if 'server_key' not in self.config:
            logger.warning("No FCM server key configured")
            return False

        try:
            import requests

            url = f"https://fcm.googleapis.com/fcm/send"
            headers = {
                'Authorization': f"key={self.config['server_key']}",
                'Content-Type': 'application/json'
            }

            payload = {
                'to': push_token,
                'notification': {
                    'title': notification.title,
                    'body': notification.message,
                    'sound': 'default'
                },
                'data': notification.data or {}
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)
            success = response.status_code == 200

            if success:
                logger.info(f"Push notification sent via legacy API: {notification.title}")
            else:
                logger.warning(f"FCM legacy API failed: {response.status_code} - {response.text}")

            return success

        except Exception as e:
            logger.error(f"Error sending push via legacy API: {e}")
            return False


class SMSProvider(NotificationProvider):
    """SMS notification provider using Twilio"""

    def __init__(self, sms_config: Dict[str, Any] = None):
        self.config = sms_config or {}
        self._client = None
        self._initialized = False

    def is_configured(self) -> bool:
        """Check if Twilio is properly configured"""
        return ('account_sid' in self.config and 'auth_token' in self.config and
                'from_number' in self.config)

    def _initialize_twilio(self):
        """Initialize Twilio client"""
        if self._initialized:
            return

        try:
            from twilio.rest import Client

            self._client = Client(
                self.config['account_sid'],
                self.config['auth_token']
            )
            self._initialized = True
            logger.info(f"Twilio client initialized")

        except ImportError:
            logger.warning("twilio not installed. Install with: pip install twilio")
        except Exception as e:
            logger.error(f"Error initializing Twilio: {e}")

    def send(self, notification: Notification, recipient_config: Dict[str, Any]) -> bool:
        """Send SMS notification via Twilio"""
        if not self.is_configured():
            logger.debug("SMS provider not configured")
            return False

        phone = recipient_config.get('phone')
        if not phone:
            logger.debug("No phone number for recipient")
            return False

        try:
            # Initialize Twilio client if needed
            if not self._initialized:
                self._initialize_twilio()

            if not self._initialized or not self._client:
                logger.warning("Twilio client not available")
                return False

            # Format phone number (ensure it has + prefix)
            if not phone.startswith('+'):
                phone = '+' + phone  # Just add the plus sign

            # Create SMS message
            message_body = f"[PREDICT] {notification.title}\n{notification.message}"

            # Send SMS
            message = self._client.messages.create(
                body=message_body,
                from_=self.config['from_number'],
                to=phone
            )

            logger.info(f"SMS sent to {phone}: {notification.title} (SID: {message.sid})")
            return True

        except ImportError:
            logger.warning("twilio not installed. Install with: pip install twilio")
            return False
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return False


class WebhookProvider(NotificationProvider):
    """Webhook notification provider"""

    def __init__(self):
        pass

    def is_configured(self) -> bool:
        return True  # Webhook URLs come from recipient config

    def send(self, notification: Notification, recipient_config: Dict[str, Any]) -> bool:
        webhook_url = recipient_config.get('webhook_url')
        if not webhook_url:
            return False

        try:
            import requests

            payload = {
                'notification_id': notification.notification_id,
                'type': notification.alert_type.value,
                'priority': notification.priority.value,
                'title': notification.title,
                'message': notification.message,
                'data': notification.data,
                'timestamp': notification.created_at.isoformat()
            }

            response = requests.post(webhook_url, json=payload, timeout=10)
            success = response.status_code == 200

            if success:
                logger.info(f"Webhook delivered to {webhook_url}")
            else:
                logger.warning(f"Webhook failed: {response.status_code}")

            return success

        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            return False


class AlertNotificationManager:
    """
    Central manager for alert notifications.

    Features:
    - Multi-channel delivery (email, push, SMS, webhook)
    - Priority-based routing with automatic priority calculation
    - Delivery tracking and retry
    - User notification preferences
    - Rate limiting and intelligent batching
    - Audit logging for LLM context
    """

    def __init__(self):
        self.db_path = CONFIG.DATA_DIR / "notifications.db"
        self.config_file = CONFIG.CONFIG_DIR / "notification_config.json"

        self.providers: Dict[NotificationChannel, NotificationProvider] = {}
        self._notification_queue: List[Notification] = []
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[Notification], None]] = []
        self._running = False

        # Initialize priority calculator and batcher
        self.priority_calculator = NotificationPriorityCalculator()
        self.batcher = NotificationBatcher()
        self.batcher.set_send_callback(self._send_batched_notifications)

        # Initialize audit log for LLM context
        self.audit_log = NotificationAuditLog() if AUDIT_AVAILABLE else None

        self._init_database()
        self._load_config()
        self._init_providers()

        # Recover any pending batched notifications
        self.batcher.recover_pending()

        logger.info("AlertNotificationManager initialized with priority calculator and batcher")

    def _init_database(self):
        """Initialize notifications database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        # Notifications history
        c.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY,
                alert_type TEXT,
                priority TEXT,
                title TEXT,
                message TEXT,
                data TEXT,
                recipient_id INTEGER,
                channels TEXT,
                created_at TEXT,
                sent_at TEXT,
                delivered INTEGER DEFAULT 0,
                error TEXT
            )
        ''')

        # User notification preferences
        c.execute('''
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id INTEGER PRIMARY KEY,
                email_enabled INTEGER DEFAULT 1,
                push_enabled INTEGER DEFAULT 1,
                sms_enabled INTEGER DEFAULT 0,
                webhook_url TEXT,
                quiet_hours_start TEXT,
                quiet_hours_end TEXT,
                alert_types TEXT
            )
        ''')

        # Rate limiting
        c.execute('''
            CREATE TABLE IF NOT EXISTS notification_rate_limits (
                user_id INTEGER,
                alert_type TEXT,
                last_sent TEXT,
                count_today INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, alert_type)
            )
        ''')

        conn.commit()
        conn.close()

    def _load_config(self):
        """Load notification configuration"""
        self.config = {
            'email': {},
            'push': {},
            'sms': {},
            'rate_limits': {
                'max_per_hour': 10,
                'max_per_day': 50
            }
        }

        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self.config.update(json.load(f))
        except Exception as e:
            logger.error(f"Error loading notification config: {e}")

    def _init_providers(self):
        """Initialize notification providers"""
        self.providers[NotificationChannel.EMAIL] = EmailProvider(self.config.get('email', {}))
        self.providers[NotificationChannel.PUSH] = PushProvider(self.config.get('push', {}))
        self.providers[NotificationChannel.SMS] = SMSProvider(self.config.get('sms', {}))
        self.providers[NotificationChannel.WEBHOOK] = WebhookProvider()

    def register_callback(self, callback: Callable[[Notification], None]):
        """Register callback for in-app notifications"""
        with self._lock:
            self._callbacks.append(callback)

    def send_notification(self, alert_type: AlertType, priority: NotificationPriority = None,
                          title: str = "", message: str = "", recipient_id: int = 0,
                          data: Dict[str, Any] = None,
                          channels: List[NotificationChannel] = None,
                          auto_calculate_priority: bool = True,
                          profile_id: str = None,
                          vehicle_id: str = None,
                          driver_id: str = None) -> str:
        """
        Send a notification to a user.

        Args:
            alert_type: Type of alert
            priority: Notification priority (auto-calculated if None and auto_calculate_priority=True)
            title: Notification title
            message: Notification message
            recipient_id: User/customer ID
            data: Additional data to include
            channels: Specific channels to use (defaults to user preferences)
            auto_calculate_priority: If True, calculate priority from data when not specified
            profile_id: Profile ID for audit logging
            vehicle_id: Vehicle ID for audit logging
            driver_id: Driver ID for audit logging

        Returns:
            notification_id
        """
        import uuid

        notification_id = str(uuid.uuid4())
        data = data or {}

        # Auto-calculate priority if not specified
        if priority is None and auto_calculate_priority:
            priority = self.priority_calculator.calculate_priority(alert_type, data)
            logger.debug(f"Auto-calculated priority: {priority.value} for {alert_type.value}")
        elif priority is None:
            priority = NotificationPriority.MEDIUM

        # Get user preferences if channels not specified
        if channels is None:
            channels = self._get_user_channels(recipient_id, alert_type)

        notification = Notification(
            notification_id=notification_id,
            alert_type=alert_type,
            priority=priority,
            title=title,
            message=message,
            data=data,
            recipient_id=recipient_id,
            channels=channels,
            created_at=datetime.now()
        )

        # Check rate limits
        if not self._check_rate_limit(recipient_id, alert_type):
            logger.warning(f"Rate limit exceeded for user {recipient_id}, alert {alert_type.value}")
            notification.error = "Rate limit exceeded"
            self._save_notification(notification)
            return notification_id

        # Log to audit system for LLM context
        audit_id = None
        if self.audit_log and AUDIT_AVAILABLE:
            try:
                # Determine trigger type from alert type
                trigger_type = self._get_trigger_type(alert_type)

                audit_id = self.audit_log.log_notification(
                    notification_id=notification_id,
                    recipient_id=str(recipient_id),
                    recipient_type="owner",  # Default, can be overridden
                    profile_id=profile_id or data.get('profile_id'),
                    vehicle_id=vehicle_id or data.get('vehicle_id'),
                    driver_id=driver_id or data.get('driver_id'),
                    trigger_type=trigger_type,
                    trigger_data=data,
                    priority=priority.value,
                    title=title,
                    message=message,
                    channels=[c.value for c in channels]
                )
                logger.debug(f"Notification logged to audit: {audit_id}")
            except Exception as e:
                logger.error(f"Error logging notification to audit: {e}")

        # Check if notification should be batched
        send_immediately = self.batcher.add_notification(notification)

        if send_immediately:
            # Send immediately for critical/high priority
            delivered, errors = self._deliver_notification(notification)

            # Update notification status
            notification.sent_at = datetime.now()
            notification.delivered = delivered
            notification.error = "; ".join(errors) if errors else None

            # Save to database
            self._save_notification(notification)

            # Update audit with delivery status
            if self.audit_log and audit_id:
                try:
                    self.audit_log.update_delivery_status(
                        notification_id=notification_id,
                        channel="multi",
                        status="delivered" if delivered else "failed",
                        error=notification.error
                    )
                except Exception as e:
                    logger.error(f"Error updating audit delivery status: {e}")
        else:
            # Notification is batched, save as pending
            notification.error = "Batched for later delivery"
            self._save_notification(notification)
            logger.info(f"Notification {notification_id} batched (priority: {priority.value})")

        # Update rate limit
        self._update_rate_limit(recipient_id, alert_type)

        return notification_id

    def _get_trigger_type(self, alert_type: AlertType):
        """Map alert type to trigger type for audit logging"""
        if not AUDIT_AVAILABLE:
            return None

        mapping = {
            AlertType.PREDICTION_HIGH_RISK: TriggerType.PREDICTION,
            AlertType.VEHICLE_CRITICAL: TriggerType.THRESHOLD,
            AlertType.VEHICLE_WARNING: TriggerType.THRESHOLD,
            AlertType.DTC_DETECTED: TriggerType.DTC_CODE,
            AlertType.DEVICE_OFFLINE: TriggerType.DEVICE_STATUS,
            AlertType.DEVICE_ONLINE: TriggerType.DEVICE_STATUS,
            AlertType.SERVICE_DUE: TriggerType.SCHEDULED,
            AlertType.SUBSCRIPTION_EXPIRING: TriggerType.SCHEDULED,
            AlertType.SUBSCRIPTION_EXPIRED: TriggerType.SCHEDULED,
            AlertType.AI_TRAINING_COMPLETE: TriggerType.SYSTEM,
            AlertType.SYSTEM_ERROR: TriggerType.SYSTEM,
            AlertType.BACKUP_FAILED: TriggerType.SYSTEM,
        }
        return mapping.get(alert_type, TriggerType.MANUAL)

    def _deliver_notification(self, notification: Notification) -> tuple:
        """Deliver notification through all channels. Returns (delivered, errors)."""
        delivered = False
        errors = []

        for channel in notification.channels:
            try:
                provider = self.providers.get(channel)
                if provider and provider.is_configured():
                    recipient_config = self._get_recipient_config(notification.recipient_id, channel)
                    if provider.send(notification, recipient_config):
                        delivered = True
                    else:
                        errors.append(f"{channel.value}: delivery failed")
                else:
                    errors.append(f"{channel.value}: not configured")
            except Exception as e:
                errors.append(f"{channel.value}: {str(e)}")

        # Handle in-app notifications
        if NotificationChannel.IN_APP in notification.channels:
            self._deliver_in_app(notification)
            delivered = True

        return delivered, errors

    def _send_batched_notifications(self, notifications: List[Notification]):
        """Callback to send batched notifications"""
        for notification in notifications:
            delivered, errors = self._deliver_notification(notification)

            notification.sent_at = datetime.now()
            notification.delivered = delivered
            notification.error = "; ".join(errors) if errors else None

            self._save_notification(notification)

            # Update audit log
            if self.audit_log:
                try:
                    self.audit_log.update_delivery_status(
                        notification_id=notification.notification_id,
                        channel="multi",
                        status="delivered" if delivered else "failed",
                        error=notification.error
                    )
                except Exception as e:
                    logger.error(f"Error updating audit for batched notification: {e}")

    def send_bulk_notification(self, alert_type: AlertType, priority: NotificationPriority,
                               title: str, message: str, recipient_ids: List[int],
                               data: Dict[str, Any] = None) -> List[str]:
        """Send notification to multiple recipients"""
        notification_ids = []
        for recipient_id in recipient_ids:
            nid = self.send_notification(
                alert_type=alert_type,
                priority=priority,
                title=title,
                message=message,
                recipient_id=recipient_id,
                data=data
            )
            notification_ids.append(nid)
        return notification_ids

    def _get_user_channels(self, user_id: int, alert_type: AlertType) -> List[NotificationChannel]:
        """Get enabled notification channels for a user"""
        channels = []

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('SELECT * FROM notification_preferences WHERE user_id = ?', (user_id,))
            row = c.fetchone()
            conn.close()

            if row:
                if row['email_enabled']:
                    channels.append(NotificationChannel.EMAIL)
                if row['push_enabled']:
                    channels.append(NotificationChannel.PUSH)
                if row['sms_enabled']:
                    channels.append(NotificationChannel.SMS)
                if row['webhook_url']:
                    channels.append(NotificationChannel.WEBHOOK)
            else:
                # Default: email and in-app
                channels = [NotificationChannel.EMAIL, NotificationChannel.IN_APP]

        except Exception as e:
            logger.error(f"Error getting user channels: {e}")
            channels = [NotificationChannel.IN_APP]

        channels.append(NotificationChannel.IN_APP)  # Always include in-app
        return list(set(channels))

    def _get_recipient_config(self, user_id: int, channel: NotificationChannel) -> Dict[str, Any]:
        """Get recipient configuration for a channel"""
        config = {}

        try:
            # Get from user preferences
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('SELECT * FROM notification_preferences WHERE user_id = ?', (user_id,))
            row = c.fetchone()

            if row:
                config['webhook_url'] = row['webhook_url']

            # Get from RBAC user data
            from rbac import get_rbac_manager
            rbac = get_rbac_manager()

            rbac_conn = sqlite3.connect(str(rbac.db_path))
            rbac_conn.row_factory = sqlite3.Row
            rbac_c = rbac_conn.cursor()

            rbac_c.execute('SELECT email FROM users WHERE user_id = ?', (user_id,))
            user_row = rbac_c.fetchone()
            if user_row:
                config['email'] = user_row['email']

            rbac_conn.close()
            conn.close()

        except Exception as e:
            logger.error(f"Error getting recipient config: {e}")

        return config

    def _check_rate_limit(self, user_id: int, alert_type: AlertType) -> bool:
        """Check if notification would exceed rate limit"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                SELECT count_today FROM notification_rate_limits
                WHERE user_id = ? AND alert_type = ?
            ''', (user_id, alert_type.value))

            row = c.fetchone()
            conn.close()

            if row:
                max_daily = self.config.get('rate_limits', {}).get('max_per_day', 50)
                return row[0] < max_daily

            return True

        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True

    def _update_rate_limit(self, user_id: int, alert_type: AlertType):
        """Update rate limit counter"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT INTO notification_rate_limits (user_id, alert_type, last_sent, count_today)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, alert_type) DO UPDATE SET
                    last_sent = excluded.last_sent,
                    count_today = count_today + 1
            ''', (user_id, alert_type.value, datetime.now().isoformat()))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error updating rate limit: {e}")

    def _deliver_in_app(self, notification: Notification):
        """Deliver notification via in-app callbacks"""
        for callback in self._callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}")

    def _save_notification(self, notification: Notification):
        """Save notification to database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT OR REPLACE INTO notifications
                (notification_id, alert_type, priority, title, message, data,
                 recipient_id, channels, created_at, sent_at, delivered, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                notification.notification_id,
                notification.alert_type.value,
                notification.priority.value,
                notification.title,
                notification.message,
                json.dumps(notification.data),
                notification.recipient_id,
                json.dumps([c.value for c in notification.channels]),
                notification.created_at.isoformat(),
                notification.sent_at.isoformat() if notification.sent_at else None,
                1 if notification.delivered else 0,
                notification.error
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error saving notification: {e}")

    def get_user_notifications(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get notifications for a user"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('''
                SELECT * FROM notifications
                WHERE recipient_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))

            rows = c.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []

    def set_user_preferences(self, user_id: int, email_enabled: bool = True,
                             push_enabled: bool = True, sms_enabled: bool = False,
                             webhook_url: str = None):
        """Set notification preferences for a user"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT OR REPLACE INTO notification_preferences
                (user_id, email_enabled, push_enabled, sms_enabled, webhook_url)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 1 if email_enabled else 0, 1 if push_enabled else 0,
                  1 if sms_enabled else 0, webhook_url))

            conn.commit()
            conn.close()

            logger.info(f"Updated notification preferences for user {user_id}")

        except Exception as e:
            logger.error(f"Error setting user preferences: {e}")

    def configure_channel(self, channel: NotificationChannel, config: Dict[str, Any]):
        """Configure a notification channel with provider settings"""
        try:
            if channel in self.providers:
                # Re-initialize provider with new config
                if channel == NotificationChannel.EMAIL:
                    self.providers[channel] = EmailProvider(config)
                elif channel == NotificationChannel.PUSH:
                    self.providers[channel] = PushProvider(config)
                elif channel == NotificationChannel.SMS:
                    self.providers[channel] = SMSProvider(config)
                
                # Update config and save
                channel_name = channel.value
                if 'channels' not in self.config:
                    self.config['channels'] = {}
                self.config['channels'][channel_name] = config
                
                # Save to config file
                self.config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
                
                logger.info(f"Configured {channel_name} channel")
            else:
                logger.warning(f"Unknown channel: {channel}")
        except Exception as e:
            logger.error(f"Error configuring channel {channel}: {e}")

    def start(self):
        """Start the notification manager (background processing)"""
        if self._running:
            logger.warning("Notification manager already running")
            return
        
        self._running = True
        logger.info("AlertNotificationManager started")

    def stop(self):
        """Stop the notification manager"""
        self._running = False
        logger.info("AlertNotificationManager stopped")


# Singleton instance
_notification_manager: Optional[AlertNotificationManager] = None


def get_notification_manager() -> AlertNotificationManager:
    """Get the singleton AlertNotificationManager instance."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = AlertNotificationManager()
    return _notification_manager


# Convenience functions for common notifications
def notify_vehicle_critical(recipient_id: int, vehicle_name: str, issue: str, data: Dict = None):
    """Send critical vehicle alert"""
    manager = get_notification_manager()
    return manager.send_notification(
        alert_type=AlertType.VEHICLE_CRITICAL,
        priority=NotificationPriority.CRITICAL,
        title=f"Critical Alert: {vehicle_name}",
        message=issue,
        recipient_id=recipient_id,
        data=data
    )


def notify_device_offline(recipient_id: int, device_id: str, data: Dict = None):
    """Send device offline notification"""
    manager = get_notification_manager()
    return manager.send_notification(
        alert_type=AlertType.DEVICE_OFFLINE,
        priority=NotificationPriority.MEDIUM,
        title="Device Disconnected",
        message=f"Device {device_id} has gone offline",
        recipient_id=recipient_id,
        data=data
    )


def notify_prediction_risk(recipient_id: int, vehicle_name: str, component: str,
                           risk_level: float, data: Dict = None):
    """Send high-risk prediction notification"""
    manager = get_notification_manager()
    return manager.send_notification(
        alert_type=AlertType.PREDICTION_HIGH_RISK,
        priority=NotificationPriority.HIGH,
        title=f"High Risk Detected: {vehicle_name}",
        message=f"{component} shows {risk_level:.0%} failure risk",
        recipient_id=recipient_id,
        data=data
    )


def notify_prediction_auto_priority(
    recipient_id: int,
    vehicle_name: str,
    component: str,
    risk_level: float,
    confidence: float = 1.0,
    days_until_failure: int = None,
    is_safety_related: bool = False,
    profile_id: str = None,
    vehicle_id: str = None,
    driver_id: str = None,
    data: Dict = None
):
    """
    Send prediction notification with auto-calculated priority.

    Priority is calculated based on:
    - Component criticality (engine, brakes more critical)
    - Risk level (higher risk = higher priority)
    - Time until predicted failure
    - Whether it's safety-related
    """
    manager = get_notification_manager()

    # Build data for priority calculation
    notification_data = data or {}
    notification_data.update({
        'component': component,
        'risk_level': risk_level,
        'confidence': confidence,
        'is_safety_related': is_safety_related,
        'vehicle_name': vehicle_name,
        'profile_id': profile_id,
        'vehicle_id': vehicle_id,
        'driver_id': driver_id,
    })
    if days_until_failure is not None:
        notification_data['days_until_failure'] = days_until_failure

    return manager.send_notification(
        alert_type=AlertType.PREDICTION_HIGH_RISK,
        priority=None,  # Auto-calculate
        title=f"Prediction Alert: {vehicle_name}",
        message=f"{component} shows {risk_level:.0%} failure risk" +
                (f" within {days_until_failure} days" if days_until_failure else ""),
        recipient_id=recipient_id,
        data=notification_data,
        auto_calculate_priority=True,
        profile_id=profile_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id
    )


def notify_dtc_detected(
    recipient_id: int,
    vehicle_name: str,
    dtc_code: str,
    dtc_description: str,
    severity: str = "medium",
    profile_id: str = None,
    vehicle_id: str = None,
    data: Dict = None
):
    """Send DTC detection notification with auto-calculated priority"""
    manager = get_notification_manager()

    notification_data = data or {}
    notification_data.update({
        'dtc_code': dtc_code,
        'dtc_description': dtc_description,
        'dtc_severity': severity,
        'vehicle_name': vehicle_name,
    })

    return manager.send_notification(
        alert_type=AlertType.DTC_DETECTED,
        priority=None,  # Auto-calculate based on severity
        title=f"DTC Detected: {vehicle_name}",
        message=f"Code {dtc_code}: {dtc_description}",
        recipient_id=recipient_id,
        data=notification_data,
        auto_calculate_priority=True,
        profile_id=profile_id,
        vehicle_id=vehicle_id
    )


def notify_service_due(
    recipient_id: int,
    vehicle_name: str,
    service_type: str,
    due_date: str = None,
    mileage_remaining: int = None,
    profile_id: str = None,
    vehicle_id: str = None,
    data: Dict = None
):
    """Send service due notification"""
    manager = get_notification_manager()

    message_parts = [f"{service_type} service is due"]
    if due_date:
        message_parts.append(f"by {due_date}")
    if mileage_remaining:
        message_parts.append(f"or in {mileage_remaining:,} km")

    notification_data = data or {}
    notification_data.update({
        'service_type': service_type,
        'due_date': due_date,
        'mileage_remaining': mileage_remaining,
        'vehicle_name': vehicle_name,
    })

    return manager.send_notification(
        alert_type=AlertType.SERVICE_DUE,
        priority=NotificationPriority.MEDIUM,
        title=f"Service Due: {vehicle_name}",
        message=" ".join(message_parts),
        recipient_id=recipient_id,
        data=notification_data,
        profile_id=profile_id,
        vehicle_id=vehicle_id
    )


# Export new classes for external use
__all__ = [
    'NotificationChannel',
    'NotificationPriority',
    'AlertType',
    'Notification',
    'NotificationPriorityCalculator',
    'NotificationBatcher',
    'AlertNotificationManager',
    'get_notification_manager',
    'notify_vehicle_critical',
    'notify_device_offline',
    'notify_prediction_risk',
    'notify_prediction_auto_priority',
    'notify_dtc_detected',
    'notify_service_due',
]
