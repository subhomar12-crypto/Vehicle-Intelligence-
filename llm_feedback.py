"""
LLM Feedback System
Collects user feedback (thumbs up/down) on LLM responses.

Features:
1. Thumbs up/down rating collection
2. Optional text feedback
3. Analytics and reporting
4. Quality improvement tracking

Part of the PREDICT Vehicle Intelligence Platform.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class FeedbackRating(Enum):
    """User rating for LLM response"""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    NEUTRAL = "neutral"


class FeedbackCategory(Enum):
    """Categories for negative feedback"""
    INACCURATE = "inaccurate"          # Information was wrong
    INCOMPLETE = "incomplete"          # Missing important info
    UNCLEAR = "unclear"                # Hard to understand
    NOT_HELPFUL = "not_helpful"        # Didn't answer the question
    TOO_SLOW = "too_slow"              # Response took too long
    WRONG_LANGUAGE = "wrong_language"  # Responded in wrong language
    OTHER = "other"


@dataclass
class LLMFeedback:
    """A single feedback entry"""
    id: Optional[int]
    feedback_id: str
    message_id: Optional[int]          # ID from conversation history
    conversation_id: Optional[str]
    user_id: str
    rating: FeedbackRating
    category: Optional[FeedbackCategory]
    comment: Optional[str]

    # Context about the response
    query: str
    response_preview: str              # First 200 chars of response
    response_language: str

    # Metadata
    device_type: str                   # desktop, mobile, etc.
    app_version: Optional[str]
    timestamp: datetime


class LLMFeedbackCollector:
    """
    Collects and analyzes user feedback on LLM responses.

    Used to:
    - Track user satisfaction
    - Identify areas for improvement
    - Monitor response quality over time
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            app_data = os.path.join(os.path.expanduser("~"), ".predict")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "llm_feedback.db")

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the feedback database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Main feedback table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feedback_id TEXT UNIQUE NOT NULL,
                    message_id INTEGER,
                    conversation_id TEXT,
                    user_id TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    category TEXT,
                    comment TEXT,
                    query TEXT,
                    response_preview TEXT,
                    response_language TEXT,
                    device_type TEXT,
                    app_version TEXT,
                    timestamp TEXT NOT NULL
                )
            """)

            # Indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_user
                ON llm_feedback(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_rating
                ON llm_feedback(rating)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
                ON llm_feedback(timestamp)
            """)

            # Daily metrics aggregation table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_daily_metrics (
                    metric_date TEXT NOT NULL,
                    total_feedback INTEGER DEFAULT 0,
                    thumbs_up INTEGER DEFAULT 0,
                    thumbs_down INTEGER DEFAULT 0,
                    neutral INTEGER DEFAULT 0,
                    satisfaction_rate REAL,
                    top_negative_category TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (metric_date)
                )
            """)

            conn.commit()

    def submit_feedback(
        self,
        user_id: str,
        rating: FeedbackRating,
        query: str,
        response: str,
        message_id: int = None,
        conversation_id: str = None,
        category: FeedbackCategory = None,
        comment: str = None,
        response_language: str = "en",
        device_type: str = "desktop",
        app_version: str = None
    ) -> str:
        """
        Submit feedback for an LLM response.

        Args:
            user_id: User submitting feedback
            rating: Thumbs up/down/neutral
            query: The original user query
            response: The LLM response (will be truncated for storage)
            message_id: Optional link to conversation history
            conversation_id: Optional conversation ID
            category: Category for negative feedback
            comment: Optional text comment
            response_language: Language of the response
            device_type: Device type
            app_version: App version

        Returns:
            feedback_id
        """
        import uuid
        feedback_id = str(uuid.uuid4())
        now = datetime.now()

        # Truncate response for preview
        response_preview = response[:200] + "..." if len(response) > 200 else response

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO llm_feedback
                (feedback_id, message_id, conversation_id, user_id, rating,
                 category, comment, query, response_preview, response_language,
                 device_type, app_version, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback_id,
                message_id,
                conversation_id,
                user_id,
                rating.value,
                category.value if category else None,
                comment,
                query,
                response_preview,
                response_language,
                device_type,
                app_version,
                now.isoformat()
            ))
            conn.commit()

        # Update daily metrics
        self._update_daily_metrics(now.strftime("%Y-%m-%d"))

        return feedback_id

    def thumbs_up(
        self,
        user_id: str,
        query: str,
        response: str,
        **kwargs
    ) -> str:
        """Shortcut for submitting thumbs up feedback"""
        return self.submit_feedback(
            user_id=user_id,
            rating=FeedbackRating.THUMBS_UP,
            query=query,
            response=response,
            **kwargs
        )

    def thumbs_down(
        self,
        user_id: str,
        query: str,
        response: str,
        category: FeedbackCategory = None,
        comment: str = None,
        **kwargs
    ) -> str:
        """Shortcut for submitting thumbs down feedback"""
        return self.submit_feedback(
            user_id=user_id,
            rating=FeedbackRating.THUMBS_DOWN,
            query=query,
            response=response,
            category=category,
            comment=comment,
            **kwargs
        )

    def get_user_feedback(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 50
    ) -> List[LLMFeedback]:
        """Get feedback submitted by a specific user"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM llm_feedback
                WHERE user_id = ?
                AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, since.isoformat(), limit))

            return [self._row_to_feedback(row) for row in cursor.fetchall()]

    def get_negative_feedback(
        self,
        days: int = 7,
        limit: int = 50
    ) -> List[LLMFeedback]:
        """Get recent negative feedback for review"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM llm_feedback
                WHERE rating = 'thumbs_down'
                AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (since.isoformat(), limit))

            return [self._row_to_feedback(row) for row in cursor.fetchall()]

    def get_satisfaction_rate(self, days: int = 30) -> Dict[str, Any]:
        """Calculate satisfaction rate over the specified period"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Count by rating
            cursor.execute("""
                SELECT rating, COUNT(*) as count
                FROM llm_feedback
                WHERE timestamp >= ?
                GROUP BY rating
            """, (since.isoformat(),))

            rating_counts = dict(cursor.fetchall())

            total = sum(rating_counts.values())
            thumbs_up = rating_counts.get(FeedbackRating.THUMBS_UP.value, 0)
            thumbs_down = rating_counts.get(FeedbackRating.THUMBS_DOWN.value, 0)

            satisfaction_rate = thumbs_up / total if total > 0 else 0

            return {
                "period_days": days,
                "total_feedback": total,
                "thumbs_up": thumbs_up,
                "thumbs_down": thumbs_down,
                "neutral": rating_counts.get(FeedbackRating.NEUTRAL.value, 0),
                "satisfaction_rate": satisfaction_rate,
                "satisfaction_percentage": f"{satisfaction_rate * 100:.1f}%"
            }

    def get_category_breakdown(self, days: int = 30) -> Dict[str, int]:
        """Get breakdown of negative feedback categories"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM llm_feedback
                WHERE rating = 'thumbs_down'
                AND timestamp >= ?
                AND category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """, (since.isoformat(),))

            return dict(cursor.fetchall())

    def get_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily satisfaction trends"""
        since = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM feedback_daily_metrics
                WHERE metric_date >= ?
                ORDER BY metric_date ASC
            """, (since.strftime("%Y-%m-%d"),))

            trends = []
            for row in cursor.fetchall():
                trends.append({
                    "date": row[0],
                    "total": row[1],
                    "thumbs_up": row[2],
                    "thumbs_down": row[3],
                    "neutral": row[4],
                    "satisfaction_rate": row[5]
                })

            return trends

    def get_improvement_suggestions(self, days: int = 30) -> List[str]:
        """Generate improvement suggestions based on feedback"""
        suggestions = []

        # Get satisfaction rate
        stats = self.get_satisfaction_rate(days)

        if stats["satisfaction_rate"] < 0.8:
            suggestions.append(
                f"Satisfaction rate is {stats['satisfaction_percentage']}. "
                "Consider reviewing negative feedback for patterns."
            )

        # Get category breakdown
        categories = self.get_category_breakdown(days)

        if categories:
            top_category = max(categories.items(), key=lambda x: x[1])
            category_name = top_category[0].replace("_", " ")
            count = top_category[1]

            suggestions.append(
                f"Most common complaint: '{category_name}' ({count} times). "
                "Focus improvement efforts here."
            )

            # Specific suggestions by category
            if top_category[0] == FeedbackCategory.INACCURATE.value:
                suggestions.append(
                    "High inaccuracy complaints. Review data validation and ensure "
                    "LLM has access to up-to-date vehicle data."
                )
            elif top_category[0] == FeedbackCategory.INCOMPLETE.value:
                suggestions.append(
                    "Responses marked as incomplete. Consider enhancing context "
                    "provided to LLM with more detailed information."
                )
            elif top_category[0] == FeedbackCategory.UNCLEAR.value:
                suggestions.append(
                    "Clarity issues reported. Consider simplifying response language "
                    "and adding more specific examples."
                )
            elif top_category[0] == FeedbackCategory.WRONG_LANGUAGE.value:
                suggestions.append(
                    "Language detection issues. Review language detection algorithm "
                    "and ensure proper bilingual prompt handling."
                )

        # Check for recent drops in satisfaction
        trends = self.get_trends(7)
        if len(trends) >= 2:
            recent_rate = trends[-1].get("satisfaction_rate", 0) or 0
            previous_rate = trends[-2].get("satisfaction_rate", 0) or 0

            if recent_rate < previous_rate - 0.1:
                suggestions.append(
                    "Satisfaction rate dropped recently. Check for any system changes "
                    "or data issues that might have affected quality."
                )

        if not suggestions:
            suggestions.append(
                "Feedback is positive! Continue monitoring and maintain current quality."
            )

        return suggestions

    def _update_daily_metrics(self, date_str: str):
        """Update daily aggregated metrics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Calculate metrics for the day
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN rating = 'thumbs_up' THEN 1 ELSE 0 END) as up,
                    SUM(CASE WHEN rating = 'thumbs_down' THEN 1 ELSE 0 END) as down,
                    SUM(CASE WHEN rating = 'neutral' THEN 1 ELSE 0 END) as neutral
                FROM llm_feedback
                WHERE timestamp LIKE ?
            """, (f"{date_str}%",))

            row = cursor.fetchone()
            total = row[0] or 0
            thumbs_up = row[1] or 0
            thumbs_down = row[2] or 0
            neutral = row[3] or 0

            satisfaction_rate = thumbs_up / total if total > 0 else None

            # Get top negative category
            cursor.execute("""
                SELECT category FROM llm_feedback
                WHERE timestamp LIKE ?
                AND rating = 'thumbs_down'
                AND category IS NOT NULL
                GROUP BY category
                ORDER BY COUNT(*) DESC
                LIMIT 1
            """, (f"{date_str}%",))

            top_category_row = cursor.fetchone()
            top_category = top_category_row[0] if top_category_row else None

            # Upsert metrics
            cursor.execute("""
                INSERT INTO feedback_daily_metrics
                (metric_date, total_feedback, thumbs_up, thumbs_down, neutral,
                 satisfaction_rate, top_negative_category, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric_date) DO UPDATE SET
                    total_feedback = excluded.total_feedback,
                    thumbs_up = excluded.thumbs_up,
                    thumbs_down = excluded.thumbs_down,
                    neutral = excluded.neutral,
                    satisfaction_rate = excluded.satisfaction_rate,
                    top_negative_category = excluded.top_negative_category
            """, (
                date_str,
                total,
                thumbs_up,
                thumbs_down,
                neutral,
                satisfaction_rate,
                top_category,
                datetime.now().isoformat()
            ))

            conn.commit()

    def _row_to_feedback(self, row: sqlite3.Row) -> LLMFeedback:
        """Convert database row to LLMFeedback object"""
        return LLMFeedback(
            id=row["id"],
            feedback_id=row["feedback_id"],
            message_id=row["message_id"],
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            rating=FeedbackRating(row["rating"]),
            category=FeedbackCategory(row["category"]) if row["category"] else None,
            comment=row["comment"],
            query=row["query"],
            response_preview=row["response_preview"],
            response_language=row["response_language"],
            device_type=row["device_type"],
            app_version=row["app_version"],
            timestamp=datetime.fromisoformat(row["timestamp"])
        )

    def export_feedback_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate a comprehensive feedback report"""
        return {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "satisfaction": self.get_satisfaction_rate(days),
            "category_breakdown": self.get_category_breakdown(days),
            "daily_trends": self.get_trends(days),
            "improvement_suggestions": self.get_improvement_suggestions(days)
        }

    def cleanup_old_feedback(self, days: int = 90) -> int:
        """Remove feedback older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM llm_feedback
                WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            deleted = cursor.rowcount
            conn.commit()
            return deleted


# Singleton instance
_feedback_collector: Optional[LLMFeedbackCollector] = None


def get_feedback_collector() -> LLMFeedbackCollector:
    """Get the singleton LLMFeedbackCollector instance"""
    global _feedback_collector
    if _feedback_collector is None:
        _feedback_collector = LLMFeedbackCollector()
    return _feedback_collector


# Convenience functions
def submit_thumbs_up(
    user_id: str,
    query: str,
    response: str,
    **kwargs
) -> str:
    """Submit a thumbs up for an LLM response"""
    collector = get_feedback_collector()
    return collector.thumbs_up(user_id, query, response, **kwargs)


def submit_thumbs_down(
    user_id: str,
    query: str,
    response: str,
    category: str = None,
    comment: str = None,
    **kwargs
) -> str:
    """Submit a thumbs down for an LLM response"""
    collector = get_feedback_collector()
    cat = FeedbackCategory(category) if category else None
    return collector.thumbs_down(user_id, query, response, cat, comment, **kwargs)


def get_satisfaction_stats(days: int = 30) -> Dict[str, Any]:
    """Get satisfaction statistics"""
    collector = get_feedback_collector()
    return collector.get_satisfaction_rate(days)
