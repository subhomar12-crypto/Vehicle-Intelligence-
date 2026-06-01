"""
LLM Conversation History
Stores and retrieves conversation history for 7-day memory.

This module provides:
1. Persistent conversation storage with SQLite
2. 7-day retention with automatic cleanup
3. User-specific conversation threads
4. Context retrieval for follow-up conversations
5. Bilingual support (English/Arabic)

Part of the PREDICT Vehicle Intelligence Platform.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import hashlib


class MessageRole(Enum):
    """Role of the message sender"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(Enum):
    """Status of a conversation"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class Message:
    """A single message in a conversation"""
    id: Optional[int]
    conversation_id: str
    role: MessageRole
    content: str
    language: str  # "en" or "ar"
    timestamp: datetime
    metadata: Optional[Dict[str, Any]]

    # Context that was used for this message
    context_summary: Optional[str]

    # References to entities discussed
    referenced_vehicles: List[str]
    referenced_drivers: List[str]
    referenced_notifications: List[str]


@dataclass
class Conversation:
    """A conversation thread"""
    id: str
    user_id: str
    title: Optional[str]
    status: ConversationStatus
    language: str  # Primary language
    created_at: datetime
    updated_at: datetime
    message_count: int
    summary: Optional[str]

    # Related entities for quick filtering
    profile_id: Optional[str]
    vehicle_ids: List[str]
    driver_ids: List[str]


class LLMConversationHistory:
    """
    Manages conversation history with 7-day retention.

    Features:
    - Store conversations per user
    - 7-day memory window
    - Retrieve relevant past context
    - Support for bilingual conversations
    """

    # Default retention period
    DEFAULT_RETENTION_DAYS = 7

    def __init__(self, db_path: str = None, retention_days: int = None):
        if db_path is None:
            app_data = os.path.join(os.path.expanduser("~"), ".predict")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "conversation_history.db")

        self.db_path = db_path
        self.retention_days = retention_days or self.DEFAULT_RETENTION_DAYS
        self._init_database()

    def _init_database(self):
        """Initialize the conversation database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    status TEXT DEFAULT 'active',
                    language TEXT DEFAULT 'en',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    summary TEXT,
                    profile_id TEXT,
                    vehicle_ids TEXT,
                    driver_ids TEXT
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    language TEXT DEFAULT 'en',
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    context_summary TEXT,
                    referenced_vehicles TEXT,
                    referenced_drivers TEXT,
                    referenced_notifications TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_user
                ON conversations(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_updated
                ON conversations(updated_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_msg_conv
                ON messages(conversation_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_msg_timestamp
                ON messages(timestamp)
            """)

            conn.commit()

    def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
        language: str = "en",
        profile_id: str = None,
        vehicle_ids: List[str] = None,
        driver_ids: List[str] = None
    ) -> str:
        """Create a new conversation thread"""
        import uuid
        conversation_id = str(uuid.uuid4())
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations
                (id, user_id, title, status, language, created_at, updated_at,
                 message_count, profile_id, vehicle_ids, driver_ids)
                VALUES (?, ?, ?, 'active', ?, ?, ?, 0, ?, ?, ?)
            """, (
                conversation_id,
                user_id,
                title,
                language,
                now.isoformat(),
                now.isoformat(),
                profile_id,
                json.dumps(vehicle_ids or []),
                json.dumps(driver_ids or [])
            ))
            conn.commit()

        return conversation_id

    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        language: str = "en",
        context_summary: str = None,
        metadata: Dict[str, Any] = None,
        referenced_vehicles: List[str] = None,
        referenced_drivers: List[str] = None,
        referenced_notifications: List[str] = None
    ) -> int:
        """Add a message to a conversation"""
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Insert message
            cursor.execute("""
                INSERT INTO messages
                (conversation_id, role, content, language, timestamp, metadata,
                 context_summary, referenced_vehicles, referenced_drivers, referenced_notifications)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conversation_id,
                role.value,
                content,
                language,
                now.isoformat(),
                json.dumps(metadata) if metadata else None,
                context_summary,
                json.dumps(referenced_vehicles or []),
                json.dumps(referenced_drivers or []),
                json.dumps(referenced_notifications or [])
            ))
            message_id = cursor.lastrowid

            # Update conversation
            cursor.execute("""
                UPDATE conversations
                SET updated_at = ?,
                    message_count = message_count + 1
                WHERE id = ?
            """, (now.isoformat(), conversation_id))

            # Update referenced entities in conversation
            if referenced_vehicles or referenced_drivers:
                self._update_conversation_entities(
                    cursor, conversation_id, referenced_vehicles, referenced_drivers
                )

            conn.commit()

        return message_id

    def _update_conversation_entities(
        self,
        cursor,
        conversation_id: str,
        vehicles: List[str] = None,
        drivers: List[str] = None
    ):
        """Update conversation's referenced entities"""
        cursor.execute(
            "SELECT vehicle_ids, driver_ids FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        row = cursor.fetchone()
        if not row:
            return

        existing_vehicles = set(json.loads(row[0]) if row[0] else [])
        existing_drivers = set(json.loads(row[1]) if row[1] else [])

        if vehicles:
            existing_vehicles.update(vehicles)
        if drivers:
            existing_drivers.update(drivers)

        cursor.execute("""
            UPDATE conversations
            SET vehicle_ids = ?, driver_ids = ?
            WHERE id = ?
        """, (
            json.dumps(list(existing_vehicles)),
            json.dumps(list(existing_drivers)),
            conversation_id
        ))

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_conversation(row)

    def get_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Message]:
        """Get messages in a conversation"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
            """, (conversation_id, limit, offset))

            return [self._row_to_message(row) for row in cursor.fetchall()]

    def get_recent_conversations(
        self,
        user_id: str,
        limit: int = 10,
        include_archived: bool = False
    ) -> List[Conversation]:
        """Get recent conversations for a user"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if include_archived:
                cursor.execute("""
                    SELECT * FROM conversations
                    WHERE user_id = ?
                    AND updated_at >= ?
                    AND status != 'deleted'
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (user_id, cutoff.isoformat(), limit))
            else:
                cursor.execute("""
                    SELECT * FROM conversations
                    WHERE user_id = ?
                    AND updated_at >= ?
                    AND status = 'active'
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (user_id, cutoff.isoformat(), limit))

            return [self._row_to_conversation(row) for row in cursor.fetchall()]

    def get_conversation_context(
        self,
        conversation_id: str,
        max_messages: int = 10
    ) -> Dict[str, Any]:
        """
        Get context from a conversation for continuing the discussion.

        This retrieves recent messages formatted for injection into LLM context.
        """
        messages = self.get_messages(conversation_id, limit=max_messages)
        conversation = self.get_conversation(conversation_id)

        if not conversation:
            return {"error": "Conversation not found"}

        # Format messages for context
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "language": msg.language
            })

        # Get referenced entities
        all_vehicles = set()
        all_drivers = set()
        all_notifications = set()

        for msg in messages:
            all_vehicles.update(msg.referenced_vehicles or [])
            all_drivers.update(msg.referenced_drivers or [])
            all_notifications.update(msg.referenced_notifications or [])

        return {
            "conversation_id": conversation_id,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "language": conversation.language,
            "message_count": len(formatted_messages),
            "messages": formatted_messages,
            "referenced_entities": {
                "vehicles": list(all_vehicles),
                "drivers": list(all_drivers),
                "notifications": list(all_notifications),
            },
            "summary": conversation.summary
        }

    def search_conversations(
        self,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> List[Conversation]:
        """Search conversations by content"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Search in message content
            cursor.execute("""
                SELECT DISTINCT c.* FROM conversations c
                INNER JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = ?
                AND c.updated_at >= ?
                AND c.status = 'active'
                AND m.content LIKE ?
                ORDER BY c.updated_at DESC
                LIMIT ?
            """, (user_id, cutoff.isoformat(), f"%{query}%", limit))

            return [self._row_to_conversation(row) for row in cursor.fetchall()]

    def get_conversations_by_vehicle(
        self,
        user_id: str,
        vehicle_id: str,
        limit: int = 10
    ) -> List[Conversation]:
        """Get conversations related to a specific vehicle"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM conversations
                WHERE user_id = ?
                AND updated_at >= ?
                AND status = 'active'
                AND vehicle_ids LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (user_id, cutoff.isoformat(), f'%"{vehicle_id}"%', limit))

            return [self._row_to_conversation(row) for row in cursor.fetchall()]

    def update_conversation_title(self, conversation_id: str, title: str) -> bool:
        """Update conversation title"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
            """, (title, datetime.now().isoformat(), conversation_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_conversation_summary(self, conversation_id: str, summary: str) -> bool:
        """Update conversation summary (for LLM context)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations
                SET summary = ?, updated_at = ?
                WHERE id = ?
            """, (summary, datetime.now().isoformat(), conversation_id))
            conn.commit()
            return cursor.rowcount > 0

    def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a conversation"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations
                SET status = 'archived', updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), conversation_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_conversation(self, conversation_id: str) -> bool:
        """Soft delete a conversation"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations
                SET status = 'deleted', updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), conversation_id))
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_old_conversations(self) -> int:
        """Remove conversations older than retention period"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Delete old messages first
            cursor.execute("""
                DELETE FROM messages
                WHERE conversation_id IN (
                    SELECT id FROM conversations
                    WHERE updated_at < ?
                )
            """, (cutoff.isoformat(),))
            messages_deleted = cursor.rowcount

            # Delete old conversations
            cursor.execute("""
                DELETE FROM conversations
                WHERE updated_at < ?
            """, (cutoff.isoformat(),))
            conversations_deleted = cursor.rowcount

            conn.commit()

            return conversations_deleted

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get conversation statistics for a user"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Conversation count
            cursor.execute("""
                SELECT COUNT(*) FROM conversations
                WHERE user_id = ? AND updated_at >= ? AND status = 'active'
            """, (user_id, cutoff.isoformat()))
            conv_count = cursor.fetchone()[0]

            # Message count
            cursor.execute("""
                SELECT COUNT(*) FROM messages m
                INNER JOIN conversations c ON m.conversation_id = c.id
                WHERE c.user_id = ? AND c.updated_at >= ? AND c.status = 'active'
            """, (user_id, cutoff.isoformat()))
            msg_count = cursor.fetchone()[0]

            # Language distribution
            cursor.execute("""
                SELECT language, COUNT(*) FROM conversations
                WHERE user_id = ? AND updated_at >= ? AND status = 'active'
                GROUP BY language
            """, (user_id, cutoff.isoformat()))
            lang_dist = dict(cursor.fetchall())

            return {
                "user_id": user_id,
                "retention_days": self.retention_days,
                "conversation_count": conv_count,
                "message_count": msg_count,
                "language_distribution": lang_dist
            }

    def format_history_for_prompt(
        self,
        conversation_id: str,
        max_messages: int = 10,
        include_context: bool = True
    ) -> str:
        """
        Format conversation history for injection into LLM prompt.

        Returns a formatted string suitable for the LLM context window.
        """
        context = self.get_conversation_context(conversation_id, max_messages)

        if "error" in context:
            return ""

        parts = []

        # Add conversation summary if available
        if include_context and context.get("summary"):
            parts.append(f"=== CONVERSATION SUMMARY ===")
            parts.append(context["summary"])
            parts.append("")

        # Add message history
        parts.append("=== CONVERSATION HISTORY ===")
        for msg in context.get("messages", []):
            role = msg["role"].upper()
            content = msg["content"]
            parts.append(f"[{role}]: {content}")
        parts.append("")

        # Add referenced entities note
        if context.get("referenced_entities"):
            entities = context["referenced_entities"]
            if any(entities.values()):
                parts.append("=== ENTITIES DISCUSSED ===")
                if entities.get("vehicles"):
                    parts.append(f"Vehicles: {', '.join(entities['vehicles'])}")
                if entities.get("drivers"):
                    parts.append(f"Drivers: {', '.join(entities['drivers'])}")
                if entities.get("notifications"):
                    parts.append(f"Notifications: {', '.join(entities['notifications'])}")
                parts.append("")

        return "\n".join(parts)

    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        """Convert database row to Conversation object"""
        return Conversation(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            status=ConversationStatus(row["status"]),
            language=row["language"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            message_count=row["message_count"],
            summary=row["summary"],
            profile_id=row["profile_id"],
            vehicle_ids=json.loads(row["vehicle_ids"]) if row["vehicle_ids"] else [],
            driver_ids=json.loads(row["driver_ids"]) if row["driver_ids"] else []
        )

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        """Convert database row to Message object"""
        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            language=row["language"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            context_summary=row["context_summary"],
            referenced_vehicles=json.loads(row["referenced_vehicles"]) if row["referenced_vehicles"] else [],
            referenced_drivers=json.loads(row["referenced_drivers"]) if row["referenced_drivers"] else [],
            referenced_notifications=json.loads(row["referenced_notifications"]) if row["referenced_notifications"] else []
        )


# Singleton instance
_history: Optional[LLMConversationHistory] = None


def get_conversation_history() -> LLMConversationHistory:
    """Get the singleton LLMConversationHistory instance"""
    global _history
    if _history is None:
        _history = LLMConversationHistory()
    return _history


# Convenience functions
def start_conversation(
    user_id: str,
    first_message: str,
    language: str = "en",
    profile_id: str = None
) -> str:
    """Start a new conversation with an initial user message"""
    history = get_conversation_history()
    conv_id = history.create_conversation(
        user_id=user_id,
        language=language,
        profile_id=profile_id
    )
    history.add_message(
        conversation_id=conv_id,
        role=MessageRole.USER,
        content=first_message,
        language=language
    )
    return conv_id


def continue_conversation(
    conversation_id: str,
    user_message: str,
    assistant_response: str,
    language: str = "en",
    context_summary: str = None,
    referenced_vehicles: List[str] = None,
    referenced_drivers: List[str] = None,
    referenced_notifications: List[str] = None
):
    """Add a user message and assistant response to a conversation"""
    history = get_conversation_history()

    # Add user message
    history.add_message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=user_message,
        language=language
    )

    # Add assistant response
    history.add_message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=assistant_response,
        language=language,
        context_summary=context_summary,
        referenced_vehicles=referenced_vehicles,
        referenced_drivers=referenced_drivers,
        referenced_notifications=referenced_notifications
    )
