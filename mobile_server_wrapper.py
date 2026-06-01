"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Mobile Server Wrapper

Mobile Server Wrapper - Simplified integration for Android OBD app
Connects to the Previlium OBD Server running on port 8000
"""

from PySide6.QtCore import QObject, Signal, QTimer, QThread, Slot
import subprocess
import logging
import requests
import os
from pathlib import Path
from typing import Dict, Any, Optional
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import json

# WebSocket client - optional import
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    try:
        import websockets
        WEBSOCKET_AVAILABLE = True
    except ImportError:
        WEBSOCKET_AVAILABLE = False
        websocket = None

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

logger = logging.getLogger(__name__)


class HttpWorker(QThread):
    """Background thread for HTTP requests to avoid blocking UI"""
    finished = Signal(object)  # Emits result

    def __init__(self, session, url, params=None, timeout=0.5):
        super().__init__()
        self.session = session
        self.url = url
        self.params = params
        self.timeout = timeout

    def run(self):
        try:
            response = self.session.get(self.url, params=self.params, timeout=self.timeout)
            if response.status_code == 200:
                self.finished.emit(response.json())
            else:
                self.finished.emit(None)
        except Exception as e:
            logger.debug(f"HTTP request failed: {e}")
            self.finished.emit(None)


class ReportRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for PDF reports"""
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs

        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = parse_qs(parsed_path.query)

        if path == '/report':
            # Extract device_id from query parameters
            device_id = params.get('device_id', [None])[0]
            if not device_id:
                self.send_error(400, "Missing device_id parameter. Use: /report?device_id=YOUR_DEVICE_ID")
                return
            self.server.api_obj.handle_report_request(self, device_id)
        elif path == '/health':
            # Health check endpoint
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "service": "pdf-api", "port": 8001}')
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Silence console logs


class DirectReportServer(QObject):
    """
    Lightweight HTTP server to serve PDF reports to Android app on demand.
    Runs on port 8001 by default.
    """
    report_requested = Signal()  # Signal to main thread to generate PDF
    
    def __init__(self, port=8001, parent=None):
        super().__init__(parent)
        self.port = port
        self.httpd = None
        self.thread = None
        self.is_running = False
        self._report_event = threading.Event()
        self._report_path = None
        self._device_id = None
        
    def start(self):
        if self.is_running: return True
        try:
            self.httpd = HTTPServer(('0.0.0.0', self.port), ReportRequestHandler)
            self.httpd.api_obj = self
            self.thread = threading.Thread(target=self.httpd.serve_forever)
            self.thread.daemon = True
            self.thread.start()
            self.is_running = True
            logger.info(f"Direct Report Server started on port {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start report server: {e}")
            return False

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        self.is_running = False

    def handle_report_request(self, handler, device_id):
        """Handle incoming GET /report request for specific device"""
        import json
        from pathlib import Path
        
        logger.info(f"PDF report requested for device/request_id: {device_id}")

        # First, check if this is a completed PDF from the queue system
        if CONFIG:
            pdf_queue_file = CONFIG.REPORTS_QUEUE_FILE
        else:
            pdf_queue_file = Path("data/pdf_queue.json")
        
        if pdf_queue_file.exists():
            try:
                with open(pdf_queue_file, 'r') as f:
                    queue_data = json.load(f)
                
                completed = queue_data.get("completed", {})
                if device_id in completed:
                    request_info = completed[device_id]
                    if request_info.get("status") == "completed":
                        file_path = request_info.get("file_path")
                        filename = request_info.get("filename", f"vehicle_report_{device_id}.pdf")
                        
                        if file_path and os.path.exists(file_path):
                            try:
                                with open(file_path, 'rb') as f:
                                    content = f.read()
                                handler.send_response(200)
                                handler.send_header('Content-type', 'application/pdf')
                                handler.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                                handler.send_header('Content-Length', str(len(content)))
                                handler.end_headers()
                                handler.wfile.write(content)
                                logger.info(f"Report sent from queue: {filename}")
                                return
                            except Exception as e:
                                logger.error(f"Error sending queued file: {e}")
            except Exception as e:
                logger.debug(f"Error checking PDF queue: {e}")

        # Fallback to on-demand generation (original behavior)
        # Clear previous event
        self._report_event.clear()
        self._report_path = None
        self._device_id = device_id

        # Emit signal to main thread (PyQt) to generate report
        # This is thread-safe because signals are queued
        self.report_requested.emit()

        # Wait for report generation (max 10 seconds)
        if self._report_event.wait(timeout=10):
            if self._report_path and os.path.exists(self._report_path):
                try:
                    with open(self._report_path, 'rb') as f:
                        content = f.read()
                    handler.send_response(200)
                    handler.send_header('Content-type', 'application/pdf')
                    handler.send_header('Content-Disposition', f'attachment; filename="vehicle_report_{device_id}.pdf"')
                    handler.send_header('Content-Length', str(len(content)))
                    handler.end_headers()
                    handler.wfile.write(content)
                    logger.info(f"Report sent to device {device_id}")
                except Exception as e:
                    logger.error(f"Error sending file: {e}")
                    handler.send_error(500, f"Error sending file: {e}")
            else:
                handler.send_error(500, "Report generated but file not found")
        else:
            handler.send_error(503, "Report generation timed out")

    def set_report_ready(self, path):
        """Called by main thread when PDF is ready"""
        self._report_path = path
        self._report_event.set()

    def get_device_id(self):
        """Get the current device_id for report generation"""
        return self._device_id


