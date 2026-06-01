"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Remote Server Client
"""

"""
Remote Server Client - Connects desktop to cloud server

Features:
- HTTP polling for data updates
- WebSocket real-time streaming
- Auto-reconnection
- Local caching
- Error handling
"""

import requests
import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Callable, Optional
from PySide6.QtCore import QObject, Signal, QTimer

logger = logging.getLogger(__name__)


class RemoteServerClient(QObject):
    """
    Client for connecting to remote Predict AI server

    Supports both HTTP polling and WebSocket streaming
    """

    # Signals
    data_received = Signal(dict)  # New data received
    connection_status_changed = Signal(bool, str)  # connected, message
    error_occurred = Signal(str)  # error message
    stats_updated = Signal(dict)  # server stats

    def __init__(self, server_url: str, api_key: str, poll_interval: int = 3):
        """
        Initialize remote server client

        Args:
            server_url: Server URL (e.g., https://predict.previlium.com)
            api_key: API key for authentication
            poll_interval: Polling interval in seconds
        """
        super().__init__()

        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.poll_interval = poll_interval

        # State
        self.is_connected = False
        self.is_polling = False
        self.last_sync_time = None
        self.last_timestamps = {}  # Track last timestamp per profile

        # HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Predict-Desktop-Client/1.0'
        })

        # Polling timer
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_data)

        # Stats
        self.stats = {
            'connected': False,
            'last_sync': None,
            'poll_count': 0,
            'data_received': 0,
            'errors': 0,
            'latency_ms': 0
        }

        logger.info(f"Remote client initialized: {self.server_url}")

    def connect(self) -> bool:
        """
        Connect to remote server and start polling

        Returns:
            True if connection successful
        """
        try:
            # Test connection
            response = self.session.get(f'{self.server_url}/api/health', timeout=10)

            if response.status_code == 200:
                self.is_connected = True
                self.connection_status_changed.emit(True, "Connected to remote server")
                logger.info(f"Connected to remote server: {self.server_url}")

                # Start polling
                self.start_polling()

                return True
            else:
                error_msg = f"Connection failed: HTTP {response.status_code}"
                self.connection_status_changed.emit(False, error_msg)
                logger.error(error_msg)
                return False

        except requests.exceptions.RequestException as e:
            error_msg = f"Connection error: {str(e)}"
            self.connection_status_changed.emit(False, error_msg)
            self.error_occurred.emit(error_msg)
            logger.error(error_msg)
            return False

    def disconnect(self):
        """Disconnect from remote server"""
        self.stop_polling()
        self.is_connected = False
        self.connection_status_changed.emit(False, "Disconnected")
        logger.info("Disconnected from remote server")

    def start_polling(self):
        """Start polling for data updates"""
        if not self.is_polling:
            self.is_polling = True
            self.poll_timer.start(self.poll_interval * 1000)  # Convert to milliseconds
            logger.info(f"Started polling (interval: {self.poll_interval}s)")

    def stop_polling(self):
        """Stop polling"""
        if self.is_polling:
            self.is_polling = False
            self.poll_timer.stop()
            logger.info("Stopped polling")

    def set_poll_interval(self, interval: int):
        """
        Change poll interval

        Args:
            interval: New interval in seconds
        """
        self.poll_interval = interval
        if self.is_polling:
            self.poll_timer.setInterval(interval * 1000)
            logger.info(f"Poll interval changed to {interval}s")

    def _poll_data(self):
        """Poll for new data (called by timer)"""
        try:
            start_time = time.time()

            # Get list of profiles
            profiles = self.get_profiles()

            if not profiles:
                logger.debug("No profiles found on server")
                return

            # Poll each profile for new data
            for profile_id in profiles:
                self._poll_profile(profile_id)

            # Update stats
            self.stats['poll_count'] += 1
            self.stats['last_sync'] = datetime.now().isoformat()
            self.stats['latency_ms'] = int((time.time() - start_time) * 1000)
            self.stats['connected'] = True

            self.last_sync_time = datetime.now()
            self.stats_updated.emit(self.stats)

        except Exception as e:
            self.stats['errors'] += 1
            self.error_occurred.emit(f"Poll error: {str(e)}")
            logger.error(f"Poll error: {e}")

    def _poll_profile(self, profile_id: str):
        """
        Poll for new data for a specific profile

        Args:
            profile_id: Vehicle profile ID
        """
        try:
            # Check if we have a last timestamp
            last_timestamp = self.last_timestamps.get(profile_id)

            if last_timestamp:
                # Get data since last timestamp
                url = f'{self.server_url}/api/profiles/{profile_id}/since/{last_timestamp}'
            else:
                # Get latest data only (first poll)
                url = f'{self.server_url}/api/profiles/{profile_id}/latest'

            response = self.session.get(url, timeout=5)

            if response.status_code == 200:
                result = response.json()

                # Process data
                if last_timestamp:
                    # Multiple data points
                    data_list = result.get('data', [])
                    for data in data_list:
                        if data:
                            self._process_data_point(data, profile_id)
                else:
                    # Single latest data point
                    data = result.get('data')
                    if data:
                        self._process_data_point(data, profile_id)

            elif response.status_code != 404:  # 404 is ok (no data)
                logger.warning(f"Poll failed for {profile_id}: HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            logger.warning(f"Poll timeout for {profile_id}")
        except Exception as e:
            logger.error(f"Error polling {profile_id}: {e}")

    def _process_data_point(self, data: Dict, profile_id: str):
        """
        Process a single data point

        Args:
            data: Data dictionary from server
            profile_id: Vehicle profile ID
        """
        try:
            # Update last timestamp
            timestamp = data.get('timestamp')
            if timestamp:
                self.last_timestamps[profile_id] = timestamp

            # Convert flat database format to unified frame format
            unified_frame = self._convert_to_unified_frame(data)

            # Emit signal
            self.data_received.emit(unified_frame)
            self.stats['data_received'] += 1

            logger.debug(f"Processed data for {profile_id} at {timestamp}")

        except Exception as e:
            logger.error(f"Error processing data point: {e}")

    def _convert_to_unified_frame(self, db_data: Dict) -> Dict:
        """
        Convert database flat format to unified frame format

        Args:
            db_data: Data from database (flat format)

        Returns:
            Unified frame format
        """
        # Create unified frame structure
        unified = {
            'rpm': db_data.get('rpm'),
            'speed': db_data.get('speed'),
            'coolant_temp': db_data.get('coolant_temp'),
            'battery_voltage': db_data.get('battery_voltage'),
            'engine_load': db_data.get('engine_load'),
            'intake_pressure': db_data.get('intake_pressure'),
            'air_temp': db_data.get('air_temp'),
            'maf_flow': db_data.get('maf_flow'),
            'throttle_pos': db_data.get('throttle_pos'),
            'fuel_pressure': db_data.get('fuel_pressure'),

            'metadata': {
                'source': 'remote_server',
                'vehicle_id': db_data.get('profile_id'),
                'timestamp': db_data.get('timestamp'),
                'profile_name': db_data.get('profile_id')
            }
        }

        # Add GPS if available
        if db_data.get('latitude') and db_data.get('longitude'):
            unified['gps'] = {
                'latitude': db_data.get('latitude'),
                'longitude': db_data.get('longitude')
            }

        # Add accelerometer if available
        if db_data.get('acceleration_x'):
            unified['accelerometer'] = {
                'x': db_data.get('acceleration_x'),
                'y': db_data.get('acceleration_y'),
                'z': db_data.get('acceleration_z')
            }

        return unified

    # ========================================
    # Public API Methods
    # ========================================

    def get_profiles(self) -> List[str]:
        """
        Get list of all vehicle profiles

        Returns:
            List of profile IDs
        """
        try:
            response = self.session.get(f'{self.server_url}/api/profiles', timeout=5)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get profiles: HTTP {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error getting profiles: {e}")
            return []

    def get_latest_data(self, profile_id: str) -> Optional[Dict]:
        """
        Get latest data for a profile

        Args:
            profile_id: Vehicle profile ID

        Returns:
            Latest data or None
        """
        try:
            response = self.session.get(
                f'{self.server_url}/api/profiles/{profile_id}/latest',
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('data')
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting latest data: {e}")
            return None

    def get_sessions(self, profile_id: str) -> List[Dict]:
        """
        Get session list for a profile

        Args:
            profile_id: Vehicle profile ID

        Returns:
            List of sessions
        """
        try:
            response = self.session.get(
                f'{self.server_url}/api/profiles/{profile_id}/sessions',
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('sessions', [])
            else:
                return []

        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            return []

    def get_server_stats(self) -> Dict:
        """
        Get server statistics

        Returns:
            Server stats dictionary
        """
        try:
            response = self.session.get(f'{self.server_url}/api/stats', timeout=5)

            if response.status_code == 200:
                return response.json()
            else:
                return {}

        except Exception as e:
            logger.error(f"Error getting server stats: {e}")
            return {}

    def test_connection(self) -> tuple[bool, str]:
        """
        Test connection to server

        Returns:
            (success, message) tuple
        """
        try:
            start_time = time.time()
            response = self.session.get(f'{self.server_url}/api/health', timeout=10)
            latency = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                return True, f"Connected successfully ({latency}ms)"
            else:
                return False, f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection refused"
        except Exception as e:
            return False, str(e)

    def get_stats(self) -> Dict:
        """Get client statistics"""
        return self.stats.copy()
