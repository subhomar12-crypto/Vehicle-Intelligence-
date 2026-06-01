"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Device Heartbeat

Device Heartbeat System
Real-time online/offline detection for connected vehicles and mobile devices.
"""

import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class DeviceStatus(Enum):
    """Device connection status"""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"  # Intermittent connection
    UNKNOWN = "unknown"


@dataclass
class HeartbeatInfo:
    """Information about a device's heartbeat"""
    device_id: str
    profile_id: int
    last_seen: datetime
    status: DeviceStatus
    consecutive_misses: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None


class DeviceHeartbeatManager:
    """
    Manages heartbeat tracking for all connected devices.

    Features:
    - Real-time online/offline status (<=10s detection)
    - Connection history logging
    - Device health telemetry
    - Callback notifications for status changes
    """

    # Heartbeat configuration
    HEARTBEAT_INTERVAL = 10  # Expected heartbeat every 10 seconds
    OFFLINE_THRESHOLD = 30  # Mark offline after 30 seconds without heartbeat
    DEGRADED_THRESHOLD = 20  # Mark degraded after 20 seconds
    CLEANUP_INTERVAL = 300  # Clean old records every 5 minutes

    def __init__(self):
        self.db_path = CONFIG.DATA_DIR / "device_heartbeats.db"
        self._devices: Dict[str, HeartbeatInfo] = {}
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[str, DeviceStatus, DeviceStatus], None]] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

        self._init_database()
        logger.info("DeviceHeartbeatManager initialized")

    def _init_database(self):
        """Initialize heartbeat tracking database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        # Current device status table
        c.execute('''
            CREATE TABLE IF NOT EXISTS device_status (
                device_id TEXT PRIMARY KEY,
                profile_id INTEGER,
                status TEXT,
                last_heartbeat TEXT,
                consecutive_misses INTEGER DEFAULT 0,
                ip_address TEXT,
                user_agent TEXT,
                battery_level INTEGER,
                signal_strength INTEGER,
                updated_at TEXT
            )
        ''')

        # Heartbeat history table (for connection logging)
        c.execute('''
            CREATE TABLE IF NOT EXISTS heartbeat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                profile_id INTEGER,
                event_type TEXT,
                timestamp TEXT,
                ip_address TEXT,
                details TEXT
            )
        ''')

        # Create indexes
        c.execute('CREATE INDEX IF NOT EXISTS idx_heartbeat_device ON heartbeat_history(device_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_heartbeat_time ON heartbeat_history(timestamp)')

        conn.commit()
        conn.close()

    def start_monitoring(self):
        """Start the background monitoring thread"""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Heartbeat monitoring started")

    def stop_monitoring(self):
        """Stop the background monitoring thread"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Heartbeat monitoring stopped")

    def register_callback(self, callback: Callable[[str, DeviceStatus, DeviceStatus], None]):
        """
        Register a callback for device status changes.

        Args:
            callback: Function called with (device_id, old_status, new_status)
        """
        with self._lock:
            self._callbacks.append(callback)

    def record_heartbeat(self, device_id: str, profile_id: int,
                         ip_address: str = None, user_agent: str = None,
                         battery_level: int = None, signal_strength: int = None) -> DeviceStatus:
        """
        Record a heartbeat from a device.

        Args:
            device_id: Unique device identifier
            profile_id: Associated vehicle profile ID
            ip_address: Device IP address
            user_agent: Client user agent string
            battery_level: Device battery percentage (0-100)
            signal_strength: Network signal strength (0-100)

        Returns:
            Current device status
        """
        now = datetime.now()

        with self._lock:
            old_info = self._devices.get(device_id)
            old_status = old_info.status if old_info else DeviceStatus.UNKNOWN

            # Create/update device info
            new_info = HeartbeatInfo(
                device_id=device_id,
                profile_id=profile_id,
                last_seen=now,
                status=DeviceStatus.ONLINE,
                consecutive_misses=0,
                ip_address=ip_address,
                user_agent=user_agent,
                battery_level=battery_level,
                signal_strength=signal_strength
            )
            self._devices[device_id] = new_info

            # Log status change
            if old_status != DeviceStatus.ONLINE:
                self._log_event(device_id, profile_id, "connected", ip_address)
                self._notify_callbacks(device_id, old_status, DeviceStatus.ONLINE)

            # Persist to database
            self._update_device_db(new_info)

        return DeviceStatus.ONLINE

    def get_device_status(self, device_id: str) -> Optional[HeartbeatInfo]:
        """Get current status for a device"""
        with self._lock:
            return self._devices.get(device_id)

    def get_all_devices(self) -> List[HeartbeatInfo]:
        """Get status of all tracked devices"""
        with self._lock:
            return list(self._devices.values())

    def get_online_devices(self) -> List[HeartbeatInfo]:
        """Get list of currently online devices"""
        with self._lock:
            return [d for d in self._devices.values() if d.status == DeviceStatus.ONLINE]

    def get_offline_devices(self) -> List[HeartbeatInfo]:
        """Get list of currently offline devices"""
        with self._lock:
            return [d for d in self._devices.values() if d.status == DeviceStatus.OFFLINE]

    def get_connection_history(self, device_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get connection history for a device"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).isoformat()

            c.execute('''
                SELECT device_id, profile_id, event_type, timestamp, ip_address, details
                FROM heartbeat_history
                WHERE device_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1000
            ''', (device_id, start_date))

            rows = c.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting connection history: {e}")
            return []

    def get_device_uptime(self, device_id: str, days: int = 30) -> Dict[str, Any]:
        """Calculate device uptime statistics"""
        history = self.get_connection_history(device_id, days)

        if not history:
            return {
                'uptime_percentage': 0,
                'total_connects': 0,
                'total_disconnects': 0,
                'average_session_minutes': 0
            }

        connects = [h for h in history if h['event_type'] == 'connected']
        disconnects = [h for h in history if h['event_type'] == 'disconnected']

        # Calculate average session duration
        sessions = []
        for i, connect in enumerate(connects):
            connect_time = datetime.fromisoformat(connect['timestamp'])
            # Find next disconnect
            for disconnect in disconnects:
                disconnect_time = datetime.fromisoformat(disconnect['timestamp'])
                if disconnect_time > connect_time:
                    session_duration = (disconnect_time - connect_time).total_seconds() / 60
                    sessions.append(session_duration)
                    break

        avg_session = sum(sessions) / len(sessions) if sessions else 0

        return {
            'uptime_percentage': (len(connects) / max(len(history), 1)) * 100,
            'total_connects': len(connects),
            'total_disconnects': len(disconnects),
            'average_session_minutes': round(avg_session, 2)
        }

    def _monitor_loop(self):
        """Background monitoring loop"""
        last_cleanup = time.time()

        while self._running:
            try:
                now = datetime.now()

                with self._lock:
                    for device_id, info in list(self._devices.items()):
                        elapsed = (now - info.last_seen).total_seconds()

                        # Determine new status based on elapsed time
                        if elapsed > self.OFFLINE_THRESHOLD:
                            new_status = DeviceStatus.OFFLINE
                        elif elapsed > self.DEGRADED_THRESHOLD:
                            new_status = DeviceStatus.DEGRADED
                        else:
                            new_status = DeviceStatus.ONLINE

                        # Update if status changed
                        if info.status != new_status:
                            old_status = info.status
                            info.status = new_status

                            if new_status == DeviceStatus.OFFLINE:
                                info.consecutive_misses += 1
                                self._log_event(device_id, info.profile_id, "disconnected")

                            self._notify_callbacks(device_id, old_status, new_status)
                            self._update_device_db(info)

                # Periodic cleanup
                if time.time() - last_cleanup > self.CLEANUP_INTERVAL:
                    self._cleanup_old_records()
                    last_cleanup = time.time()

            except Exception as e:
                logger.error(f"Error in heartbeat monitor loop: {e}")

            time.sleep(1)  # Check every second for fast detection

    def _log_event(self, device_id: str, profile_id: int, event_type: str,
                   ip_address: str = None, details: str = None):
        """Log a connection event to history"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT INTO heartbeat_history (device_id, profile_id, event_type, timestamp, ip_address, details)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (device_id, profile_id, event_type, datetime.now().isoformat(), ip_address, details))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error logging heartbeat event: {e}")

    def _update_device_db(self, info: HeartbeatInfo):
        """Update device status in database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            c.execute('''
                INSERT OR REPLACE INTO device_status
                (device_id, profile_id, status, last_heartbeat, consecutive_misses,
                 ip_address, user_agent, battery_level, signal_strength, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                info.device_id,
                info.profile_id,
                info.status.value,
                info.last_seen.isoformat(),
                info.consecutive_misses,
                info.ip_address,
                info.user_agent,
                info.battery_level,
                info.signal_strength,
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error updating device status: {e}")

    def _notify_callbacks(self, device_id: str, old_status: DeviceStatus, new_status: DeviceStatus):
        """Notify all registered callbacks of status change"""
        for callback in self._callbacks:
            try:
                callback(device_id, old_status, new_status)
            except Exception as e:
                logger.error(f"Error in heartbeat callback: {e}")

    def _cleanup_old_records(self):
        """Clean up old heartbeat history records"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()

            # Keep last 90 days of history
            cutoff = (datetime.now() - timedelta(days=90)).isoformat()
            c.execute('DELETE FROM heartbeat_history WHERE timestamp < ?', (cutoff,))

            deleted = c.rowcount
            conn.commit()
            conn.close()

            if deleted > 0:
                logger.debug(f"Cleaned up {deleted} old heartbeat records")

        except Exception as e:
            logger.error(f"Error cleaning up heartbeat records: {e}")

    def load_from_database(self):
        """Load device states from database on startup"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('SELECT * FROM device_status')
            rows = c.fetchall()
            conn.close()

            with self._lock:
                for row in rows:
                    try:
                        info = HeartbeatInfo(
                            device_id=row['device_id'],
                            profile_id=row['profile_id'],
                            last_seen=datetime.fromisoformat(row['last_heartbeat']),
                            status=DeviceStatus(row['status']),
                            consecutive_misses=row['consecutive_misses'],
                            ip_address=row['ip_address'],
                            user_agent=row['user_agent'],
                            battery_level=row['battery_level'],
                            signal_strength=row['signal_strength']
                        )
                        self._devices[row['device_id']] = info
                    except Exception as e:
                        logger.warning(f"Error loading device {row['device_id']}: {e}")

            logger.info(f"Loaded {len(self._devices)} devices from database")

        except Exception as e:
            logger.error(f"Error loading devices from database: {e}")


# Singleton instance
_heartbeat_manager: Optional[DeviceHeartbeatManager] = None
_manager_lock = threading.Lock()


def get_heartbeat_manager() -> DeviceHeartbeatManager:
    """Get the singleton DeviceHeartbeatManager instance."""
    global _heartbeat_manager

    with _manager_lock:
        if _heartbeat_manager is None:
            _heartbeat_manager = DeviceHeartbeatManager()
            _heartbeat_manager.load_from_database()
            _heartbeat_manager.start_monitoring()

        return _heartbeat_manager
