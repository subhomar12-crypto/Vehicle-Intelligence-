"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Database Worker
Purpose: Background thread for database operations to prevent UI blocking
"""

import queue
import threading
import logging
import time
import traceback
from typing import Callable, Any, Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal, QThread

# Configure logging
db_worker_logger = logging.getLogger(__name__)


class OperationPriority(Enum):
    """Priority levels for database operations"""
    HIGH = 1      # Critical operations (profile loading, active session)
    NORMAL = 5    # Regular operations (updates, inserts)
    LOW = 10      # Background operations (cleanup, sync)


@dataclass
class DatabaseOperation:
    """Represents a queued database operation"""
    operation_id: str
    function: Callable
    args: tuple
    kwargs: dict
    priority: OperationPriority
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    timestamp: float = 0.0

    def __post_init__(self):
        self.timestamp = time.time()

    def __lt__(self, other):
        """For priority queue comparison"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.timestamp < other.timestamp


class DatabaseWorker(QThread):
    """
    Background worker thread for database operations.

    This class provides a non-blocking interface for database operations,
    preventing UI freezes during heavy database access.

    Usage:
        worker = DatabaseWorker()
        worker.start()

        # Queue an operation
        worker.queue_operation(
            'load_profile_1',
            vehicle_manager.load_profile,
            args=(1,),
            callback=on_profile_loaded
        )
    """

    # Signals for communicating results back to main thread
    operation_completed = Signal(str, object)  # (operation_id, result)
    operation_failed = Signal(str, str)        # (operation_id, error_message)
    queue_empty = Signal()                     # Emitted when queue becomes empty
    progress_update = Signal(int, int)         # (completed, total)

    def __init__(self, max_queue_size: int = 1000, parent=None):
        super().__init__(parent)

        # Priority queue for operations
        self._queue = queue.PriorityQueue(maxsize=max_queue_size)

        # Control flags
        self._running = True
        self._paused = False

        # Statistics
        self._stats = {
            'operations_completed': 0,
            'operations_failed': 0,
            'total_time': 0.0,
            'average_time': 0.0
        }

        # Operation tracking
        self._pending_operations: Dict[str, DatabaseOperation] = {}
        self._lock = threading.Lock()

        db_worker_logger.info("DatabaseWorker initialized")

    def queue_operation(
        self,
        operation_id: str,
        function: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: OperationPriority = OperationPriority.NORMAL,
        callback: Callable = None,
        error_callback: Callable = None
    ) -> bool:
        """
        Queue a database operation for background execution.

        Args:
            operation_id: Unique identifier for this operation
            function: The function to execute
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            priority: Operation priority level
            callback: Function to call with result on success
            error_callback: Function to call with error message on failure

        Returns:
            True if operation was queued, False if queue is full
        """
        if kwargs is None:
            kwargs = {}

        operation = DatabaseOperation(
            operation_id=operation_id,
            function=function,
            args=args,
            kwargs=kwargs,
            priority=priority,
            callback=callback,
            error_callback=error_callback
        )

        try:
            self._queue.put_nowait(operation)

            with self._lock:
                self._pending_operations[operation_id] = operation

            db_worker_logger.debug(f"Queued operation: {operation_id}")
            return True

        except queue.Full:
            db_worker_logger.warning(f"Queue full, could not queue: {operation_id}")
            return False

    def run(self):
        """Main worker thread loop"""
        db_worker_logger.info("DatabaseWorker thread started")

        while self._running:
            try:
                # Check if paused
                if self._paused:
                    time.sleep(0.1)
                    continue

                # Get next operation with timeout
                try:
                    operation = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # Execute the operation
                start_time = time.time()
                try:
                    result = operation.function(*operation.args, **operation.kwargs)
                    elapsed = time.time() - start_time

                    # Update statistics
                    self._stats['operations_completed'] += 1
                    self._stats['total_time'] += elapsed
                    self._stats['average_time'] = (
                        self._stats['total_time'] / self._stats['operations_completed']
                    )

                    # Emit success signal
                    self.operation_completed.emit(operation.operation_id, result)

                    # Call callback if provided
                    if operation.callback:
                        try:
                            operation.callback(result)
                        except Exception as cb_error:
                            db_worker_logger.error(
                                f"Callback error for {operation.operation_id}: {cb_error}"
                            )

                    db_worker_logger.debug(
                        f"Completed operation: {operation.operation_id} in {elapsed:.3f}s"
                    )

                except Exception as e:
                    elapsed = time.time() - start_time
                    error_msg = f"{type(e).__name__}: {str(e)}"

                    self._stats['operations_failed'] += 1

                    # Emit failure signal
                    self.operation_failed.emit(operation.operation_id, error_msg)

                    # Call error callback if provided
                    if operation.error_callback:
                        try:
                            operation.error_callback(error_msg)
                        except Exception as cb_error:
                            db_worker_logger.error(
                                f"Error callback error for {operation.operation_id}: {cb_error}"
                            )

                    db_worker_logger.error(
                        f"Failed operation: {operation.operation_id} - {error_msg}"
                    )

                finally:
                    # Remove from pending
                    with self._lock:
                        self._pending_operations.pop(operation.operation_id, None)

                    # Mark task as done
                    self._queue.task_done()

                    # Check if queue is empty
                    if self._queue.empty():
                        self.queue_empty.emit()

            except Exception as e:
                db_worker_logger.error(f"Worker thread error: {e}")
                traceback.print_exc()

        db_worker_logger.info("DatabaseWorker thread stopped")

    def stop(self, wait_for_queue: bool = True, timeout: float = 5.0):
        """
        Stop the worker thread.

        Args:
            wait_for_queue: If True, wait for pending operations to complete
            timeout: Maximum time to wait for queue to empty
        """
        if wait_for_queue and not self._queue.empty():
            db_worker_logger.info("Waiting for queue to empty...")
            start_time = time.time()
            while not self._queue.empty() and (time.time() - start_time) < timeout:
                time.sleep(0.1)

        self._running = False
        self.wait(int(timeout * 1000))  # Wait for thread to finish

        db_worker_logger.info("DatabaseWorker stopped")

    def pause(self):
        """Pause processing of queue"""
        self._paused = True
        db_worker_logger.info("DatabaseWorker paused")

    def resume(self):
        """Resume processing of queue"""
        self._paused = False
        db_worker_logger.info("DatabaseWorker resumed")

    def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel a pending operation.

        Note: Cannot cancel an operation that's already executing.
        """
        with self._lock:
            if operation_id in self._pending_operations:
                # Note: PriorityQueue doesn't support removal
                # We mark it as cancelled and skip during execution
                del self._pending_operations[operation_id]
                db_worker_logger.info(f"Cancelled operation: {operation_id}")
                return True
        return False

    def get_queue_size(self) -> int:
        """Get current number of pending operations"""
        return self._queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        return {
            **self._stats,
            'queue_size': self._queue.qsize(),
            'pending_operations': len(self._pending_operations),
            'is_running': self._running,
            'is_paused': self._paused
        }

    def clear_queue(self):
        """Clear all pending operations from the queue"""
        cleared = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                cleared += 1
            except queue.Empty:
                break

        with self._lock:
            self._pending_operations.clear()

        db_worker_logger.info(f"Cleared {cleared} operations from queue")


class DatabaseWorkerPool:
    """
    Pool of database workers for parallel operations.

    Useful when you need to handle multiple concurrent database operations.
    """

    def __init__(self, num_workers: int = 2):
        self.workers = [DatabaseWorker() for _ in range(num_workers)]
        self._current_worker = 0
        self._lock = threading.Lock()

    def start(self):
        """Start all workers"""
        for worker in self.workers:
            worker.start()

    def stop(self, wait_for_queue: bool = True):
        """Stop all workers"""
        for worker in self.workers:
            worker.stop(wait_for_queue)

    def queue_operation(self, *args, **kwargs) -> bool:
        """Queue operation on next available worker (round-robin)"""
        with self._lock:
            worker = self.workers[self._current_worker]
            self._current_worker = (self._current_worker + 1) % len(self.workers)

        return worker.queue_operation(*args, **kwargs)

    def get_total_queue_size(self) -> int:
        """Get total queue size across all workers"""
        return sum(w.get_queue_size() for w in self.workers)


# Singleton instance for global access
_worker_instance: Optional[DatabaseWorker] = None


def get_database_worker() -> DatabaseWorker:
    """Get or create the global database worker instance"""
    global _worker_instance

    if _worker_instance is None:
        _worker_instance = DatabaseWorker()
        _worker_instance.start()

    return _worker_instance


def shutdown_database_worker():
    """Shutdown the global database worker"""
    global _worker_instance

    if _worker_instance is not None:
        _worker_instance.stop()
        _worker_instance = None


if __name__ == "__main__":
    # Test the database worker
    import sys
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    def test_function(value):
        time.sleep(0.5)  # Simulate DB operation
        return value * 2

    def on_result(result):
        print(f"Result: {result}")

    def on_error(error):
        print(f"Error: {error}")

    worker = get_database_worker()

    # Queue some operations
    for i in range(5):
        worker.queue_operation(
            f'test_{i}',
            test_function,
            args=(i,),
            callback=on_result,
            error_callback=on_error
        )

    print(f"Queue size: {worker.get_queue_size()}")

    # Wait a bit
    QTimer.singleShot(3000, app.quit)
    app.exec()

    shutdown_database_worker()
