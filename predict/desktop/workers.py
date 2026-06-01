"""
Background workers for PREDICT Desktop.

Provides QThread-based workers for non-blocking API calls
and WebSocket real-time event listening.
"""

import json
import logging
import time
from typing import Any, Callable, Optional

import requests
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class APIWorker(QThread):
    """One-shot background worker for API calls.

    Prevents premature garbage collection by tracking active workers
    in a class-level set. Workers are cleaned up when new ones start
    (not inside run(), which would race with C++ thread cleanup).
    """

    _active_workers: set = set()

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int)

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def start(self):
        # Clean up workers whose C++ threads have fully finished
        done = {w for w in APIWorker._active_workers if w.isFinished()}
        APIWorker._active_workers -= done

        APIWorker._active_workers.add(self)
        super().start()

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"APIWorker error: {e}")
            self.error.emit(str(e))


class PollingWorker(QThread):
    """Repeating poll worker for periodic API calls."""

    data_received = Signal(object)
    error = Signal(str)

    def __init__(self, func: Callable, interval_ms: int = 5000):
        super().__init__()
        self._func = func
        self._interval_ms = interval_ms
        self._running = True

    def run(self):
        while self._running:
            try:
                result = self._func()
                self.data_received.emit(result)
            except Exception as e:
                self.error.emit(str(e))

            # Interruptible sleep
            for _ in range(self._interval_ms // 100):
                if not self._running:
                    break
                self.msleep(100)

    def stop(self):
        self._running = False


class StatusPoller(QThread):
    """Background thread for polling server status."""

    status_updated = Signal(dict)
    server_ready = Signal()  # emitted once when server first becomes reachable

    def __init__(self, server_url: str, interval_ms: int = 5000):
        super().__init__()
        self.server_url = server_url
        self.interval_ms = interval_ms
        self._running = True
        self._ready_fired = False

    def run(self):
        """Poll server status periodically."""
        while self._running:
            try:
                response = requests.get(
                    f"{self.server_url}/health",
                    timeout=5
                )
                status = {
                    "online": response.status_code == 200,
                    "status_code": response.status_code,
                }
                if response.status_code == 200 and not self._ready_fired:
                    self._ready_fired = True
                    self.server_ready.emit()
            except Exception as e:
                status = {
                    "online": False,
                    "error": str(e),
                }

            self.status_updated.emit(status)

            # Poll faster until server is ready, then slow down
            interval = 1000 if not self._ready_fired else self.interval_ms
            for _ in range(interval // 100):
                if not self._running:
                    break
                self.msleep(100)

    def stop(self):
        """Stop the poller."""
        self._running = False


class WebSocketListener(QThread):
    """Listens to server WebSocket for real-time events."""

    vehicle_update = Signal(dict)
    user_change = Signal(dict)
    alert = Signal(dict)
    connected = Signal()
    disconnected = Signal()

    def __init__(self, ws_url: str):
        super().__init__()
        self._ws_url = ws_url
        self._running = True

    def run(self):
        try:
            import websocket
        except ImportError:
            logger.warning(
                "websocket-client not installed - real-time updates disabled"
            )
            return

        while self._running:
            try:
                ws = websocket.WebSocket()
                ws.settimeout(5)
                ws.connect(self._ws_url)
                self.connected.emit()
                logger.info(f"WebSocket connected to {self._ws_url}")

                while self._running:
                    try:
                        raw = ws.recv()
                        if not raw:
                            continue
                        data = json.loads(raw)
                        msg_type = data.get("type", "")

                        if msg_type == "VEHICLE_UPDATE":
                            self.vehicle_update.emit(data)
                        elif msg_type == "USER_CHANGE":
                            self.user_change.emit(data)
                        elif msg_type == "ALERT":
                            self.alert.emit(data)
                        else:
                            logger.debug(f"Unknown WS message type: {msg_type}")

                    except websocket.WebSocketTimeoutException:
                        continue
                    except websocket.WebSocketConnectionClosedException:
                        logger.info("WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"WebSocket receive error: {e}")
                        break

                ws.close()

            except Exception as e:
                logger.debug(f"WebSocket connect error: {e}")

            self.disconnected.emit()

            # Reconnect delay (interruptible)
            for _ in range(50):  # 5 seconds
                if not self._running:
                    return
                self.msleep(100)

    def stop(self):
        self._running = False
