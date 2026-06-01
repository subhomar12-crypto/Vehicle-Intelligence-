"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Connection Monitor
Purpose: Monitor server connection health and trigger sync on reconnection
"""

import time
import logging
import threading
from typing import Optional, Callable, Dict, Any
from datetime import datetime

import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

from PySide6.QtCore import QObject, Signal, QTimer

# Configure logging
monitor_logger = logging.getLogger(__name__)


class ConnectionState:
    """Connection state constants"""
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"


class ConnectionMonitor(QObject):
    """
    Monitor server connection health and emit signals on state changes.

    Features:
    - Periodic health checks
    - Connection state tracking
    - Auto-reconnection detection
    - Offline queue sync trigger
    - Statistics and uptime tracking
    """

    # Signals
    connection_established = Signal()          # First connection or reconnection
    connection_lost = Signal()                 # Connection lost
    connection_state_changed = Signal(str)     # State name
    health_check_completed = Signal(bool, int) # (success, latency_ms)

    # Configuration
    DEFAULT_CHECK_INTERVAL = 30  # seconds
    HEALTH_TIMEOUT = 10          # seconds
    RECONNECT_THRESHOLD = 3      # consecutive failures before marking disconnected

    def __init__(
        self,
        server_url: str = None,
        api_key: str = None,
        check_interval: int = None,
        parent=None
    ):
        super().__init__(parent)

        self.server_url = server_url or "http://localhost:8000"
        self.api_key = api_key or ""
        self.check_interval = check_interval or self.DEFAULT_CHECK_INTERVAL

        # State tracking
        self._state = ConnectionState.UNKNOWN
        self._previous_state = ConnectionState.UNKNOWN
        self._consecutive_failures = 0
        self._last_successful_check = None
        self._last_check_time = None
        self._is_monitoring = False

        # Statistics
        self._stats = {
            'total_checks': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'total_downtime_seconds': 0,
            'downtime_start': None,
            'average_latency_ms': 0,
            'uptime_percentage': 100.0
        }

        # Timer for periodic checks
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._perform_health_check)

        # Callbacks for sync trigger
        self._on_reconnect_callbacks = []

        monitor_logger.info(f"ConnectionMonitor initialized for {self.server_url}")

    def set_server_config(self, server_url: str, api_key: str = None):
        """Update server configuration"""
        self.server_url = server_url.rstrip('/')
        if api_key is not None:
            self.api_key = api_key
        monitor_logger.info(f"Server config updated: {self.server_url}")

    def start_monitoring(self, interval: int = None):
        """Start periodic health monitoring"""
        if interval:
            self.check_interval = interval

        if self._is_monitoring:
            monitor_logger.warning("Already monitoring")
            return

        self._is_monitoring = True
        self._timer.start(self.check_interval * 1000)

        # Perform initial check
        self._perform_health_check()

        monitor_logger.info(
            f"Started monitoring with {self.check_interval}s interval"
        )

    def stop_monitoring(self):
        """Stop periodic health monitoring"""
        self._is_monitoring = False
        self._timer.stop()
        monitor_logger.info("Stopped monitoring")

    def check_now(self) -> bool:
        """Perform immediate health check"""
        return self._perform_health_check()

    def _perform_health_check(self) -> bool:
        """Execute health check against server"""
        self._stats['total_checks'] += 1
        self._last_check_time = time.time()

        try:
            start_time = time.time()

            # Build request
            headers = {'Accept': 'application/json'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            # Make health check request
            response = requests.get(
                f"{self.server_url}/api/health",
                headers=headers,
                timeout=self.HEALTH_TIMEOUT
            )

            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code in (200, 204):
                self._on_check_success(latency_ms)
                return True
            else:
                self._on_check_failure(f"Status code: {response.status_code}")
                return False

        except ConnectionError:
            self._on_check_failure("Connection refused")
            return False
        except Timeout:
            self._on_check_failure("Request timeout")
            return False
        except RequestException as e:
            self._on_check_failure(str(e))
            return False
        except Exception as e:
            self._on_check_failure(f"Unexpected error: {e}")
            return False

    def _on_check_success(self, latency_ms: int):
        """Handle successful health check"""
        self._stats['successful_checks'] += 1
        self._consecutive_failures = 0
        self._last_successful_check = time.time()

        # Update average latency
        total = self._stats['successful_checks']
        old_avg = self._stats['average_latency_ms']
        self._stats['average_latency_ms'] = (
            (old_avg * (total - 1) + latency_ms) / total
        )

        # Calculate uptime
        self._stats['uptime_percentage'] = (
            self._stats['successful_checks'] / self._stats['total_checks'] * 100
        )

        # Emit signal
        self.health_check_completed.emit(True, latency_ms)

        # Check for state change
        if self._state != ConnectionState.CONNECTED:
            was_disconnected = self._state == ConnectionState.DISCONNECTED

            # Record downtime
            if self._stats['downtime_start']:
                downtime = time.time() - self._stats['downtime_start']
                self._stats['total_downtime_seconds'] += downtime
                self._stats['downtime_start'] = None

            self._update_state(ConnectionState.CONNECTED)

            if was_disconnected:
                monitor_logger.info("Connection restored!")
                self.connection_established.emit()
                self._trigger_reconnect_callbacks()

    def _on_check_failure(self, error: str):
        """Handle failed health check"""
        self._stats['failed_checks'] += 1
        self._consecutive_failures += 1

        # Emit signal
        self.health_check_completed.emit(False, 0)

        monitor_logger.warning(
            f"Health check failed ({self._consecutive_failures}): {error}"
        )

        # Check threshold for disconnected state
        if self._consecutive_failures >= self.RECONNECT_THRESHOLD:
            if self._state != ConnectionState.DISCONNECTED:
                self._update_state(ConnectionState.DISCONNECTED)
                self._stats['downtime_start'] = time.time()
                self.connection_lost.emit()
                monitor_logger.error("Server connection lost!")

    def _update_state(self, new_state: str):
        """Update connection state and emit signal"""
        self._previous_state = self._state
        self._state = new_state
        self.connection_state_changed.emit(new_state)
        monitor_logger.info(f"Connection state: {new_state}")

    def register_reconnect_callback(self, callback: Callable):
        """Register a callback to be called when connection is restored"""
        if callback not in self._on_reconnect_callbacks:
            self._on_reconnect_callbacks.append(callback)

    def unregister_reconnect_callback(self, callback: Callable):
        """Unregister a reconnect callback"""
        if callback in self._on_reconnect_callbacks:
            self._on_reconnect_callbacks.remove(callback)

    def _trigger_reconnect_callbacks(self):
        """Call all registered reconnect callbacks"""
        for callback in self._on_reconnect_callbacks:
            try:
                callback()
            except Exception as e:
                monitor_logger.error(f"Reconnect callback error: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self._state == ConnectionState.CONNECTED

    @property
    def state(self) -> str:
        """Get current connection state"""
        return self._state

    @property
    def last_successful_check(self) -> Optional[float]:
        """Get timestamp of last successful check"""
        return self._last_successful_check

    def get_statistics(self) -> Dict[str, Any]:
        """Get connection statistics"""
        stats = self._stats.copy()
        stats['current_state'] = self._state
        stats['is_monitoring'] = self._is_monitoring
        stats['check_interval'] = self.check_interval
        stats['consecutive_failures'] = self._consecutive_failures

        if self._last_successful_check:
            stats['seconds_since_last_success'] = (
                time.time() - self._last_successful_check
            )
        else:
            stats['seconds_since_last_success'] = None

        return stats

    def get_status_display(self) -> Dict[str, Any]:
        """Get human-readable status for UI display"""
        if self._state == ConnectionState.CONNECTED:
            icon = "green"
            text = "Connected"
            detail = f"Latency: {self._stats['average_latency_ms']:.0f}ms"
        elif self._state == ConnectionState.DISCONNECTED:
            icon = "red"
            text = "Disconnected"
            if self._stats['downtime_start']:
                downtime = time.time() - self._stats['downtime_start']
                detail = f"Down for {int(downtime)}s"
            else:
                detail = "Connection lost"
        else:
            icon = "gray"
            text = "Unknown"
            detail = "Checking..."

        return {
            'icon': icon,
            'text': text,
            'detail': detail,
            'uptime': f"{self._stats['uptime_percentage']:.1f}%"
        }


class ConnectionMonitorIntegration:
    """
    Helper class to integrate ConnectionMonitor with sync services.

    Usage:
        integration = ConnectionMonitorIntegration(
            connection_monitor,
            driver_sync_service,
            offline_queue
        )
        integration.enable_auto_sync()
    """

    def __init__(
        self,
        monitor: ConnectionMonitor,
        sync_service=None,
        offline_queue=None
    ):
        self.monitor = monitor
        self.sync_service = sync_service
        self.offline_queue = offline_queue
        self._auto_sync_enabled = False

    def enable_auto_sync(self):
        """Enable automatic sync when connection is restored"""
        if not self._auto_sync_enabled:
            self.monitor.register_reconnect_callback(self._on_reconnect)
            self._auto_sync_enabled = True
            monitor_logger.info("Auto-sync on reconnect enabled")

    def disable_auto_sync(self):
        """Disable automatic sync"""
        if self._auto_sync_enabled:
            self.monitor.unregister_reconnect_callback(self._on_reconnect)
            self._auto_sync_enabled = False
            monitor_logger.info("Auto-sync on reconnect disabled")

    def _on_reconnect(self):
        """Handle reconnection - trigger sync"""
        monitor_logger.info("Reconnected - triggering sync")

        # Process offline queue
        if self.offline_queue and self.sync_service:
            try:
                pending = self.offline_queue.get_pending_count()
                if pending > 0:
                    monitor_logger.info(f"Processing {pending} queued operations")
                    success, failed = self.offline_queue.process_queue(
                        self.sync_service
                    )
                    monitor_logger.info(
                        f"Sync complete: {success} succeeded, {failed} failed"
                    )
            except Exception as e:
                monitor_logger.error(f"Auto-sync error: {e}")

        # Trigger driver sync
        if self.sync_service:
            try:
                self.sync_service.batch_sync_drivers()
            except Exception as e:
                monitor_logger.error(f"Driver sync error: {e}")


# Singleton instance
_monitor_instance: Optional[ConnectionMonitor] = None


def get_connection_monitor() -> ConnectionMonitor:
    """Get or create the global connection monitor instance"""
    global _monitor_instance

    if _monitor_instance is None:
        _monitor_instance = ConnectionMonitor()

    return _monitor_instance


def configure_connection_monitor(server_url: str, api_key: str = None):
    """Configure the global connection monitor"""
    monitor = get_connection_monitor()
    monitor.set_server_config(server_url, api_key)
    return monitor


if __name__ == "__main__":
    # Test the connection monitor
    import sys
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    monitor = ConnectionMonitor(
        server_url="http://localhost:8000",
        check_interval=5
    )

    # Connect signals
    monitor.connection_established.connect(
        lambda: print("CONNECTED!")
    )
    monitor.connection_lost.connect(
        lambda: print("DISCONNECTED!")
    )
    monitor.health_check_completed.connect(
        lambda ok, ms: print(f"Check: {'OK' if ok else 'FAIL'} ({ms}ms)")
    )

    # Start monitoring
    monitor.start_monitoring()

    # Run for 30 seconds
    QTimer.singleShot(30000, app.quit)
    app.exec()

    print(f"Stats: {monitor.get_statistics()}")
    monitor.stop_monitoring()
