"""
PREDICT - Vehicle Intelligence Platform
Real-Time Data Sync Service

This module provides real-time synchronization between:
- Mobile apps (Predict OBD, Predict Guardian)
- OBD Server
- Desktop PREDICT application

Features:
- WebSocket connection to server for live updates
- Database change detection
- Push notifications to UI
- Automatic reconnection
- Offline queue for when server is unavailable
"""

import asyncio
import json
import logging
import threading
import time
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from queue import Queue
from enum import Enum

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from config import get_config

logger = logging.getLogger(__name__)
CONFIG = get_config()


class SyncEventType(Enum):
    """Types of sync events"""
    NEW_OBD_DATA = "new_obd_data"
    NEW_DTC = "new_dtc"
    VEHICLE_UPDATE = "vehicle_update"
    PREDICTION_READY = "prediction_ready"
    DRIVER_LOCATION = "driver_location"
    ALERT = "alert"
    CONNECTION_STATUS = "connection_status"
    NEW_OWNER_REGISTERED = "new_owner_registered"
    NEW_DRIVER_REGISTERED = "new_driver_registered"
    VEHICLE_RESEARCH_UPDATE = "vehicle_research_update"


@dataclass
class SyncEvent:
    """A synchronization event"""
    event_type: SyncEventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    profile_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "profile_id": self.profile_id
        }


class DatabaseWatcher:
    """
    Watches the SQLite database for changes.
    Uses polling since SQLite doesn't have built-in change notifications.
    """

    def __init__(self, db_path: Path, poll_interval: float = 2.0):
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.running = False
        self._last_check = {}
        self._callbacks: List[Callable[[SyncEvent], None]] = []
        self._thread: Optional[threading.Thread] = None

    def add_callback(self, callback: Callable[[SyncEvent], None]):
        """Add a callback for database changes"""
        self._callbacks.append(callback)

    def _notify(self, event: SyncEvent):
        """Notify all callbacks of an event"""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def _get_table_hash(self, conn: sqlite3.Connection, table: str) -> str:
        """Get a hash of table contents for change detection"""
        try:
            cursor = conn.execute(f"SELECT COUNT(*), MAX(rowid) FROM {table}")
            row = cursor.fetchone()
            return f"{row[0]}:{row[1]}"
        except Exception:
            return ""

    def _check_for_changes(self):
        """Check database for changes"""
        if not self.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row

            # Tables to watch
            tables_to_watch = [
                ("vehicle_profiles", SyncEventType.VEHICLE_UPDATE),
                ("obd_snapshots", SyncEventType.NEW_OBD_DATA),
                ("dtc_history", SyncEventType.NEW_DTC),
                ("predictions", SyncEventType.PREDICTION_READY),
            ]

            for table, event_type in tables_to_watch:
                try:
                    current_hash = self._get_table_hash(conn, table)
                    last_hash = self._last_check.get(table, "")

                    if current_hash != last_hash and last_hash != "":
                        # Table changed - get recent records
                        cursor = conn.execute(
                            f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 5"
                        )
                        rows = cursor.fetchall()

                        if rows:
                            self._notify(SyncEvent(
                                event_type=event_type,
                                data={
                                    "table": table,
                                    "records": [dict(row) for row in rows]
                                }
                            ))

                    self._last_check[table] = current_hash
                except sqlite3.OperationalError:
                    # Table doesn't exist yet
                    pass

            conn.close()

        except Exception as e:
            logger.error(f"Database watch error: {e}")

    def _watch_loop(self):
        """Main watch loop"""
        logger.info(f"Database watcher started for {self.db_path}")

        while self.running:
            self._check_for_changes()
            time.sleep(self.poll_interval)

        logger.info("Database watcher stopped")

    def start(self):
        """Start watching the database"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop watching"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)


class ServerSyncClient:
    """
    WebSocket client for real-time sync with the OBD server.
    """

    def __init__(
        self,
        server_url: str = "ws://localhost:8000/ws",
        reconnect_interval: float = 5.0
    ):
        self.server_url = server_url
        self.reconnect_interval = reconnect_interval
        self.connected = False
        self.running = False
        self._websocket = None
        self._callbacks: List[Callable[[SyncEvent], None]] = []
        self._send_queue: Queue = Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def add_callback(self, callback: Callable[[SyncEvent], None]):
        """Add a callback for server events"""
        self._callbacks.append(callback)

    def _notify(self, event: SyncEvent):
        """Notify all callbacks"""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def _connect(self):
        """Connect to the WebSocket server"""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("websockets library not available")
            return

        while self.running:
            try:
                logger.info(f"Connecting to server: {self.server_url}")

                async with websockets.connect(self.server_url) as websocket:
                    self._websocket = websocket
                    self.connected = True

                    self._notify(SyncEvent(
                        event_type=SyncEventType.CONNECTION_STATUS,
                        data={"connected": True, "url": self.server_url}
                    ))

                    logger.info("Connected to server")

                    # Handle messages
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            event_type = SyncEventType(data.get("type", "alert"))
                            self._notify(SyncEvent(
                                event_type=event_type,
                                data=data.get("data", {}),
                                profile_id=data.get("profile_id")
                            ))
                        except Exception as e:
                            logger.warning(f"Failed to process message: {e}")

            except Exception as e:
                logger.warning(f"WebSocket connection error: {e}")
                self.connected = False

                self._notify(SyncEvent(
                    event_type=SyncEventType.CONNECTION_STATUS,
                    data={"connected": False, "error": str(e)}
                ))

            if self.running:
                logger.info(f"Reconnecting in {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)

    def _run_async_loop(self):
        """Run the async event loop in a thread"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect())

    def start(self):
        """Start the sync client"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the sync client"""
        self.running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def send(self, event: SyncEvent):
        """Send an event to the server"""
        if self._websocket and self.connected:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._websocket.send(json.dumps(event.to_dict())),
                    self._loop
                )
            except Exception as e:
                logger.error(f"Failed to send event: {e}")


