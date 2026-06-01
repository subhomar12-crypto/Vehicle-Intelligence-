"""
Customer Communication Log System
Logs all customer interactions (calls, emails, chats) for LLM reference.

When a customer calls asking about a notification, this log helps the LLM
provide accurate context about previous communications.

Part of the PREDICT Vehicle Intelligence Platform.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class CommunicationType(Enum):
    """Types of customer communication"""
    PHONE_CALL = "phone_call"
    EMAIL = "email"
    SMS = "sms"
    IN_APP_CHAT = "in_app_chat"
    VIDEO_CALL = "video_call"
    IN_PERSON = "in_person"
    SUPPORT_TICKET = "support_ticket"
    WHATSAPP = "whatsapp"


class CommunicationDirection(Enum):
    """Direction of communication"""
    INBOUND = "inbound"      # Customer initiated
    OUTBOUND = "outbound"    # We initiated


class CommunicationStatus(Enum):
    """Status of the communication"""
    COMPLETED = "completed"
    MISSED = "missed"
    VOICEMAIL = "voicemail"
    PENDING = "pending"
    ESCALATED = "escalated"
    FOLLOW_UP_REQUIRED = "follow_up_required"


class TopicCategory(Enum):
    """Categories for communication topics"""
    NOTIFICATION_INQUIRY = "notification_inquiry"
    PREDICTION_QUESTION = "prediction_question"
    VEHICLE_STATUS = "vehicle_status"
    DRIVER_BEHAVIOR = "driver_behavior"
    SERVICE_RECOMMENDATION = "service_recommendation"
    BILLING = "billing"
    TECHNICAL_SUPPORT = "technical_support"
    ACCOUNT_MANAGEMENT = "account_management"
    COMPLAINT = "complaint"
    FEEDBACK = "feedback"
    GENERAL_INQUIRY = "general_inquiry"
    EMERGENCY = "emergency"


@dataclass
class CommunicationEntry:
    """A single communication log entry"""
    id: Optional[int]
    communication_id: str              # Unique ID for this communication

    # Customer/Owner info
    customer_id: str                   # Owner ID from profiles
    customer_name: str
    customer_phone: Optional[str]
    customer_email: Optional[str]

    # Communication details
    comm_type: CommunicationType
    direction: CommunicationDirection
    status: CommunicationStatus
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]

    # Topic and content
    topic_category: TopicCategory
    subject: str                       # Brief subject line
    summary: str                       # Detailed summary of conversation
    key_points: List[str]             # Bullet points of key items discussed

    # Related entities
    related_notification_ids: List[str]   # Notification audit IDs discussed
    related_vehicle_ids: List[str]        # Vehicle profile IDs
    related_driver_ids: List[str]         # Driver profile IDs
    related_prediction_ids: List[str]     # Prediction IDs discussed

    # Staff handling
    handled_by_user_id: Optional[str]     # Staff member who handled
    handled_by_name: Optional[str]

    # Follow-up
    follow_up_required: bool
    follow_up_date: Optional[datetime]
    follow_up_notes: Optional[str]

    # Resolution
    resolution: Optional[str]
    customer_satisfaction: Optional[int]   # 1-5 rating

    # LLM context
    llm_context_summary: Optional[str]     # Pre-generated summary for LLM

    # Metadata
    language: str                          # "en" or "ar"
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class CustomerCommunicationLog:
    """Manages customer communication logs"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            app_data = os.path.join(os.path.expanduser("~"), ".predict")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "communication_log.db")

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS communication_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    communication_id TEXT UNIQUE NOT NULL,
                    customer_id TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    customer_phone TEXT,
                    customer_email TEXT,
                    comm_type TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_seconds INTEGER,
                    topic_category TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    key_points TEXT,
                    related_notification_ids TEXT,
                    related_vehicle_ids TEXT,
                    related_driver_ids TEXT,
                    related_prediction_ids TEXT,
                    handled_by_user_id TEXT,
                    handled_by_name TEXT,
                    follow_up_required INTEGER DEFAULT 0,
                    follow_up_date TEXT,
                    follow_up_notes TEXT,
                    resolution TEXT,
                    customer_satisfaction INTEGER,
                    llm_context_summary TEXT,
                    language TEXT DEFAULT 'en',
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_comm_customer
                ON communication_log(customer_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_comm_started
                ON communication_log(started_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_comm_topic
                ON communication_log(topic_category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_comm_status
                ON communication_log(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_comm_follow_up
                ON communication_log(follow_up_required, follow_up_date)
            """)

            conn.commit()

    def log_communication(
        self,
        customer_id: str,
        customer_name: str,
        comm_type: CommunicationType,
        direction: CommunicationDirection,
        topic_category: TopicCategory,
        subject: str,
        summary: str,
        key_points: List[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        status: CommunicationStatus = CommunicationStatus.COMPLETED,
        started_at: datetime = None,
        ended_at: datetime = None,
        duration_seconds: Optional[int] = None,
        related_notification_ids: List[str] = None,
        related_vehicle_ids: List[str] = None,
        related_driver_ids: List[str] = None,
        related_prediction_ids: List[str] = None,
        handled_by_user_id: Optional[str] = None,
        handled_by_name: Optional[str] = None,
        follow_up_required: bool = False,
        follow_up_date: datetime = None,
        follow_up_notes: Optional[str] = None,
        resolution: Optional[str] = None,
        customer_satisfaction: Optional[int] = None,
        language: str = "en",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log a new customer communication"""
        import uuid
        communication_id = str(uuid.uuid4())
        now = datetime.now()

        if started_at is None:
            started_at = now

        # Generate LLM context summary
        llm_context = self._generate_llm_context(
            customer_name=customer_name,
            comm_type=comm_type,
            direction=direction,
            topic_category=topic_category,
            subject=subject,
            summary=summary,
            key_points=key_points or [],
            resolution=resolution
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO communication_log (
                    communication_id, customer_id, customer_name,
                    customer_phone, customer_email, comm_type, direction,
                    status, started_at, ended_at, duration_seconds,
                    topic_category, subject, summary, key_points,
                    related_notification_ids, related_vehicle_ids,
                    related_driver_ids, related_prediction_ids,
                    handled_by_user_id, handled_by_name,
                    follow_up_required, follow_up_date, follow_up_notes,
                    resolution, customer_satisfaction, llm_context_summary,
                    language, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                communication_id,
                customer_id,
                customer_name,
                customer_phone,
                customer_email,
                comm_type.value,
                direction.value,
                status.value,
                started_at.isoformat(),
                ended_at.isoformat() if ended_at else None,
                duration_seconds,
                topic_category.value,
                subject,
                summary,
                json.dumps(key_points or []),
                json.dumps(related_notification_ids or []),
                json.dumps(related_vehicle_ids or []),
                json.dumps(related_driver_ids or []),
                json.dumps(related_prediction_ids or []),
                handled_by_user_id,
                handled_by_name,
                1 if follow_up_required else 0,
                follow_up_date.isoformat() if follow_up_date else None,
                follow_up_notes,
                resolution,
                customer_satisfaction,
                llm_context,
                language,
                json.dumps(metadata) if metadata else None,
                now.isoformat(),
                now.isoformat()
            ))
            conn.commit()

        return communication_id

    def _generate_llm_context(
        self,
        customer_name: str,
        comm_type: CommunicationType,
        direction: CommunicationDirection,
        topic_category: TopicCategory,
        subject: str,
        summary: str,
        key_points: List[str],
        resolution: Optional[str]
    ) -> str:
        """Generate a summary optimized for LLM context"""
        direction_text = "contacted us" if direction == CommunicationDirection.INBOUND else "was contacted"
        comm_text = comm_type.value.replace("_", " ")
        topic_text = topic_category.value.replace("_", " ")

        context = f"{customer_name} {direction_text} via {comm_text} regarding {topic_text}. "
        context += f"Subject: {subject}. "
        context += f"Summary: {summary}"

        if key_points:
            context += " Key points discussed: " + "; ".join(key_points) + "."

        if resolution:
            context += f" Resolution: {resolution}"

        return context

    def get_customer_history(
        self,
        customer_id: str,
        days: int = 90,
        limit: int = 50
    ) -> List[CommunicationEntry]:
        """Get communication history for a customer"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM communication_log
                WHERE customer_id = ?
                AND started_at >= ?
                ORDER BY started_at DESC
                LIMIT ?
            """, (customer_id, since.isoformat(), limit))

            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_notification_related_communications(
        self,
        notification_id: str
    ) -> List[CommunicationEntry]:
        """Get all communications related to a specific notification"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM communication_log
                WHERE related_notification_ids LIKE ?
                ORDER BY started_at DESC
            """, (f'%"{notification_id}"%',))

            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_vehicle_related_communications(
        self,
        vehicle_id: str,
        days: int = 90
    ) -> List[CommunicationEntry]:
        """Get communications related to a specific vehicle"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM communication_log
                WHERE related_vehicle_ids LIKE ?
                AND started_at >= ?
                ORDER BY started_at DESC
            """, (f'%"{vehicle_id}"%', since.isoformat()))

            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_pending_follow_ups(self) -> List[CommunicationEntry]:
        """Get all communications requiring follow-up"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM communication_log
                WHERE follow_up_required = 1
                AND (follow_up_date IS NULL OR follow_up_date <= ?)
                ORDER BY follow_up_date ASC, started_at DESC
            """, (datetime.now().isoformat(),))

            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def update_follow_up(
        self,
        communication_id: str,
        follow_up_required: bool,
        follow_up_date: datetime = None,
        follow_up_notes: str = None
    ) -> bool:
        """Update follow-up status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE communication_log
                SET follow_up_required = ?,
                    follow_up_date = ?,
                    follow_up_notes = ?,
                    updated_at = ?
                WHERE communication_id = ?
            """, (
                1 if follow_up_required else 0,
                follow_up_date.isoformat() if follow_up_date else None,
                follow_up_notes,
                datetime.now().isoformat(),
                communication_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def update_resolution(
        self,
        communication_id: str,
        resolution: str,
        customer_satisfaction: int = None
    ) -> bool:
        """Update resolution and satisfaction"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE communication_log
                SET resolution = ?,
                    customer_satisfaction = ?,
                    status = 'completed',
                    updated_at = ?
                WHERE communication_id = ?
            """, (
                resolution,
                customer_satisfaction,
                datetime.now().isoformat(),
                communication_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def get_llm_context_for_customer(
        self,
        customer_id: str,
        max_entries: int = 10
    ) -> Dict[str, Any]:
        """Get communication context optimized for LLM"""
        history = self.get_customer_history(customer_id, days=90, limit=max_entries)

        if not history:
            return {
                "has_history": False,
                "summary": "No previous communication history with this customer."
            }

        # Build context
        recent_topics = {}
        total_calls = 0
        total_emails = 0
        pending_issues = []

        for entry in history:
            # Count by type
            if entry.comm_type == CommunicationType.PHONE_CALL:
                total_calls += 1
            elif entry.comm_type == CommunicationType.EMAIL:
                total_emails += 1

            # Track topics
            topic = entry.topic_category.value
            if topic not in recent_topics:
                recent_topics[topic] = 0
            recent_topics[topic] += 1

            # Track pending issues
            if entry.follow_up_required and entry.status != CommunicationStatus.COMPLETED:
                pending_issues.append({
                    "subject": entry.subject,
                    "date": entry.started_at.strftime("%Y-%m-%d"),
                    "notes": entry.follow_up_notes
                })

        # Generate summary
        summaries = [entry.llm_context_summary for entry in history[:5] if entry.llm_context_summary]

        return {
            "has_history": True,
            "total_interactions": len(history),
            "total_calls": total_calls,
            "total_emails": total_emails,
            "topic_distribution": recent_topics,
            "pending_issues": pending_issues,
            "recent_summaries": summaries,
            "last_contact": history[0].started_at.isoformat() if history else None,
            "summary": self._build_customer_summary(history, recent_topics, pending_issues)
        }

    def _build_customer_summary(
        self,
        history: List[CommunicationEntry],
        topics: Dict[str, int],
        pending: List[Dict]
    ) -> str:
        """Build a natural language summary for LLM context"""
        if not history:
            return "No communication history."

        summary_parts = []

        # Total interactions
        summary_parts.append(f"Customer has {len(history)} communications in the last 90 days.")

        # Most common topics
        if topics:
            top_topic = max(topics.items(), key=lambda x: x[1])
            summary_parts.append(
                f"Most discussed topic: {top_topic[0].replace('_', ' ')} ({top_topic[1]} times)."
            )

        # Pending issues
        if pending:
            summary_parts.append(f"There are {len(pending)} pending follow-up issues.")

        # Last interaction
        last = history[0]
        summary_parts.append(
            f"Last contact was {last.started_at.strftime('%Y-%m-%d')} regarding {last.subject}."
        )

        # Satisfaction trend
        satisfaction_scores = [e.customer_satisfaction for e in history if e.customer_satisfaction]
        if satisfaction_scores:
            avg = sum(satisfaction_scores) / len(satisfaction_scores)
            summary_parts.append(f"Average satisfaction rating: {avg:.1f}/5.")

        return " ".join(summary_parts)

    def search_communications(
        self,
        query: str,
        customer_id: Optional[str] = None,
        topic: Optional[TopicCategory] = None,
        days: int = 90
    ) -> List[CommunicationEntry]:
        """Search communications by keyword"""
        since = datetime.now() - timedelta(days=days)

        conditions = ["started_at >= ?"]
        params = [since.isoformat()]

        if customer_id:
            conditions.append("customer_id = ?")
            params.append(customer_id)

        if topic:
            conditions.append("topic_category = ?")
            params.append(topic.value)

        # Search in subject, summary, key_points
        conditions.append("(subject LIKE ? OR summary LIKE ? OR key_points LIKE ?)")
        search_term = f"%{query}%"
        params.extend([search_term, search_term, search_term])

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT * FROM communication_log
                WHERE {' AND '.join(conditions)}
                ORDER BY started_at DESC
                LIMIT 50
            """, params)

            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get communication statistics"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute("""
                SELECT COUNT(*) FROM communication_log
                WHERE started_at >= ?
            """, (since.isoformat(),))
            total = cursor.fetchone()[0]

            # By type
            cursor.execute("""
                SELECT comm_type, COUNT(*) FROM communication_log
                WHERE started_at >= ?
                GROUP BY comm_type
            """, (since.isoformat(),))
            by_type = dict(cursor.fetchall())

            # By topic
            cursor.execute("""
                SELECT topic_category, COUNT(*) FROM communication_log
                WHERE started_at >= ?
                GROUP BY topic_category
            """, (since.isoformat(),))
            by_topic = dict(cursor.fetchall())

            # Average satisfaction
            cursor.execute("""
                SELECT AVG(customer_satisfaction) FROM communication_log
                WHERE started_at >= ?
                AND customer_satisfaction IS NOT NULL
            """, (since.isoformat(),))
            avg_satisfaction = cursor.fetchone()[0]

            # Pending follow-ups
            cursor.execute("""
                SELECT COUNT(*) FROM communication_log
                WHERE follow_up_required = 1
                AND status != 'completed'
            """)
            pending_follow_ups = cursor.fetchone()[0]

            return {
                "period_days": days,
                "total_communications": total,
                "by_type": by_type,
                "by_topic": by_topic,
                "avg_satisfaction": avg_satisfaction,
                "pending_follow_ups": pending_follow_ups
            }

    def _row_to_entry(self, row: sqlite3.Row) -> CommunicationEntry:
        """Convert database row to CommunicationEntry"""
        return CommunicationEntry(
            id=row["id"],
            communication_id=row["communication_id"],
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            customer_phone=row["customer_phone"],
            customer_email=row["customer_email"],
            comm_type=CommunicationType(row["comm_type"]),
            direction=CommunicationDirection(row["direction"]),
            status=CommunicationStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            duration_seconds=row["duration_seconds"],
            topic_category=TopicCategory(row["topic_category"]),
            subject=row["subject"],
            summary=row["summary"],
            key_points=json.loads(row["key_points"]) if row["key_points"] else [],
            related_notification_ids=json.loads(row["related_notification_ids"]) if row["related_notification_ids"] else [],
            related_vehicle_ids=json.loads(row["related_vehicle_ids"]) if row["related_vehicle_ids"] else [],
            related_driver_ids=json.loads(row["related_driver_ids"]) if row["related_driver_ids"] else [],
            related_prediction_ids=json.loads(row["related_prediction_ids"]) if row["related_prediction_ids"] else [],
            handled_by_user_id=row["handled_by_user_id"],
            handled_by_name=row["handled_by_name"],
            follow_up_required=bool(row["follow_up_required"]),
            follow_up_date=datetime.fromisoformat(row["follow_up_date"]) if row["follow_up_date"] else None,
            follow_up_notes=row["follow_up_notes"],
            resolution=row["resolution"],
            customer_satisfaction=row["customer_satisfaction"],
            llm_context_summary=row["llm_context_summary"],
            language=row["language"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )

    def cleanup_old_entries(self, days: int = 365):
        """Remove entries older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM communication_log
                WHERE started_at < ?
            """, (cutoff.isoformat(),))
            deleted = cursor.rowcount
            conn.commit()
            return deleted


# Helper function for quick logging
def log_customer_call(
    customer_id: str,
    customer_name: str,
    subject: str,
    summary: str,
    topic: TopicCategory = TopicCategory.GENERAL_INQUIRY,
    notification_ids: List[str] = None,
    vehicle_ids: List[str] = None,
    handled_by: str = None
) -> str:
    """Quick helper to log an inbound customer call"""
    log = CustomerCommunicationLog()
    return log.log_communication(
        customer_id=customer_id,
        customer_name=customer_name,
        comm_type=CommunicationType.PHONE_CALL,
        direction=CommunicationDirection.INBOUND,
        topic_category=topic,
        subject=subject,
        summary=summary,
        related_notification_ids=notification_ids or [],
        related_vehicle_ids=vehicle_ids or [],
        handled_by_name=handled_by
    )
