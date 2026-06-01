"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Module: Notification Audit Log
Purpose: Store every notification with full context for LLM queries and explanation

This module provides audit logging for all notifications sent, including:
- Full trigger data (predictions, thresholds, etc.)
- Delivery status across channels
- User actions and outcomes
- LLM explanation context
"""

import sqlite3
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels"""
    CRITICAL = "critical"  # Immediate push to all channels
    HIGH = "high"          # Push notification
    MEDIUM = "medium"      # In-app + email digest
    LOW = "low"            # In-app only


class TriggerType(Enum):
    """Types of events that trigger notifications"""
    PREDICTION = "prediction"
    DTC = "dtc"
    THRESHOLD = "threshold"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    SYSTEM = "system"


@dataclass
class NotificationAuditEntry:
    """Complete audit record for a notification"""
    notification_id: str
    recipient_id: int
    recipient_type: str  # 'owner' or 'driver'
    title: str
    message: str
    priority: str
    trigger_type: str
    trigger_data: Dict[str, Any]  # Full prediction/event data
    channels_attempted: List[str]
    channels_delivered: List[str]
    sent_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    user_action: Optional[str] = None  # 'acknowledged', 'dismissed', 'acted_upon'
    profile_id: Optional[int] = None
    vehicle_info: Optional[Dict] = None
    explanation_context: Optional[str] = None


