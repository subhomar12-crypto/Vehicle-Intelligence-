"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Database Utilities - Shared Database Management

db_utils.py — Shared Database Utilities for Predict OBD
Provides retry logic and connection management for SQLite
"""

import sqlite3
import time
import functools
import logging
from typing import Callable, TypeVar, Optional
from contextlib import contextmanager

# Configure logging
logger = logging.getLogger(__name__)

# SQLite retry configuration
SQLITE_MAX_RETRIES = 5
SQLITE_RETRY_DELAY_BASE = 0.1  # Base delay in seconds
SQLITE_LOCK_TIMEOUT = 30  # Connection timeout in seconds

# Type variable for generic return types
T = TypeVar('T')


def with_db_retry(max_retries: int = SQLITE_MAX_RETRIES,
                  base_delay: float = SQLITE_RETRY_DELAY_BASE) -> Callable:
    """
    Decorator that retries a function on SQLite database lock errors.
    Uses exponential backoff with jitter for retry delays.

    Usage:
        @with_db_retry()
        def save_record(data):
            conn = sqlite3.connect(db_path)
            # ... database operations ...

    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Base delay between retries in seconds (default: 0.1)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    if "locked" in error_msg or "busy" in error_msg:
                        last_error = e
                        # Exponential backoff with jitter
                        delay = base_delay * (2 ** attempt) + (time.time() % 0.1)
                        logger.warning(
                            f"SQLite lock detected in {func.__name__}, "
                            f"retry {attempt + 1}/{max_retries} after {delay:.2f}s"
                        )
                        time.sleep(delay)
                    else:
                        # Non-lock related error, re-raise immediately
                        raise
            # All retries exhausted
            logger.error(f"SQLite lock persisted after {max_retries} retries in {func.__name__}")
            raise last_error
        return wrapper
    return decorator


@contextmanager
def get_db_connection(db_path: str, timeout: float = SQLITE_LOCK_TIMEOUT):
    """
    Context manager for database connections with retry-safe behavior.
    Automatically handles connection cleanup and lock timeouts.
    Enables WAL mode for better concurrent access.

    Usage:
        with get_db_connection('path/to/db.sqlite') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM table")
            results = cursor.fetchall()
            conn.commit()

    Args:
        db_path: Path to the SQLite database file
        timeout: Connection timeout in seconds (default: 30)

    Yields:
        sqlite3.Connection object with row_factory set to sqlite3.Row
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
        except sqlite3.OperationalError:
            pass  # WAL might already be set or not supported
        yield conn
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")


def create_connection(db_path: str, timeout: float = SQLITE_LOCK_TIMEOUT) -> sqlite3.Connection:
    """
    Create a database connection with proper configuration.
    Caller is responsible for closing the connection.

    Args:
        db_path: Path to the SQLite database file
        timeout: Connection timeout in seconds (default: 30)

    Returns:
        Configured sqlite3.Connection object
    """
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent access
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    except sqlite3.OperationalError:
        pass  # WAL might already be set or not supported
    return conn


def execute_with_retry(db_path: str,
                       query: str,
                       params: tuple = (),
                       fetch: str = 'none',
                       max_retries: int = SQLITE_MAX_RETRIES) -> Optional[list]:
    """
    Execute a query with automatic retry on database locks.

    Args:
        db_path: Path to the SQLite database file
        query: SQL query to execute
        params: Query parameters (default: empty tuple)
        fetch: 'none', 'one', 'all' - what to return (default: 'none')
        max_retries: Maximum number of retry attempts

    Returns:
        Query results based on fetch parameter, or None for 'none'
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            with get_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)

                if fetch == 'one':
                    result = cursor.fetchone()
                    return dict(result) if result else None
                elif fetch == 'all':
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                else:
                    conn.commit()
                    return None

        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if "locked" in error_msg or "busy" in error_msg:
                last_error = e
                delay = SQLITE_RETRY_DELAY_BASE * (2 ** attempt) + (time.time() % 0.1)
                logger.warning(f"SQLite lock detected, retry {attempt + 1}/{max_retries}")
                time.sleep(delay)
            else:
                raise

    if last_error:
        raise last_error
    return None


class DatabaseConnectionPool:
    """
    Simple connection pool for SQLite databases.
    Provides connection reuse and automatic retry logic.
    """

    def __init__(self, db_path: str, max_connections: int = 5, timeout: float = SQLITE_LOCK_TIMEOUT):
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self._pool: list = []
        self._lock = __import__('threading').Lock()

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool or create a new one."""
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
                # Test if connection is still valid
                try:
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    pass  # Connection is stale, create new one

            return create_connection(self.db_path, self.timeout)

    def return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        with self._lock:
            if len(self._pool) < self.max_connections:
                self._pool.append(conn)
            else:
                try:
                    conn.close()
                except Exception:
                    pass

    @contextmanager
    def connection(self):
        """Context manager for pooled connections."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)

    def close_all(self):
        """Close all connections in the pool."""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()


# Export commonly used items
__all__ = [
    'with_db_retry',
    'get_db_connection',
    'create_connection',
    'execute_with_retry',
    'DatabaseConnectionPool',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY_BASE',
    'SQLITE_LOCK_TIMEOUT'
]
