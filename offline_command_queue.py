"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Offline Command Queue

Offline Command Queue
Queue and retry system for commands when devices are offline.
"""

import logging
import sqlite3
import threading
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class CommandStatus(Enum):
    """Command execution status"""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CommandType(Enum):
    """Types of commands that can be queued"""
    READ_DTC = "read_dtc"
    CLEAR_DTC = "clear_dtc"
    READ_SENSOR = "read_sensor"
    UPDATE_CONFIG = "update_config"
    REQUEST_DATA = "request_data"
    SYNC_PROFILE = "sync_profile"
    CUSTOM = "custom"


@dataclass
class QueuedCommand:
    """Represents a queued command"""
    command_id: str
    device_id: str
    profile_id: int
    command_type: CommandType
    parameters: Dict[str, Any]
    status: CommandStatus
    priority: int  # Higher = more important
    created_at: datetime
    expires_at: datetime
    retry_count: int
    max_retries: int
    last_attempt: Optional[datetime]
    response: Optional[Dict[str, Any]]
    error: Optional[str]


class OfflineCommandQueue:
    """
    Manages command queueing and retry for offline devices.

    Features:
    - Persistent command storage
    - Priority-based execution
    - Automatic retry with backoff
    - Expiration handling
    - Delivery confirmation
    """

    # Configuration
    DEFAULT_EXPIRY_HOURS = 24
    MAX_RETRIES = 5
    RETRY_BACKOFF_BASE = 30  # seconds
    CHECK_INTERVAL = 10  # seconds

    def __init__(self):
        self.db_path = CONFIG.DATA_DIR / "command_queue.db"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._delivery_handlers: Dict[str, Callable] = {}

        self._init_database()
        logger.info("OfflineCommandQueue initialized")

    def _init_database(self):
        """Initialize command queue database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS command_queue (
                command_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                profile_id INTEGER,
                command_type TEXT NOT NULL,
                parameters TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                created_at TEXT,
                expires_at TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 5,
                last_attempt TEXT,
                response TEXT,
                error TEXT
            )
        ''')

        c.execute('CREATE INDEX IF NOT EXISTS idx_queue_device ON command_queue(device_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_queue_status ON command_queue(status)')

        conn.commit()
        conn.close()

    def start(self):
        """Start the queue processor"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        logger.info("Command queue processor started")

    def stop(self):
        """Stop the queue processor"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Command queue processor stopped")

    def register_delivery_handler(self, device_id: str, handler: Callable[[QueuedCommand], bool]):
        """
        Register a handler to deliver commands to a specific device.

        Args:
            device_id: Device identifier
            handler: Callback that returns True if command was delivered
        """
        with self._lock:
            self._delivery_handlers[device_id] = handler

    def unregister_delivery_handler(self, device_id: str):
        """Unregister delivery handler for a device"""
        with self._lock:
            self._delivery_handlers.pop(device_id, None)

    def queue_command(self, device_id: str, profile_id: int, command_type: CommandType,
                      parameters: Dict[str, Any] = None, priority: int = 0,
                      expiry_hours: int = None, max_retries: int = None) -> str:
        """
        Queue a command for a device.

        Args:
            device_id: Target device ID
            profile_id: Associated profile ID
            command_type: Type of command
            parameters: Command parameters
            priority: Execution priority (higher = first)
            expiry_hours: Hours until command expires
            max_retries: Maximum delivery attempts

        Returns:
            command_id
        """
        import uuid

        command_id = str(uuid.uuid4())
        now = datetime.now()
        expires_at = now + timedelta(hours=expiry_hours or self.DEFAULT_EXPIRY_HOURS)

        command = QueuedCommand(
            command_id=command_id,
            device_id=device_id,
            profile_id=profile_id,
            command_type=command_type,
            parameters=parameters or {},
            status=CommandStatus.PENDING,
            priority=priority,
            created_at=now,
            expires_at=expires_at,
            retry_count=0,
            max_retries=max_retries or self.MAX_RETRIES,
            last_attempt=None,
            response=None,
            error=None
        )

        self._save_command(command)
        logger.info(f"Queued command {command_id} for device {device_id}: {command_type.value}")

        # Try immediate delivery if handler available
        self._try_deliver(command)

        return command_id

    def get_pending_commands(self, device_id: str) -> List[QueuedCommand]:
        """Get all pending commands for a device"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('''
                SELECT * FROM command_queue
                WHERE device_id = ? AND status IN ('pending', 'queued')
                ORDER BY priority DESC, created_at ASC
            ''', (device_id,))

            rows = c.fetchall()
            conn.close()

            return [self._row_to_command(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting pending commands: {e}")
            return []

    def mark_delivered(self, command_id: str, response: Dict[str, Any] = None):
        """Mark a command as delivered"""
        self._update_status(command_id, CommandStatus.DELIVERED, response=response)

    def mark_executed(self, command_id: str, response: Dict[str, Any] = None):
        """Mark a command as executed successfully"""
        self._update_status(command_id, CommandStatus.EXECUTED, response=response)

    def mark_failed(self, command_id: str, error: str):
        """Mark a command as failed"""
        self._update_status(command_id, CommandStatus.FAILED, error=error)

    def cancel_command(self, command_id: str):
        """Cancel a pending command"""
        self._update_status(command_id, CommandStatus.CANCELLED)

    def get_command_status(self, command_id: str) -> Optional[QueuedCommand]:
        """Get current status of a command"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('SELECT * FROM command_queue WHERE command_id = ?', (command_id,))
            row = c.fetchone()
            conn.close()

            return self._row_to_command(row) if row else None

        except Exception as e:
            logger.error(f"Error getting command status: {e}")
            return None

    def _process_loop(self):
        """Main processing loop for retry and expiration"""
        while self._running:
            try:
                self._expire_old_commands()
                self._retry_pending_commands()
            except Exception as e:
                logger.error(f"Error in command queue processor: {e}")

            time.sleep(self.CHECK_INTERVAL)

    def _expire_old_commands(self):
        """Mark expired commands"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            now = datetime.now().isoformat()
            c.execute('''
                UPDATE command_queue
                SET status = ?
                WHERE status IN ('pending', 'queued') AND expires_at < ?
            ''', (CommandStatus.EXPIRED.value, now))

            expired = c.rowcount
            conn.commit()
            conn.close()

            if expired > 0:
                logger.info(f"Expired {expired} commands")

        except Exception as e:
            logger.error(f"Error expiring commands: {e}")

    def _retry_pending_commands(self):
        """Retry pending commands that are ready for retry"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get commands ready for retry
            c.execute('''
                SELECT * FROM command_queue
                WHERE status IN ('pending', 'queued') AND retry_count < max_retries
                ORDER BY priority DESC, created_at ASC
                LIMIT 10
            ''')

            rows = c.fetchall()
            conn.close()

            for row in rows:
                command = self._row_to_command(row)

                # Check if ready for retry (exponential backoff)
                if command.last_attempt:
                    backoff = self.RETRY_BACKOFF_BASE * (2 ** command.retry_count)
                    next_retry = command.last_attempt + timedelta(seconds=backoff)
                    if datetime.now() < next_retry:
                        continue

                self._try_deliver(command)

        except Exception as e:
            logger.error(f"Error retrying commands: {e}")

    def _try_deliver(self, command: QueuedCommand):
        """Attempt to deliver a command"""
        with self._lock:
            handler = self._delivery_handlers.get(command.device_id)

        if handler:
            try:
                # Increment retry count
                command.retry_count += 1
                command.last_attempt = datetime.now()
                command.status = CommandStatus.QUEUED

                if handler(command):
                    command.status = CommandStatus.SENT
                    logger.info(f"Command {command.command_id} sent to device {command.device_id}")
                else:
                    logger.debug(f"Command {command.command_id} delivery failed, will retry")

            except Exception as e:
                logger.error(f"Error delivering command {command.command_id}: {e}")
                command.error = str(e)

            self._save_command(command)

    def _save_command(self, command: QueuedCommand):
        """Save command to database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT OR REPLACE INTO command_queue
                (command_id, device_id, profile_id, command_type, parameters, status,
                 priority, created_at, expires_at, retry_count, max_retries,
                 last_attempt, response, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                command.command_id,
                command.device_id,
                command.profile_id,
                command.command_type.value,
                json.dumps(command.parameters),
                command.status.value,
                command.priority,
                command.created_at.isoformat(),
                command.expires_at.isoformat(),
                command.retry_count,
                command.max_retries,
                command.last_attempt.isoformat() if command.last_attempt else None,
                json.dumps(command.response) if command.response else None,
                command.error
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error saving command: {e}")

    def _update_status(self, command_id: str, status: CommandStatus,
                       response: Dict[str, Any] = None, error: str = None):
        """Update command status"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                UPDATE command_queue
                SET status = ?, response = ?, error = ?
                WHERE command_id = ?
            ''', (
                status.value,
                json.dumps(response) if response else None,
                error,
                command_id
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error updating command status: {e}")

    def _row_to_command(self, row) -> QueuedCommand:
        """Convert database row to QueuedCommand"""
        return QueuedCommand(
            command_id=row['command_id'],
            device_id=row['device_id'],
            profile_id=row['profile_id'],
            command_type=CommandType(row['command_type']),
            parameters=json.loads(row['parameters']) if row['parameters'] else {},
            status=CommandStatus(row['status']),
            priority=row['priority'],
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']),
            retry_count=row['retry_count'],
            max_retries=row['max_retries'],
            last_attempt=datetime.fromisoformat(row['last_attempt']) if row['last_attempt'] else None,
            response=json.loads(row['response']) if row['response'] else None,
            error=row['error']
        )

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            stats = {}
            for status in CommandStatus:
                c.execute('SELECT COUNT(*) FROM command_queue WHERE status = ?', (status.value,))
                stats[status.value] = c.fetchone()[0]

            c.execute('SELECT COUNT(DISTINCT device_id) FROM command_queue')
            stats['unique_devices'] = c.fetchone()[0]

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}


# Singleton instance
_command_queue: Optional[OfflineCommandQueue] = None


def get_command_queue() -> OfflineCommandQueue:
    """Get the singleton OfflineCommandQueue instance."""
    global _command_queue
    if _command_queue is None:
        _command_queue = OfflineCommandQueue()
    return _command_queue