class NotificationAuditLog:
    """
    Audit log for all notifications sent by the system.

    Provides:
    - Storage of notification details with trigger data
    - Retrieval for LLM explanation queries
    - Statistics and reporting
    """

    def __init__(self, db_path: Path = None):
        """Initialize the notification audit log.

        Args:
            db_path: Path to SQLite database. Defaults to PredictData/notifications/audit.db
        """
        if db_path is None:
            from config import get_config
            db_path = Path(get_config().DATA_DIR) / "notifications" / "audit.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"NotificationAuditLog initialized at {self.db_path}")

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notification_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id TEXT UNIQUE NOT NULL,
                    recipient_id INTEGER NOT NULL,
                    recipient_type TEXT NOT NULL,
                    profile_id INTEGER,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    trigger_data TEXT NOT NULL,
                    vehicle_info TEXT,
                    explanation_context TEXT,
                    channels_attempted TEXT NOT NULL,
                    channels_delivered TEXT,
                    sent_at TIMESTAMP NOT NULL,
                    delivered_at TIMESTAMP,
                    read_at TIMESTAMP,
                    user_action TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_recipient
                ON notification_audit(recipient_id, recipient_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_profile
                ON notification_audit(profile_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_sent_at
                ON notification_audit(sent_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_priority
                ON notification_audit(priority)
            """)

            conn.commit()

    def log_notification(self, entry: NotificationAuditEntry) -> str:
        """Log a notification to the audit trail.

        Args:
            entry: NotificationAuditEntry with full details

        Returns:
            The notification_id
        """
        if not entry.notification_id:
            entry.notification_id = str(uuid.uuid4())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO notification_audit (
                    notification_id, recipient_id, recipient_type, profile_id,
                    title, message, priority, trigger_type, trigger_data,
                    vehicle_info, explanation_context, channels_attempted,
                    channels_delivered, sent_at, delivered_at, read_at, user_action
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.notification_id,
                entry.recipient_id,
                entry.recipient_type,
                entry.profile_id,
                entry.title,
                entry.message,
                entry.priority,
                entry.trigger_type,
                json.dumps(entry.trigger_data),
                json.dumps(entry.vehicle_info) if entry.vehicle_info else None,
                entry.explanation_context,
                json.dumps(entry.channels_attempted),
                json.dumps(entry.channels_delivered) if entry.channels_delivered else None,
                entry.sent_at.isoformat() if entry.sent_at else None,
                entry.delivered_at.isoformat() if entry.delivered_at else None,
                entry.read_at.isoformat() if entry.read_at else None,
                entry.user_action
            ))
            conn.commit()

        logger.info(f"Logged notification {entry.notification_id} for recipient {entry.recipient_id}")
        return entry.notification_id

    def update_delivery_status(self, notification_id: str,
                                channels_delivered: List[str],
                                delivered_at: datetime = None):
        """Update the delivery status of a notification.

        Args:
            notification_id: The notification to update
            channels_delivered: List of channels that delivered successfully
            delivered_at: When delivery was confirmed
        """
        if delivered_at is None:
            delivered_at = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE notification_audit
                SET channels_delivered = ?, delivered_at = ?
                WHERE notification_id = ?
            """, (
                json.dumps(channels_delivered),
                delivered_at.isoformat(),
                notification_id
            ))
            conn.commit()

    def mark_as_read(self, notification_id: str, read_at: datetime = None):
        """Mark a notification as read.

        Args:
            notification_id: The notification to mark
            read_at: When it was read
        """
        if read_at is None:
            read_at = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE notification_audit
                SET read_at = ?
                WHERE notification_id = ?
            """, (read_at.isoformat(), notification_id))
            conn.commit()

    def record_user_action(self, notification_id: str, action: str):
        """Record what the user did with the notification.

        Args:
            notification_id: The notification
            action: One of 'acknowledged', 'dismissed', 'acted_upon'
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE notification_audit
                SET user_action = ?
                WHERE notification_id = ?
            """, (action, notification_id))
            conn.commit()

    def get_by_id(self, notification_id: str) -> Optional[Dict]:
        """Get a notification by its ID.

        Args:
            notification_id: The notification to retrieve

        Returns:
            Full notification record or None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM notification_audit
                WHERE notification_id = ?
            """, (notification_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_dict(row)
            return None

    def get_recent(self, profile_id: int = None, recipient_id: int = None,
                   limit: int = 20, days: int = 7) -> List[Dict]:
        """Get recent notifications for a profile or recipient.

        Args:
            profile_id: Filter by vehicle profile
            recipient_id: Filter by recipient (owner/driver)
            limit: Maximum number to return
            days: Look back this many days

        Returns:
            List of notification records
        """
        query = """
            SELECT * FROM notification_audit
            WHERE sent_at >= datetime('now', ?)
        """
        params = [f'-{days} days']

        if profile_id:
            query += " AND profile_id = ?"
            params.append(profile_id)

        if recipient_id:
            query += " AND recipient_id = ?"
            params.append(recipient_id)

        query += " ORDER BY sent_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_for_llm_context(self, profile_id: int, limit: int = 10) -> str:
        """Get notifications formatted for LLM context injection.

        Args:
            profile_id: The vehicle profile to get notifications for
            limit: Maximum number to include

        Returns:
            Formatted string for LLM context
        """
        notifications = self.get_recent(profile_id=profile_id, limit=limit)

        if not notifications:
            return "No recent notifications for this vehicle."

        lines = ["RECENT NOTIFICATIONS I SENT:"]
        for notif in notifications:
            sent_at = notif.get('sent_at', 'Unknown time')
            title = notif.get('title', 'No title')
            priority = notif.get('priority', 'medium').upper()
            trigger_type = notif.get('trigger_type', 'unknown')
            user_action = notif.get('user_action', 'no action')

            lines.append(f"  - [{priority}] {title}")
            lines.append(f"    Sent: {sent_at}, Trigger: {trigger_type}, User action: {user_action}")

            # Add trigger data summary
            trigger_data = notif.get('trigger_data', {})
            if isinstance(trigger_data, str):
                try:
                    trigger_data = json.loads(trigger_data)
                except:
                    trigger_data = {}

            if trigger_data:
                if 'probability' in trigger_data:
                    lines.append(f"    Prediction probability: {trigger_data['probability']}%")
                if 'component' in trigger_data:
                    lines.append(f"    Component: {trigger_data['component']}")
                if 'days_to_failure' in trigger_data:
                    lines.append(f"    Days to failure: {trigger_data['days_to_failure']}")

        return "\n".join(lines)

    def build_explanation_context(self, notification_id: str) -> Optional[str]:
        """Build a context string for LLM to explain why a notification was sent.

        Args:
            notification_id: The notification to explain

        Returns:
            Formatted context for LLM explanation
        """
        notif = self.get_by_id(notification_id)
        if not notif:
            return None

        trigger_data = notif.get('trigger_data', {})
        if isinstance(trigger_data, str):
            try:
                trigger_data = json.loads(trigger_data)
            except:
                trigger_data = {}

        vehicle_info = notif.get('vehicle_info', {})
        if isinstance(vehicle_info, str):
            try:
                vehicle_info = json.loads(vehicle_info)
            except:
                vehicle_info = {}

        context = f"""
NOTIFICATION TO EXPLAIN:
- Title: {notif.get('title')}
- Message: {notif.get('message')}
- Priority: {notif.get('priority', 'medium').upper()}
- Sent at: {notif.get('sent_at')}
- Recipient type: {notif.get('recipient_type')}

TRIGGER INFORMATION:
- Trigger type: {notif.get('trigger_type')}
- Trigger data: {json.dumps(trigger_data, indent=2)}

VEHICLE CONTEXT:
{json.dumps(vehicle_info, indent=2) if vehicle_info else 'No vehicle info available'}

USER ACTION: {notif.get('user_action', 'No action recorded')}

Please explain in first person (as the AI system) why this notification was sent,
referencing the specific trigger data and vehicle information above.
"""
        return context

    def get_statistics(self, days: int = 30) -> Dict:
        """Get notification statistics for the specified period.

        Args:
            days: Number of days to analyze

        Returns:
            Statistics dictionary
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Total counts by priority
            cursor = conn.execute("""
                SELECT priority, COUNT(*) as count
                FROM notification_audit
                WHERE sent_at >= datetime('now', ?)
                GROUP BY priority
            """, (f'-{days} days',))
            by_priority = {row['priority']: row['count'] for row in cursor.fetchall()}

            # Delivery success rate
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN channels_delivered IS NOT NULL
                             AND channels_delivered != '[]' THEN 1 ELSE 0 END) as delivered
                FROM notification_audit
                WHERE sent_at >= datetime('now', ?)
            """, (f'-{days} days',))
            delivery = cursor.fetchone()

            # User action breakdown
            cursor = conn.execute("""
                SELECT user_action, COUNT(*) as count
                FROM notification_audit
                WHERE sent_at >= datetime('now', ?)
                AND user_action IS NOT NULL
                GROUP BY user_action
            """, (f'-{days} days',))
            by_action = {row['user_action']: row['count'] for row in cursor.fetchall()}

            # By trigger type
            cursor = conn.execute("""
                SELECT trigger_type, COUNT(*) as count
                FROM notification_audit
                WHERE sent_at >= datetime('now', ?)
                GROUP BY trigger_type
            """, (f'-{days} days',))
            by_trigger = {row['trigger_type']: row['count'] for row in cursor.fetchall()}

            total = delivery['total'] if delivery else 0
            delivered = delivery['delivered'] if delivery else 0

            return {
                'period_days': days,
                'total_notifications': total,
                'delivered': delivered,
                'delivery_rate': (delivered / total * 100) if total > 0 else 0,
                'by_priority': by_priority,
                'by_trigger_type': by_trigger,
                'by_user_action': by_action
            }

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert a database row to a dictionary."""
        d = dict(row)

        # Parse JSON fields
        for field in ['trigger_data', 'vehicle_info', 'channels_attempted', 'channels_delivered']:
            if field in d and d[field]:
                try:
                    d[field] = json.loads(d[field])
                except:
                    pass

        return d

    def cleanup_old_entries(self, days: int = 90):
        """Remove entries older than specified days.

        Args:
            days: Remove entries older than this many days
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM notification_audit
                WHERE sent_at < datetime('now', ?)
            """, (f'-{days} days',))
            deleted = cursor.rowcount
            conn.commit()

        logger.info(f"Cleaned up {deleted} notification audit entries older than {days} days")
        return deleted