class LiveDataWebSocketClient(QObject):
    """
    WebSocket client for real-time data from mobile server.
    Runs in background thread, emits PyQt signals for UI updates.

    Supports authenticated connections with user isolation.
    """

    # Signals
    data_received = Signal(dict)       # New OBD data received
    car_connected = Signal(dict)       # New car connected
    car_disconnected = Signal(str)     # Car disconnected (device_id)
    connection_status = Signal(bool)   # WebSocket connection status
    auth_status = Signal(bool, str)    # Authentication status (success, message)

    def __init__(self, server_url: str = "http://localhost:8000",
                 api_key: str = None, profile_id: int = None):
        super().__init__()
        # Convert HTTP to WebSocket URL
        self.ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        self.ws = None
        self.running = False
        self.thread = None
        self.reconnect_delay = 5  # seconds

        # Authentication credentials
        self.api_key = api_key
        self.profile_id = profile_id
        self.is_authenticated = False

    def set_credentials(self, api_key: str, profile_id: int):
        """Set authentication credentials for secure connection"""
        self.api_key = api_key
        self.profile_id = profile_id
        logger.info(f"WebSocket credentials set for profile_id={profile_id}")

    def start(self):
        """Start WebSocket connection in background thread"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        self.is_authenticated = False
        if self.ws:
            self.ws.close()

    def _run_loop(self):
        """Main WebSocket loop with auto-reconnect"""
        if not WEBSOCKET_AVAILABLE:
            logger.warning("WebSocket library not available - WebSocket client disabled")
            self.running = False
            return

        while self.running:
            try:
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )
                self.ws.run_forever()

            except Exception as e:
                logger.error(f"WebSocket error: {e}")

            if self.running:
                # Reconnect after delay
                self.is_authenticated = False
                time.sleep(self.reconnect_delay)

    def _on_open(self, ws):
        """Called when WebSocket connects - send authentication"""
        logger.info("WebSocket connected to server")

        # Send authentication message if credentials are set
        if self.api_key and self.profile_id is not None:
            auth_message = json.dumps({
                'type': 'auth',
                'api_key': self.api_key,
                'profile_id': self.profile_id
            })
            try:
                ws.send(auth_message)
                logger.info(f"WebSocket auth sent for profile_id={self.profile_id}")
            except Exception as e:
                logger.error(f"Failed to send WebSocket auth: {e}")
                self.auth_status.emit(False, str(e))
        else:
            # No credentials - unauthenticated connection (limited access)
            logger.warning("WebSocket connected without authentication (limited data access)")
            self.connection_status.emit(True)

    def _on_message(self, ws, message):
        """Called when message received from server"""
        try:
            data = json.loads(message)
            msg_type = data.get('type', 'data')

            # Handle authentication response
            if msg_type == 'auth_success':
                self.is_authenticated = True
                self.auth_status.emit(True, data.get('message', 'Authenticated'))
                self.connection_status.emit(True)
                logger.info(f"WebSocket authenticated for profile_id={data.get('profile_id')}")
                return

            if msg_type == 'error':
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"WebSocket error: {error_msg}")
                self.auth_status.emit(False, error_msg)
                return

            # Handle data messages (only if authenticated or public)
            if msg_type == 'obd_data':
                self.data_received.emit(data.get('payload', {}))
            elif msg_type == 'car_connected':
                self.car_connected.emit(data.get('payload', {}))
            elif msg_type == 'car_disconnected':
                self.car_disconnected.emit(data.get('device_id', ''))
            else:
                # Generic data
                self.data_received.emit(data)

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from WebSocket: {message[:100]}")

    def _on_error(self, ws, error):
        """Called on WebSocket error"""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status, close_msg):
        """Called when WebSocket closes"""
        logger.info(f"WebSocket closed: {close_status} - {close_msg}")
        self.is_authenticated = False
        self.connection_status.emit(False)

    def send_command(self, command: str, params: dict = None):
        """Send command to server (for two-way communication)"""
        if self.ws and self.running:
            message = json.dumps({
                'type': 'command',
                'command': command,
                'params': params or {}
            })
            self.ws.send(message)

    def send_ping(self):
        """Send heartbeat ping to server"""
        if self.ws and self.running:
            try:
                self.ws.send("ping")
            except Exception as e:
                logger.debug(f"Failed to send ping: {e}")


class MobileServerWrapper(QObject):
    """
    Wrapper for Previlium OBD Server with PyQt5 signals
    Provides clean integration with main application
    """

    # Signals
    data_received = Signal(dict)  # Raw Android data
    server_started = Signal()
    server_stopped = Signal()
    error_occurred = Signal(str)
    connection_update = Signal(str, str)  # (device_id, status)

    def __init__(self, port=8000, parent=None):
        super().__init__(parent)
        self.port = port
        self.server_url = f"http://localhost:{port}"
        self.server_process = None
        self.is_running = False
        self.active_profile = None
        self.active_sessions = {}  # profile_id -> timestamp
        self._check_timer = QTimer(self)
        self._check_timer.timeout.connect(self._check_for_data)

        # HTTP Session for connection pooling (MAJOR PERFORMANCE BOOST)
        self.session = requests.Session()
        self.session.headers.update({'Connection': 'keep-alive'})

        # Cache for network info (reduces expensive system calls)
        self._network_info_cache = None
        self._network_info_timestamp = 0
        self._network_cache_duration = 60  # Cache for 60 seconds

        # Background worker for non-blocking requests
        self._data_worker = None

        # Path to Previlium server - dynamically resolve relative to this file
        self.previlium_path = Path(__file__).parent / "Previlium_OBD_Server"

        # Verify path exists
        if not self.previlium_path.exists():
            logger.error(f"Previlium server directory not found at: {self.previlium_path}")
            if CONFIG:
                logger.error(f"Please ensure Previlium server is installed at: {CONFIG.SERVER_DIR}")
            else:
                logger.error("Please ensure Previlium server is installed at correct location")

        logger.info(f"Mobile Server Wrapper initialized for Previlium server on port {port}")

        # Create a mock server object for compatibility with server_tab.py
        self.server = self

    def start_server(self):
        """Start Previlium OBD server"""
        try:
            # Check if server is already running
            if self._check_server_running():
                logger.info("Previlium server already running")
                self.is_running = True
                self._check_timer.start(2000)  # Check every 2 seconds
                self.server_started.emit()
                return True

            if self.is_running:
                logger.warning("Server already running")
                return False

            # Check if Previlium directory exists
            if not self.previlium_path.exists():
                error_msg = f"Previlium server directory not found: {self.previlium_path}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False

            # Start Previlium server using uvicorn
            logger.info(f"Starting Previlium server from: {self.previlium_path}")

            # Change to Previlium directory and start server
            cmd = [
                "cmd", "/c", "start", "Previlium API Server",
                "cmd", "/k",
                f"cd /d \"{self.previlium_path}\" && uvicorn main:app --host 0.0.0.0 --port {self.port}"
            ]

            self.server_process = subprocess.Popen(
                cmd,
                cwd=str(self.previlium_path),
                shell=True
            )

            # Wait a moment for server to start
            import time
            time.sleep(2)

            # Verify server is running
            if self._check_server_running():
                self.is_running = True
                self._check_timer.start(2000)  # Check every 2 seconds
                self.server_started.emit()
                logger.info(f"Previlium server started successfully on port {self.port}")
                return True
            else:
                error_msg = "Previlium server failed to start or is not responding"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False

        except Exception as e:
            error_msg = f"Failed to start Previlium server: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def stop_server(self):
        """Stop Previlium OBD server"""
        try:
            if not self.is_running:
                logger.warning("Server not running")
                return False

            self._check_timer.stop()

            # Note: We don't actually stop the Previlium server process
            # because it might be used by other applications
            # Just disconnect from it
            logger.info("Disconnecting from Previlium server")

            self.is_running = False
            self.server_stopped.emit()
            logger.info("Disconnected from Previlium server")
            return True

        except Exception as e:
            error_msg = f"Failed to disconnect from server: {e}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def _check_server_running(self) -> bool:
        """Check if Previlium server is running and responding"""
        try:
            response = self.session.get(f"{self.server_url}/", timeout=0.5)
            return response.status_code == 200
        except:
            return False

    def set_active_profile(self, profile_name: str):
        """Set the currently active profile"""
        self.active_profile = profile_name
        logger.info(f"Active profile set to: {profile_name}")

    def _check_for_data(self):
        """
        Periodically check for new data from the Previlium server (non-blocking)
        """
        if not self.is_running:
            return

        # Don't start a new request if one is already running
        if self._data_worker and self._data_worker.isRunning():
            return

        # Start background HTTP request
        self._data_worker = HttpWorker(
            self.session,
            f"{self.server_url}/dashboard/api/history",
            params={"limit": 10},
            timeout=0.5
        )
        self._data_worker.finished.connect(self._on_data_received)
        self._data_worker.start()

    @Slot(object)
    def _on_data_received(self, data):
        """Handle data received from background thread"""
        if not data:
            return

        records = data.get('records', [])
        if records:
            # Get the most recent record
            latest = records[0]
            
            # Track active session - robustly extract profile_id
            profile_id = latest.get('profile_id') or latest.get('vehicle_id')
            
            # Check for camelCase alternative from some API versions
            if profile_id is None:
                profile_id = latest.get('profileId')
                
            if profile_id:
                self.active_sessions[str(profile_id)] = time.time()

            # Emit signal with data
            self.data_received.emit(latest)

            # Extract device ID
            device_id = latest.get('device_id', 'unknown')
            self.connection_update.emit(device_id, 'active')

    def get_active_sessions(self, timeout=30):
        """Get list of active profile IDs (seen in last 'timeout' seconds)"""
        current_time = time.time()
        active = []
        # Clean up and collect
        for pid, ts in list(self.active_sessions.items()):
            if current_time - ts < timeout:
                active.append(pid)
            else:
                del self.active_sessions[pid]
        return active

    def get_status(self) -> Dict[str, Any]:
        """Get server status information"""
        return {
            'running': self.is_running,
            'port': self.port,
            'active_profile': self.active_profile,
            'server_url': self.server_url,
            'server_type': 'Previlium OBD Server'
        }

    def get_server_info(self) -> Dict[str, Any]:
        """Get server information (compatible with existing interface)"""
        try:
            if not self.is_running:
                return {'error': 'Server not running'}

            # Get stats from Previlium server with session and reduced timeout
            response = self.session.get(f"{self.server_url}/dashboard/api/stats", timeout=0.5)

            if response.status_code == 200:
                stats = response.json()
                return {
                    'server_type': 'Previlium OBD Server',
                    'port': self.port,
                    'url': self.server_url,
                    'stats': stats,
                    'network_info': self._get_network_info()
                }
            else:
                return {'error': 'Failed to get server stats'}

        except Exception as e:
            logger.error(f"Failed to get server info: {e}")
            return {'error': str(e)}

    def _get_network_info(self) -> Dict[str, Any]:
        """Get network information with caching (network info rarely changes)"""
        import socket

        # Return cached data if still valid
        current_time = time.time()
        if self._network_info_cache and (current_time - self._network_info_timestamp) < self._network_cache_duration:
            return self._network_info_cache

        # Refresh network info
        network_info = {}

        try:
            import netifaces
            # Get all network interfaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)

                if netifaces.AF_INET in addrs:
                    ipv4 = addrs[netifaces.AF_INET][0]['addr']
                    network_info[interface] = {
                        'ipv4': ipv4,
                        'ipv6': addrs.get(netifaces.AF_INET6, [{}])[0].get('addr', 'N/A'),
                        'mac': addrs.get(netifaces.AF_LINK, [{}])[0].get('addr', 'N/A')
                    }
        except:
            # Fallback if netifaces is not available
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            network_info['default'] = {
                'ipv4': local_ip,
                'ipv6': 'N/A',
                'mac': 'N/A'
            }

        # Cache result
        self._network_info_cache = network_info
        self._network_info_timestamp = current_time

        return network_info

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics (compatible with existing interface)"""
        try:
            if not self.is_running:
                return {'error': 'Server not running'}

            response = self.session.get(f"{self.server_url}/dashboard/api/stats", timeout=0.5)

            if response.status_code == 200:
                return response.json()
            else:
                return {'error': 'Failed to get database stats'}

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {'error': str(e)}


# For backwards compatibility and testing
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    def on_data(data):
        print(f"Received data: {data}")

    wrapper = MobileServerWrapper(port=8080)
    wrapper.data_received.connect(on_data)
    wrapper.start_server()

    print(f"Server running: {wrapper.is_running}")
    print("Press Ctrl+C to stop...")

    sys.exit(app.exec())
