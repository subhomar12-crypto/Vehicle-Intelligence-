"""
Notification Feedback Tracking System
Tracks user actions on notifications and feeds back to AI for learning improvements.

Part of the PREDICT Vehicle Intelligence Platform notification system.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum


class FeedbackAction(Enum):
    """User actions on notifications"""
    SEEN = "seen"                    # Notification was displayed to user
    ACKNOWLEDGED = "acknowledged"    # User explicitly acknowledged
    DISMISSED = "dismissed"          # User dismissed without action
    ACTED_UPON = "acted_upon"        # User took action (clicked, opened details)
    SNOOZED = "snoozed"             # User snoozed for later
    ESCALATED = "escalated"         # User escalated to higher priority
    FORWARDED = "forwarded"         # User forwarded to someone else
    FEEDBACK_POSITIVE = "positive"  # User marked as helpful
    FEEDBACK_NEGATIVE = "negative"  # User marked as not helpful


class OutcomeType(Enum):
    """Outcome tracking for AI learning"""
    PREDICTION_CONFIRMED = "prediction_confirmed"      # Prediction was accurate
    PREDICTION_INCORRECT = "prediction_incorrect"      # Prediction was wrong
    FALSE_POSITIVE = "false_positive"                  # Alert was unnecessary
    TRUE_POSITIVE = "true_positive"                    # Alert was valid/helpful
    ISSUE_RESOLVED = "issue_resolved"                  # Problem was fixed
    ISSUE_PERSISTS = "issue_persists"                  # Problem continues
    SERVICE_SCHEDULED = "service_scheduled"            # User scheduled service
    SERVICE_COMPLETED = "service_completed"            # Service was done
    NO_ACTION_NEEDED = "no_action_needed"              # No action was required
    UNKNOWN = "unknown"                                # Outcome not determined


@dataclass
class NotificationFeedback:
    """Feedback entry for a notification"""
    id: Optional[int]
    notification_audit_id: str          # Links to notification_audit
    action: FeedbackAction
    action_timestamp: datetime
    user_id: Optional[str]              # Who performed the action
    user_type: str                      # "owner", "driver", "admin", "system"
    device_type: str                    # "desktop", "mobile_android", "mobile_ios", "web"

    # Outcome tracking for AI learning
    outcome: Optional[OutcomeType]
    outcome_timestamp: Optional[datetime]
    outcome_notes: Optional[str]

    # Context for AI learning
    response_time_seconds: Optional[int]  # Time from notification to action
    snooze_duration_minutes: Optional[int]
    forwarded_to: Optional[str]           # User ID if forwarded

    # User feedback
    helpfulness_rating: Optional[int]     # 1-5 scale
    accuracy_rating: Optional[int]        # 1-5 scale for prediction accuracy
    user_comment: Optional[str]

    # Metadata
    metadata: Optional[Dict[str, Any]]
    created_at: datetime


class NotificationFeedbackTracker:
    """Tracks user actions and feedback on notifications"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            app_data = os.path.join(os.path.expanduser("~"), ".predict")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "notification_feedback.db")

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Main feedback table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_audit_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    action_timestamp TEXT NOT NULL,
                    user_id TEXT,
                    user_type TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    outcome TEXT,
                    outcome_timestamp TEXT,
                    outcome_notes TEXT,
                    response_time_seconds INTEGER,
                    snooze_duration_minutes INTEGER,
                    forwarded_to TEXT,
                    helpfulness_rating INTEGER,
                    accuracy_rating INTEGER,
                    user_comment TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_notification
                ON notification_feedback(notification_audit_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_action
                ON notification_feedback(action)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_user
                ON notification_feedback(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
                ON notification_feedback(action_timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_outcome
                ON notification_feedback(outcome)
            """)

            # AI Learning metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_learning_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_date TEXT NOT NULL,
                    prediction_type TEXT NOT NULL,
                    total_notifications INTEGER DEFAULT 0,
                    true_positives INTEGER DEFAULT 0,
                    false_positives INTEGER DEFAULT 0,
                    confirmed_predictions INTEGER DEFAULT 0,
                    incorrect_predictions INTEGER DEFAULT 0,
                    avg_response_time_seconds REAL,
                    avg_helpfulness_rating REAL,
                    avg_accuracy_rating REAL,
                    created_at TEXT NOT NULL,
                    UNIQUE(metric_date, prediction_type)
                )
            """)

            conn.commit()

    def record_action(
        self,
        notification_audit_id: str,
        action: FeedbackAction,
        user_id: Optional[str] = None,
        user_type: str = "owner",
        device_type: str = "desktop",
        response_time_seconds: Optional[int] = None,
        snooze_duration_minutes: Optional[int] = None,
        forwarded_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Record a user action on a notification"""
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notification_feedback (
                    notification_audit_id, action, action_timestamp,
                    user_id, user_type, device_type,
                    response_time_seconds, snooze_duration_minutes,
                    forwarded_to, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification_audit_id,
                action.value,
                now.isoformat(),
                user_id,
                user_type,
                device_type,
                response_time_seconds,
                snooze_duration_minutes,
                forwarded_to,
                json.dumps(metadata) if metadata else None,
                now.isoformat()
            ))
            conn.commit()
            return cursor.lastrowid

    def record_outcome(
        self,
        notification_audit_id: str,
        outcome: OutcomeType,
        notes: Optional[str] = None
    ) -> bool:
        """Record the outcome of a notification (for AI learning)"""
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Update the most recent feedback entry for this notification
            cursor.execute("""
                UPDATE notification_feedback
                SET outcome = ?, outcome_timestamp = ?, outcome_notes = ?
                WHERE notification_audit_id = ?
                AND id = (
                    SELECT MAX(id) FROM notification_feedback
                    WHERE notification_audit_id = ?
                )
            """, (
                outcome.value,
                now.isoformat(),
                notes,
                notification_audit_id,
                notification_audit_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def record_user_feedback(
        self,
        notification_audit_id: str,
        helpfulness_rating: Optional[int] = None,
        accuracy_rating: Optional[int] = None,
        comment: Optional[str] = None
    ) -> bool:
        """Record user feedback ratings on a notification"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            updates = []
            params = []

            if helpfulness_rating is not None:
                updates.append("helpfulness_rating = ?")
                params.append(max(1, min(5, helpfulness_rating)))  # Clamp 1-5

            if accuracy_rating is not None:
                updates.append("accuracy_rating = ?")
                params.append(max(1, min(5, accuracy_rating)))

            if comment is not None:
                updates.append("user_comment = ?")
                params.append(comment)

            if not updates:
                return False

            params.extend([notification_audit_id, notification_audit_id])

            cursor.execute(f"""
                UPDATE notification_feedback
                SET {', '.join(updates)}
                WHERE notification_audit_id = ?
                AND id = (
                    SELECT MAX(id) FROM notification_feedback
                    WHERE notification_audit_id = ?
                )
            """, params)
            conn.commit()
            return cursor.rowcount > 0

    def get_feedback_for_notification(
        self,
        notification_audit_id: str
    ) -> List[NotificationFeedback]:
        """Get all feedback entries for a notification"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notification_feedback
                WHERE notification_audit_id = ?
                ORDER BY action_timestamp ASC
            """, (notification_audit_id,))

            return [self._row_to_feedback(row) for row in cursor.fetchall()]

    def get_user_feedback_history(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100
    ) -> List[NotificationFeedback]:
        """Get feedback history for a specific user"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notification_feedback
                WHERE user_id = ?
                AND action_timestamp >= ?
                ORDER BY action_timestamp DESC
                LIMIT ?
            """, (user_id, since.isoformat(), limit))

            return [self._row_to_feedback(row) for row in cursor.fetchall()]

    def get_ai_learning_data(
        self,
        prediction_type: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get aggregated data for AI learning improvements"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Base query
            base_conditions = "WHERE action_timestamp >= ?"
            params = [since.isoformat()]

            if prediction_type:
                # Would need to join with notification_audit for prediction type
                # For now, we aggregate all
                pass

            # Total actions by type
            cursor.execute(f"""
                SELECT action, COUNT(*) as count
                FROM notification_feedback
                {base_conditions}
                GROUP BY action
            """, params)
            action_counts = dict(cursor.fetchall())

            # Outcome distribution
            cursor.execute(f"""
                SELECT outcome, COUNT(*) as count
                FROM notification_feedback
                {base_conditions}
                AND outcome IS NOT NULL
                GROUP BY outcome
            """, params)
            outcome_counts = dict(cursor.fetchall())

            # Average ratings
            cursor.execute(f"""
                SELECT
                    AVG(helpfulness_rating) as avg_helpfulness,
                    AVG(accuracy_rating) as avg_accuracy,
                    AVG(response_time_seconds) as avg_response_time
                FROM notification_feedback
                {base_conditions}
            """, params)
            row = cursor.fetchone()

            # Calculate key metrics
            total_with_outcome = sum(outcome_counts.values()) if outcome_counts else 0
            true_positives = outcome_counts.get(OutcomeType.TRUE_POSITIVE.value, 0) + \
                           outcome_counts.get(OutcomeType.PREDICTION_CONFIRMED.value, 0)
            false_positives = outcome_counts.get(OutcomeType.FALSE_POSITIVE.value, 0) + \
                            outcome_counts.get(OutcomeType.PREDICTION_INCORRECT.value, 0)

            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else None

            return {
                "period_days": days,
                "action_counts": action_counts,
                "outcome_counts": outcome_counts,
                "total_with_outcome": total_with_outcome,
                "true_positives": true_positives,
                "false_positives": false_positives,
                "precision": precision,
                "avg_helpfulness_rating": row[0],
                "avg_accuracy_rating": row[1],
                "avg_response_time_seconds": row[2],
                "recommendations": self._generate_ai_recommendations(
                    action_counts, outcome_counts, precision, row[0], row[1]
                )
            }

    def _generate_ai_recommendations(
        self,
        action_counts: Dict,
        outcome_counts: Dict,
        precision: Optional[float],
        avg_helpfulness: Optional[float],
        avg_accuracy: Optional[float]
    ) -> List[str]:
        """Generate recommendations for AI model improvements"""
        recommendations = []

        # Check dismiss rate
        total_actions = sum(action_counts.values()) if action_counts else 0
        if total_actions > 0:
            dismiss_rate = action_counts.get(FeedbackAction.DISMISSED.value, 0) / total_actions
            if dismiss_rate > 0.3:
                recommendations.append(
                    f"High dismiss rate ({dismiss_rate:.1%}). Consider adjusting notification thresholds."
                )

        # Check precision
        if precision is not None and precision < 0.7:
            recommendations.append(
                f"Prediction precision is {precision:.1%}. Model may need retraining with recent data."
            )

        # Check helpfulness rating
        if avg_helpfulness is not None and avg_helpfulness < 3.0:
            recommendations.append(
                f"Low helpfulness rating ({avg_helpfulness:.1f}/5). Review notification content and timing."
            )

        # Check accuracy rating
        if avg_accuracy is not None and avg_accuracy < 3.0:
            recommendations.append(
                f"Low accuracy rating ({avg_accuracy:.1f}/5). Review prediction model inputs and thresholds."
            )

        # Check false positive rate
        total_outcomes = sum(outcome_counts.values()) if outcome_counts else 0
        if total_outcomes > 0:
            false_positive_rate = outcome_counts.get(OutcomeType.FALSE_POSITIVE.value, 0) / total_outcomes
            if false_positive_rate > 0.2:
                recommendations.append(
                    f"High false positive rate ({false_positive_rate:.1%}). Increase prediction confidence thresholds."
                )

        if not recommendations:
            recommendations.append("AI models are performing well. Continue monitoring.")

        return recommendations

    def get_feedback_summary_for_llm(
        self,
        notification_audit_id: str
    ) -> Dict[str, Any]:
        """Get a summary of feedback for LLM context"""
        feedback_list = self.get_feedback_for_notification(notification_audit_id)

        if not feedback_list:
            return {
                "has_feedback": False,
                "summary": "No user feedback recorded for this notification."
            }

        actions = [f.action.value for f in feedback_list]
        latest = feedback_list[-1]

        summary_parts = []

        # Action history
        summary_parts.append(f"User actions: {', '.join(actions)}")

        # Response time
        if latest.response_time_seconds:
            if latest.response_time_seconds < 60:
                summary_parts.append(f"Response time: {latest.response_time_seconds} seconds")
            else:
                minutes = latest.response_time_seconds // 60
                summary_parts.append(f"Response time: {minutes} minutes")

        # Outcome
        if latest.outcome:
            summary_parts.append(f"Outcome: {latest.outcome.value.replace('_', ' ')}")

        # Ratings
        if latest.helpfulness_rating:
            summary_parts.append(f"Helpfulness rating: {latest.helpfulness_rating}/5")
        if latest.accuracy_rating:
            summary_parts.append(f"Accuracy rating: {latest.accuracy_rating}/5")

        # User comment
        if latest.user_comment:
            summary_parts.append(f"User comment: \"{latest.user_comment}\"")

        return {
            "has_feedback": True,
            "action_count": len(feedback_list),
            "latest_action": latest.action.value,
            "device_type": latest.device_type,
            "outcome": latest.outcome.value if latest.outcome else None,
            "helpfulness_rating": latest.helpfulness_rating,
            "accuracy_rating": latest.accuracy_rating,
            "user_comment": latest.user_comment,
            "summary": ". ".join(summary_parts)
        }

    def update_ai_learning_metrics(self, metric_date: str = None):
        """Aggregate daily metrics for AI learning dashboard"""
        if metric_date is None:
            metric_date = datetime.now().strftime("%Y-%m-%d")

        start_of_day = f"{metric_date}T00:00:00"
        end_of_day = f"{metric_date}T23:59:59"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get aggregated data for the day
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome IN ('true_positive', 'prediction_confirmed') THEN 1 ELSE 0 END) as true_positives,
                    SUM(CASE WHEN outcome IN ('false_positive', 'prediction_incorrect') THEN 1 ELSE 0 END) as false_positives,
                    SUM(CASE WHEN outcome = 'prediction_confirmed' THEN 1 ELSE 0 END) as confirmed,
                    SUM(CASE WHEN outcome = 'prediction_incorrect' THEN 1 ELSE 0 END) as incorrect,
                    AVG(response_time_seconds) as avg_response,
                    AVG(helpfulness_rating) as avg_help,
                    AVG(accuracy_rating) as avg_acc
                FROM notification_feedback
                WHERE action_timestamp >= ? AND action_timestamp <= ?
            """, (start_of_day, end_of_day))

            row = cursor.fetchone()

            # Upsert metrics
            cursor.execute("""
                INSERT INTO ai_learning_metrics (
                    metric_date, prediction_type, total_notifications,
                    true_positives, false_positives, confirmed_predictions,
                    incorrect_predictions, avg_response_time_seconds,
                    avg_helpfulness_rating, avg_accuracy_rating, created_at
                ) VALUES (?, 'all', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric_date, prediction_type) DO UPDATE SET
                    total_notifications = excluded.total_notifications,
                    true_positives = excluded.true_positives,
                    false_positives = excluded.false_positives,
                    confirmed_predictions = excluded.confirmed_predictions,
                    incorrect_predictions = excluded.incorrect_predictions,
                    avg_response_time_seconds = excluded.avg_response_time_seconds,
                    avg_helpfulness_rating = excluded.avg_helpfulness_rating,
                    avg_accuracy_rating = excluded.avg_accuracy_rating
            """, (
                metric_date,
                row[0] or 0, row[1] or 0, row[2] or 0,
                row[3] or 0, row[4] or 0, row[5], row[6], row[7],
                datetime.now().isoformat()
            ))
            conn.commit()

    def _row_to_feedback(self, row: sqlite3.Row) -> NotificationFeedback:
        """Convert database row to NotificationFeedback object"""
        return NotificationFeedback(
            id=row["id"],
            notification_audit_id=row["notification_audit_id"],
            action=FeedbackAction(row["action"]),
            action_timestamp=datetime.fromisoformat(row["action_timestamp"]),
            user_id=row["user_id"],
            user_type=row["user_type"],
            device_type=row["device_type"],
            outcome=OutcomeType(row["outcome"]) if row["outcome"] else None,
            outcome_timestamp=datetime.fromisoformat(row["outcome_timestamp"]) if row["outcome_timestamp"] else None,
            outcome_notes=row["outcome_notes"],
            response_time_seconds=row["response_time_seconds"],
            snooze_duration_minutes=row["snooze_duration_minutes"],
            forwarded_to=row["forwarded_to"],
            helpfulness_rating=row["helpfulness_rating"],
            accuracy_rating=row["accuracy_rating"],
            user_comment=row["user_comment"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            created_at=datetime.fromisoformat(row["created_at"])
        )

    def cleanup_old_entries(self, days: int = 365):
        """Remove entries older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM notification_feedback
                WHERE action_timestamp < ?
            """, (cutoff.isoformat(),))
            deleted = cursor.rowcount
            conn.commit()
            return deleted


# Convenience functions for common operations
def record_notification_seen(
    notification_id: str,
    user_id: str,
    user_type: str = "owner",
    device_type: str = "desktop",
    response_time: Optional[int] = None
) -> int:
    """Helper to record when a notification is seen"""
    tracker = NotificationFeedbackTracker()
    return tracker.record_action(
        notification_audit_id=notification_id,
        action=FeedbackAction.SEEN,
        user_id=user_id,
        user_type=user_type,
        device_type=device_type,
        response_time_seconds=response_time
    )


def record_notification_acknowledged(
    notification_id: str,
    user_id: str,
    user_type: str = "owner",
    device_type: str = "desktop"
) -> int:
    """Helper to record when a notification is acknowledged"""
    tracker = NotificationFeedbackTracker()
    return tracker.record_action(
        notification_audit_id=notification_id,
        action=FeedbackAction.ACKNOWLEDGED,
        user_id=user_id,
        user_type=user_type,
        device_type=device_type
    )


def record_notification_dismissed(
    notification_id: str,
    user_id: str,
    user_type: str = "owner",
    device_type: str = "desktop"
) -> int:
    """Helper to record when a notification is dismissed"""
    tracker = NotificationFeedbackTracker()
    return tracker.record_action(
        notification_audit_id=notification_id,
        action=FeedbackAction.DISMISSED,
        user_id=user_id,
        user_type=user_type,
        device_type=device_type
    )


def record_prediction_outcome(
    notification_id: str,
    was_accurate: bool,
    notes: Optional[str] = None
) -> bool:
    """Helper to record whether a prediction was accurate"""
    tracker = NotificationFeedbackTracker()
    outcome = OutcomeType.PREDICTION_CONFIRMED if was_accurate else OutcomeType.PREDICTION_INCORRECT
    return tracker.record_outcome(notification_id, outcome, notes)