# Convenience function to create audit entry from prediction
def create_prediction_audit_entry(
    prediction: Dict,
    recipient_id: int,
    recipient_type: str,
    profile_id: int,
    vehicle_info: Dict,
    priority: NotificationPriority,
    channels: List[str]
) -> NotificationAuditEntry:
    """Create an audit entry for a prediction-triggered notification.

    Args:
        prediction: The prediction data that triggered the notification
        recipient_id: ID of owner or driver
        recipient_type: 'owner' or 'driver'
        profile_id: Vehicle profile ID
        vehicle_info: Vehicle details
        priority: Notification priority
        channels: Channels to send to

    Returns:
        NotificationAuditEntry ready to be logged
    """
    component = prediction.get('component', 'Unknown')
    probability = prediction.get('probability', 0)
    days = prediction.get('days_to_failure', 'N/A')
    confidence = prediction.get('confidence', 0)

    title = f"{component} Alert"
    message = f"{component} failure predicted with {probability:.0f}% probability in {days} days"

    explanation = f"""
I detected potential {component} issues based on sensor data analysis.
- Failure probability: {probability:.1f}%
- Estimated time to failure: {days} days
- Confidence level: {confidence:.1f}%
- Based on patterns from {prediction.get('samples_analyzed', 'multiple')} data points
"""

    return NotificationAuditEntry(
        notification_id=str(uuid.uuid4()),
        recipient_id=recipient_id,
        recipient_type=recipient_type,
        profile_id=profile_id,
        title=title,
        message=message,
        priority=priority.value,
        trigger_type=TriggerType.PREDICTION.value,
        trigger_data=prediction,
        vehicle_info=vehicle_info,
        explanation_context=explanation,
        channels_attempted=channels,
        channels_delivered=[],
        sent_at=datetime.now()
    )


# Singleton instance
_audit_log_instance = None

def get_notification_audit_log() -> NotificationAuditLog:
    """Get the singleton notification audit log instance."""
    global _audit_log_instance
    if _audit_log_instance is None:
        _audit_log_instance = NotificationAuditLog()
    return _audit_log_instance