class RealtimeSyncService:
    """
    Main service that coordinates real-time synchronization.

    Usage:
        sync = RealtimeSyncService()
        sync.add_listener(my_callback)  # Called when data changes
        sync.start()
    """

    def __init__(self):
        self.config = get_config()

        # Database watcher for local changes
        self.db_watcher = DatabaseWatcher(
            db_path=self.config.PROFILES_DB_PATH,
            poll_interval=2.0
        )

        # Server sync client for remote changes
        self.server_client = ServerSyncClient(
            server_url="ws://localhost:8000/ws"
        )

        # Event listeners
        self._listeners: List[Callable[[SyncEvent], None]] = []

        # Stats
        self.stats = {
            "events_received": 0,
            "last_event_time": None,
            "connection_status": "disconnected"
        }

        # Wire up internal callbacks
        self.db_watcher.add_callback(self._on_db_change)
        self.server_client.add_callback(self._on_server_event)

    def add_listener(self, listener: Callable[[SyncEvent], None]):
        """Add a listener for sync events"""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[SyncEvent], None]):
        """Remove a listener"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, event: SyncEvent):
        """Notify all listeners of an event"""
        self.stats["events_received"] += 1
        self.stats["last_event_time"] = time.time()

        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def _on_db_change(self, event: SyncEvent):
        """Handle database change events"""
        logger.debug(f"Database change: {event.event_type.value}")
        self._notify_listeners(event)

    def _on_server_event(self, event: SyncEvent):
        """Handle server events"""
        if event.event_type == SyncEventType.CONNECTION_STATUS:
            self.stats["connection_status"] = (
                "connected" if event.data.get("connected") else "disconnected"
            )

        logger.debug(f"Server event: {event.event_type.value}")
        self._notify_listeners(event)

    def start(self):
        """Start the sync service"""
        logger.info("Starting Real-Time Sync Service")
        self.db_watcher.start()
        self.server_client.start()

    def stop(self):
        """Stop the sync service"""
        logger.info("Stopping Real-Time Sync Service")
        self.db_watcher.stop()
        self.server_client.stop()

    def get_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            "db_watcher_running": self.db_watcher.running,
            "server_connected": self.server_client.connected,
            "stats": self.stats
        }


# Global instance
_sync_service: Optional[RealtimeSyncService] = None


def get_sync_service() -> RealtimeSyncService:
    """Get or create the global sync service"""
    global _sync_service
    if _sync_service is None:
        _sync_service = RealtimeSyncService()
    return _sync_service


def start_realtime_sync():
    """Start the global sync service"""
    service = get_sync_service()
    service.start()
    return service


def stop_realtime_sync():
    """Stop the global sync service"""
    global _sync_service
    if _sync_service:
        _sync_service.stop()


# Example callback for UI updates
def example_ui_callback(event: SyncEvent):
    """Example callback that could update a PySide6 UI"""
    print(f"[SYNC] {event.event_type.value}: {event.data}")

    # In a real UI, you would emit a Qt signal here:
    # self.data_updated.emit(event.to_dict())


if __name__ == "__main__":
    # Test the sync service
    logging.basicConfig(level=logging.DEBUG)

    service = start_realtime_sync()
    service.add_listener(example_ui_callback)

    print("Sync service running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_realtime_sync()
        print("Stopped.")
