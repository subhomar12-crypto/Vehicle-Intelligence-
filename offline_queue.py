"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Offline Sync Queue
Purpose: Persistent queue for operations when server is unreachable, with auto-sync on reconnection
"""

import json
import os
import time
import uuid
import sqlite3
import logging
import threading
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from PySide6.QtCore import QObject, Signal

# Configure logging
queue_logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of operations that can be queued"""
    DRIVER_CREATE = "driver_create"
    DRIVER_UPDATE = "driver_update"
    DRIVER_DELETE = "driver_delete"
    DRIVER_LINK = "driver_link"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PROFILE_UPDATE = "profile_update"
    TELEMETRY = "telemetry"
    CUSTOM = "custom"


class OperationStatus(Enum):
    """Status of queued operations"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueuedOperation:
    """Represents a queued offline operation"""
    id: int
    operation_type: str
    payload: Dict[str, Any]
    idempotency_key: str
    endpoint: str
    method: str
    created_at: float
    retry_count: int
    last_error: Optional[str]
    status: str
    priority: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OfflineSyncQueue(QObject):
    """
    Persistent queue for offline operations.

    Features:
    - SQLite-based persistence
    - Automatic retry with exponential backoff
    - Idempotency key support
    - Priority ordering
    - Maximum queue size enforcement
    - Statistics and monitoring
    """

    # Signals
    operation_queued = Signal(str)           # operation_id
    operation_completed = Signal(str)        # operation_id
    operation_failed = Signal(str, str)      # operation_id, error
    sync_started = Signal(int)               # pending_count
    sync_completed = Signal(int, int)        # success_count, fail_count
    queue_size_changed = Signal(int)         # new_size

    # Configuration
    MAX_QUEUE_SIZE = 1000
    MAX_RETRIES = 5
    BASE_RETRY_DELAY = 2  # seconds
    MAX_RETRY_DELAY = 300  # 5 minutes

    def __init__(self, db_path: str = './data/offline_queue.db', parent=None):
        super().__init__(parent)

        self.db_path = db_path
        self._lock = threading.Lock()
        self._is_syncing = False

        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        queue_logger.info(f"OfflineSyncQueue initialized with database: {db_path}")

    def _init_database(self):
        """Initialize the SQLite database for queue persistence"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create operations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT DEFAULT 'POST',
                created_at REAL NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_retry_at REAL,
                last_error TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                completed_at REAL
            )
        ''')

        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_pending_status
            ON pending_operations(status)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_pending_priority
            ON pending_operations(priority, created_at)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_idempotency
            ON pending_operations(idempotency_key)
        ''')

        # Create sync history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at REAL NOT NULL,
                completed_at REAL,
                operations_processed INTEGER DEFAULT 0,
                operations_succeeded INTEGER DEFAULT 0,
                operations_failed INTEGER DEFAULT 0,
                error_message TEXT
            )
        ''')

        conn.commit()
        conn.close()

        queue_logger.info("Offline queue database initialized")

    def queue_operation(
        self,
        operation_type: str,
        payload: Dict[str, Any],
        idempotency_key: str = None,
        endpoint: str = "/api/sync",
        method: str = "POST",
        priority: int = 5
    ) -> Optional[int]:
        """
        Queue an operation for later sync.

        Args:
            operation_type: Type of operation (e.g., 'driver_create')
            payload: JSON-serializable data for the operation
            idempotency_key: Unique key to prevent duplicate processing
            endpoint: API endpoint to call
            method: HTTP method
            priority: 1 (highest) to 10 (lowest)

        Returns:
            Operation ID if queued, None if queue is full or duplicate
        """
        # Generate idempotency key if not provided
        if idempotency_key is None:
            idempotency_key = f"{operation_type}_{uuid.uuid4()}"

        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Check queue size
                cursor.execute(
                    "SELECT COUNT(*) FROM pending_operations WHERE status = 'pending'"
                )
                current_size = cursor.fetchone()[0]

                if current_size >= self.MAX_QUEUE_SIZE:
                    queue_logger.warning(f"Queue full ({current_size}), cannot add operation")
                    conn.close()
                    return None

                # Check for duplicate idempotency key
                cursor.execute(
                    "SELECT id FROM pending_operations WHERE idempotency_key = ?",
                    (idempotency_key,)
                )
                if cursor.fetchone():
                    queue_logger.debug(f"Duplicate idempotency key: {idempotency_key}")
                    conn.close()
                    return None

                # Insert operation
                cursor.execute('''
                    INSERT INTO pending_operations (
                        operation_type, payload, idempotency_key, endpoint,
                        method, created_at, status, priority
                    ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                ''', (
                    operation_type,
                    json.dumps(payload),
                    idempotency_key,
                    endpoint,
                    method,
                    time.time(),
                    priority
                ))

                operation_id = cursor.lastrowid
                conn.commit()
                conn.close()

                queue_logger.info(f"Queued operation {operation_id}: {operation_type}")
                self.operation_queued.emit(str(operation_id))
                self.queue_size_changed.emit(current_size + 1)

                return operation_id

            except Exception as e:
                queue_logger.error(f"Error queuing operation: {e}")
                return None

    def get_pending_operations(self, limit: int = 100) -> List[QueuedOperation]:
        """Get pending operations ordered by priority and age"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, operation_type, payload, idempotency_key, endpoint,
                   method, created_at, retry_count, last_error, status, priority
            FROM pending_operations
            WHERE status = 'pending'
            ORDER BY priority ASC, created_at ASC
            LIMIT ?
        ''', (limit,))

        operations = []
        for row in cursor.fetchall():
            operations.append(QueuedOperation(
                id=row['id'],
                operation_type=row['operation_type'],
                payload=json.loads(row['payload']),
                idempotency_key=row['idempotency_key'],
                endpoint=row['endpoint'],
                method=row['method'],
                created_at=row['created_at'],
                retry_count=row['retry_count'],
                last_error=row['last_error'],
                status=row['status'],
                priority=row['priority']
            ))

        conn.close()
        return operations

    def process_queue(self, sync_service) -> Tuple[int, int]:
        """
        Process all pending operations using the provided sync service.

        Args:
            sync_service: Service with _make_request method for API calls

        Returns:
            Tuple of (success_count, failure_count)
        """
        if self._is_syncing:
            queue_logger.warning("Sync already in progress")
            return 0, 0

        self._is_syncing = True
        success_count = 0
        failure_count = 0

        try:
            pending = self.get_pending_operations()

            if not pending:
                queue_logger.info("No pending operations to sync")
                return 0, 0

            self.sync_started.emit(len(pending))
            queue_logger.info(f"Starting sync of {len(pending)} pending operations")

            # Start sync history record
            sync_id = self._start_sync_record()

            for operation in pending:
                # Check retry count
                if operation.retry_count >= self.MAX_RETRIES:
                    self._mark_failed(operation.id, "Max retries exceeded")
                    failure_count += 1
                    continue

                # Calculate retry delay (exponential backoff)
                if operation.retry_count > 0:
                    delay = min(
                        self.BASE_RETRY_DELAY * (2 ** operation.retry_count),
                        self.MAX_RETRY_DELAY
                    )
                    time.sleep(delay)

                # Mark as processing
                self._update_status(operation.id, 'processing')

                # Attempt to sync
                try:
                    success, response = sync_service._make_request(
                        operation.method,
                        operation.endpoint,
                        data=operation.payload,
                        idempotency_key=operation.idempotency_key
                    )

                    if success:
                        self._mark_completed(operation.id)
                        success_count += 1
                        self.operation_completed.emit(str(operation.id))
                        queue_logger.info(
                            f"Synced operation {operation.id}: {operation.operation_type}"
                        )
                    else:
                        error_msg = str(response)
                        self._increment_retry(operation.id, error_msg)
                        failure_count += 1
                        self.operation_failed.emit(str(operation.id), error_msg)
                        queue_logger.warning(
                            f"Failed operation {operation.id}: {error_msg}"
                        )

                except Exception as e:
                    error_msg = str(e)
                    self._increment_retry(operation.id, error_msg)
                    failure_count += 1
                    self.operation_failed.emit(str(operation.id), error_msg)
                    queue_logger.error(f"Error processing operation {operation.id}: {e}")

            # Complete sync history record
            self._complete_sync_record(sync_id, len(pending), success_count, failure_count)

            self.sync_completed.emit(success_count, failure_count)
            queue_logger.info(
                f"Sync completed: {success_count} succeeded, {failure_count} failed"
            )

        finally:
            self._is_syncing = False

        return success_count, failure_count

    def _update_status(self, operation_id: int, status: str):
        """Update operation status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE pending_operations SET status = ? WHERE id = ?",
            (status, operation_id)
        )
        conn.commit()
        conn.close()

    def _mark_completed(self, operation_id: int):
        """Mark operation as completed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pending_operations
            SET status = 'completed', completed_at = ?
            WHERE id = ?
        ''', (time.time(), operation_id))
        conn.commit()
        conn.close()

    def _mark_failed(self, operation_id: int, error: str):
        """Mark operation as permanently failed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pending_operations
            SET status = 'failed', last_error = ?, completed_at = ?
            WHERE id = ?
        ''', (error, time.time(), operation_id))
        conn.commit()
        conn.close()

    def _increment_retry(self, operation_id: int, error: str):
        """Increment retry count and record error"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pending_operations
            SET retry_count = retry_count + 1,
                last_retry_at = ?,
                last_error = ?,
                status = 'pending'
            WHERE id = ?
        ''', (time.time(), error, operation_id))
        conn.commit()
        conn.close()

    def _start_sync_record(self) -> int:
        """Start a sync history record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sync_history (started_at) VALUES (?)",
            (time.time(),)
        )
        sync_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return sync_id

    def _complete_sync_record(
        self, sync_id: int, total: int, success: int, failed: int
    ):
        """Complete a sync history record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE sync_history
            SET completed_at = ?,
                operations_processed = ?,
                operations_succeeded = ?,
                operations_failed = ?
            WHERE id = ?
        ''', (time.time(), total, success, failed, sync_id))
        conn.commit()
        conn.close()

    def get_pending_count(self) -> int:
        """Get count of pending operations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM pending_operations WHERE status = 'pending'"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Pending count
        cursor.execute(
            "SELECT COUNT(*) FROM pending_operations WHERE status = 'pending'"
        )
        stats['pending'] = cursor.fetchone()[0]

        # Completed count
        cursor.execute(
            "SELECT COUNT(*) FROM pending_operations WHERE status = 'completed'"
        )
        stats['completed'] = cursor.fetchone()[0]

        # Failed count
        cursor.execute(
            "SELECT COUNT(*) FROM pending_operations WHERE status = 'failed'"
        )
        stats['failed'] = cursor.fetchone()[0]

        # By operation type
        cursor.execute('''
            SELECT operation_type, COUNT(*) as count
            FROM pending_operations
            WHERE status = 'pending'
            GROUP BY operation_type
        ''')
        stats['by_type'] = dict(cursor.fetchall())

        # Recent sync history
        cursor.execute('''
            SELECT started_at, completed_at, operations_processed,
                   operations_succeeded, operations_failed
            FROM sync_history
            ORDER BY started_at DESC
            LIMIT 5
        ''')
        stats['recent_syncs'] = [
            {
                'started_at': row[0],
                'completed_at': row[1],
                'processed': row[2],
                'succeeded': row[3],
                'failed': row[4]
            }
            for row in cursor.fetchall()
        ]

        stats['is_syncing'] = self._is_syncing

        conn.close()
        return stats

    def clear_completed(self, older_than_days: int = 7):
        """Remove completed operations older than specified days"""
        cutoff = time.time() - (older_than_days * 24 * 60 * 60)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM pending_operations
            WHERE status = 'completed' AND completed_at < ?
        ''', (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        queue_logger.info(f"Cleared {deleted} completed operations")
        return deleted

    def cancel_operation(self, operation_id: int) -> bool:
        """Cancel a pending operation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pending_operations
            SET status = 'cancelled', completed_at = ?
            WHERE id = ? AND status = 'pending'
        ''', (time.time(), operation_id))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def clear_all_pending(self) -> int:
        """Clear all pending operations (use with caution)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM pending_operations WHERE status = 'pending'"
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        queue_logger.warning(f"Cleared {deleted} pending operations")
        self.queue_size_changed.emit(0)
        return deleted


# Singleton instance
_queue_instance: Optional[OfflineSyncQueue] = None


def get_offline_queue() -> OfflineSyncQueue:
    """Get or create the global offline queue instance"""
    global _queue_instance

    if _queue_instance is None:
        _queue_instance = OfflineSyncQueue()

    return _queue_instance


if __name__ == "__main__":
    # Test the offline queue
    logging.basicConfig(level=logging.DEBUG)

    queue = OfflineSyncQueue(db_path='./test_queue.db')

    # Queue some test operations
    for i in range(5):
        queue.queue_operation(
            'test_operation',
            {'test_id': i, 'data': f'Test data {i}'},
            endpoint='/api/test'
        )

    print(f"Pending: {queue.get_pending_count()}")
    print(f"Stats: {queue.get_statistics()}")

    # Get pending
    pending = queue.get_pending_operations()
    for op in pending:
        print(f"  {op.id}: {op.operation_type}")
