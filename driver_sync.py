"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Driver Sync Service
Purpose: Synchronize driver data between Desktop app and server with API key authentication
"""

import json
import os
import time
import uuid
import hashlib
import logging
import threading
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

# Configure logging
sync_logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    'server_url': 'http://localhost:8000',
    'api_key': '',
    'auto_sync': True,
    'sync_interval_seconds': 300,  # 5 minutes
    'request_timeout': 30,
    'max_retries': 3,
    'retry_delay': 2
}


class DriverSyncService:
    """
    Service for synchronizing driver data between Desktop app and server.

    Features:
    - API key authentication
    - Automatic background sync
    - Offline queue support
    - Last-write-wins conflict resolution
    """

    def __init__(self, config_path: str = './config/server_config.json',
                 vehicle_manager=None, offline_queue=None):
        """
        Initialize the Driver Sync Service.

        Args:
            config_path: Path to server configuration file
            vehicle_manager: VehicleProfileManager instance for local DB operations
            offline_queue: OfflineSyncQueue instance for offline support
        """
        self.config_path = config_path
        self.vehicle_manager = vehicle_manager
        self.offline_queue = offline_queue

        # Load configuration
        self.config = self._load_config()
        self.server_url = self.config.get('server_url', DEFAULT_CONFIG['server_url'])
        self.api_key = self.config.get('api_key', '')

        # Sync state
        self._sync_lock = threading.Lock()
        self._is_syncing = False
        self._last_sync_time = 0
        self._sync_thread = None
        self._stop_sync = False

        # Statistics
        self._sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'drivers_synced': 0,
            'last_error': None
        }

        sync_logger.info("DriverSyncService initialized")

    def _load_config(self) -> Dict[str, Any]:
        """Load server configuration from file"""
        try:
            config_file = Path(self.config_path)

            # Try multiple config locations
            possible_paths = [
                config_file,
                Path('./config/server_config.json'),
                Path('PredictData/system/config/server_config.json'),
                Path('../config/server_config.json')
            ]

            for path in possible_paths:
                if path.exists():
                    with open(path, 'r') as f:
                        config = json.load(f)
                        sync_logger.info(f"Loaded config from {path}")
                        return config

            # Create default config
            sync_logger.warning("No config found, using defaults")
            return DEFAULT_CONFIG.copy()

        except Exception as e:
            sync_logger.error(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()

    def save_config(self):
        """Save current configuration to file"""
        try:
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)

            config_data = {
                'server_url': self.server_url,
                'api_key': self.api_key,
                'auto_sync': self.config.get('auto_sync', True),
                'sync_interval_seconds': self.config.get('sync_interval_seconds', 300)
            }

            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)

            sync_logger.info(f"Saved config to {config_file}")
            return True

        except Exception as e:
            sync_logger.error(f"Error saving config: {e}")
            return False

    def set_api_key(self, api_key: str):
        """Set the API key for authentication"""
        self.api_key = api_key
        self.config['api_key'] = api_key
        self.save_config()

    def set_server_url(self, url: str):
        """Set the server URL"""
        self.server_url = url.rstrip('/')
        self.config['server_url'] = self.server_url
        self.save_config()

    def _get_headers(self, idempotency_key: str = None) -> Dict[str, str]:
        """Get request headers with authentication"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            headers['X-API-Key'] = self.api_key

        if idempotency_key:
            headers['X-Idempotency-Key'] = idempotency_key

        return headers

    def _make_request(self, method: str, endpoint: str, data: Dict = None,
                     idempotency_key: str = None) -> Tuple[bool, Any]:
        """
        Make HTTP request to server with retry logic.

        Returns:
            Tuple of (success, response_data or error_message)
        """
        url = f"{self.server_url}{endpoint}"
        headers = self._get_headers(idempotency_key)
        timeout = self.config.get('request_timeout', 30)
        max_retries = self.config.get('max_retries', 3)
        retry_delay = self.config.get('retry_delay', 2)

        for attempt in range(max_retries):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=headers, timeout=timeout)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=headers, json=data, timeout=timeout)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=headers, json=data, timeout=timeout)
                elif method.upper() == 'DELETE':
                    response = requests.delete(url, headers=headers, timeout=timeout)
                else:
                    return False, f"Unsupported method: {method}"

                # Check response
                if response.status_code in (200, 201):
                    try:
                        return True, response.json()
                    except:
                        return True, response.text
                elif response.status_code == 401:
                    return False, "Authentication failed - check API key"
                elif response.status_code == 404:
                    return False, "Endpoint not found"
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = int(response.headers.get('Retry-After', retry_delay * 2))
                    time.sleep(retry_after)
                    continue
                else:
                    return False, f"Server error: {response.status_code}"

            except ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                return False, "Connection error - server unreachable"
            except Timeout:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                return False, "Request timeout"
            except RequestException as e:
                return False, f"Request error: {str(e)}"

        return False, "Max retries exceeded"

    def check_server_connection(self) -> bool:
        """Check if server is reachable"""
        try:
            success, _ = self._make_request('GET', '/api/health')
            return success
        except:
            return False

    # ==================== DRIVER SYNC METHODS ====================

    def sync_drivers_from_server(self, profile_id: int = None) -> Tuple[bool, str]:
        """
        Pull driver data from server and update local database.

        Args:
            profile_id: Optional - sync only for specific profile

        Returns:
            Tuple of (success, message)
        """
        if not self.vehicle_manager:
            return False, "Vehicle manager not configured"

        with self._sync_lock:
            if self._is_syncing:
                return False, "Sync already in progress"
            self._is_syncing = True

        try:
            # Build endpoint
            if profile_id:
                endpoint = f"/api/drivers/list/{profile_id}"
            else:
                endpoint = "/api/drivers/list"

            success, response = self._make_request('GET', endpoint)

            if not success:
                self._sync_stats['failed_syncs'] += 1
                self._sync_stats['last_error'] = response
                return False, f"Failed to fetch drivers: {response}"

            # Process server drivers
            server_drivers = response if isinstance(response, list) else response.get('drivers', [])
            synced_count = 0

            for server_driver in server_drivers:
                driver_id = server_driver.get('driver_id')
                if not driver_id:
                    continue

                # Ensure guardian_role is included from server data
                if 'guardian_role' not in server_driver:
                    server_driver['guardian_role'] = 'driver'

                # Check if driver exists locally
                local_driver = self.vehicle_manager.get_driver_by_id(driver_id)

                if local_driver:
                    # Conflict resolution: last-write-wins based on updated_at
                    server_updated = server_driver.get('updated_at', '')
                    local_updated = local_driver.get('updated_at', '')

                    if server_updated > local_updated:
                        # Server is newer - update local
                        self.vehicle_manager.update_driver(driver_id, server_driver)
                        synced_count += 1
                else:
                    # New driver from server - add locally
                    self.vehicle_manager.add_driver(
                        server_driver.get('profile_id'),
                        server_driver
                    )
                    synced_count += 1

            # Update sync stats
            self._sync_stats['total_syncs'] += 1
            self._sync_stats['successful_syncs'] += 1
            self._sync_stats['drivers_synced'] += synced_count
            self._last_sync_time = time.time()

            sync_logger.info(f"Synced {synced_count} drivers from server")
            return True, f"Synced {synced_count} drivers"

        except Exception as e:
            self._sync_stats['failed_syncs'] += 1
            self._sync_stats['last_error'] = str(e)
            sync_logger.error(f"Sync error: {e}")
            return False, f"Sync error: {str(e)}"

        finally:
            with self._sync_lock:
                self._is_syncing = False

    def push_driver_to_server(self, driver_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Push a driver to the server.

        Args:
            driver_data: Driver information (including guardian_role)

        Returns:
            Tuple of (success, message)
        """
        # Ensure guardian_role is included in the payload
        if 'guardian_role' not in driver_data:
            driver_data['guardian_role'] = 'driver'

        idempotency_key = f"driver_create_{driver_data.get('driver_id', uuid.uuid4())}"

        success, response = self._make_request(
            'POST',
            '/api/drivers/create',
            data=driver_data,
            idempotency_key=idempotency_key
        )

        if not success:
            # Queue for later if offline queue available
            if self.offline_queue:
                self.offline_queue.queue_operation(
                    'driver_create',
                    driver_data,
                    idempotency_key
                )
                return False, f"Queued for later: {response}"
            return False, response

        sync_logger.info(f"Pushed driver {driver_data.get('name')} to server")
        return True, "Driver created on server"

    def update_driver_on_server(self, driver_id: str, driver_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Update driver on server (including guardian_role)"""
        idempotency_key = f"driver_update_{driver_id}_{int(time.time())}"

        # Ensure guardian_role is included in the payload
        if 'guardian_role' not in driver_data:
            driver_data['guardian_role'] = 'driver'

        payload = {**driver_data, 'driver_id': driver_id}

        success, response = self._make_request(
            'PUT',
            f'/api/drivers/update/{driver_id}',
            data=payload,
            idempotency_key=idempotency_key
        )

        if not success:
            if self.offline_queue:
                self.offline_queue.queue_operation(
                    'driver_update',
                    payload,
                    idempotency_key
                )
                return False, f"Queued for later: {response}"
            return False, response

        sync_logger.info(f"Updated driver {driver_id} on server")
        return True, "Driver updated on server"

    def delete_driver_on_server(self, driver_id: str) -> Tuple[bool, str]:
        """Delete/deactivate driver on server"""
        idempotency_key = f"driver_delete_{driver_id}_{int(time.time())}"

        success, response = self._make_request(
            'DELETE',
            f'/api/drivers/delete/{driver_id}',
            idempotency_key=idempotency_key
        )

        if not success:
            if self.offline_queue:
                self.offline_queue.queue_operation(
                    'driver_delete',
                    {'driver_id': driver_id},
                    idempotency_key
                )
                return False, f"Queued for later: {response}"
            return False, response

        sync_logger.info(f"Deleted driver {driver_id} on server")
        return True, "Driver deleted on server"

    def link_driver_to_vehicle(self, profile_id: int, driver_id: str,
                               is_primary: bool = False,
                               relationship: str = 'driver') -> Tuple[bool, str]:
        """Link a driver to a vehicle on the server"""
        idempotency_key = f"driver_link_{profile_id}_{driver_id}"

        payload = {
            'profile_id': profile_id,
            'driver_id': driver_id,
            'is_primary': is_primary,
            'relationship': relationship
        }

        success, response = self._make_request(
            'POST',
            '/api/drivers/link',
            data=payload,
            idempotency_key=idempotency_key
        )

        if not success:
            if self.offline_queue:
                self.offline_queue.queue_operation(
                    'driver_link',
                    payload,
                    idempotency_key
                )
                return False, f"Queued for later: {response}"
            return False, response

        sync_logger.info(f"Linked driver {driver_id} to profile {profile_id}")
        return True, "Driver linked to vehicle"

    # ==================== SESSION SYNC METHODS ====================

    def start_session_on_server(self, profile_id: int, driver_id: str) -> Tuple[bool, Optional[str]]:
        """Start a driving session on the server"""
        idempotency_key = f"session_start_{profile_id}_{driver_id}_{int(time.time())}"

        payload = {
            'profile_id': profile_id,
            'driver_id': driver_id
        }

        success, response = self._make_request(
            'POST',
            '/api/drivers/session/start',
            data=payload,
            idempotency_key=idempotency_key
        )

        if success:
            session_id = response.get('session_id') if isinstance(response, dict) else None
            sync_logger.info(f"Started session {session_id} on server")
            return True, session_id

        return False, None

    def end_session_on_server(self, session_id: str, stats: Dict = None) -> Tuple[bool, str]:
        """End a driving session on the server"""
        idempotency_key = f"session_end_{session_id}"

        payload = {
            'session_id': session_id,
            **(stats or {})
        }

        success, response = self._make_request(
            'POST',
            '/api/drivers/session/end',
            data=payload,
            idempotency_key=idempotency_key
        )

        if success:
            sync_logger.info(f"Ended session {session_id} on server")
            return True, "Session ended"

        return False, str(response)

    # ==================== BATCH SYNC METHODS ====================

    def batch_sync_drivers(self, profile_ids: List[int] = None) -> Tuple[bool, str]:
        """
        Perform batch sync of all drivers.

        This method:
        1. Pushes local changes to server
        2. Pulls server changes to local
        3. Resolves any conflicts
        """
        if not self.vehicle_manager:
            return False, "Vehicle manager not configured"

        try:
            # Get all local profiles if none specified
            if not profile_ids:
                profiles = self.vehicle_manager.get_all_profiles()
                profile_ids = [p['profile_id'] for p in profiles]

            total_synced = 0
            errors = []

            for profile_id in profile_ids:
                # Sync drivers for this profile
                success, message = self.sync_drivers_from_server(profile_id)

                if success:
                    # Count synced drivers
                    drivers = self.vehicle_manager.get_drivers_for_profile(profile_id)
                    total_synced += len(drivers)
                else:
                    errors.append(f"Profile {profile_id}: {message}")

            if errors:
                return False, f"Partial sync: {total_synced} drivers, errors: {'; '.join(errors)}"

            return True, f"Synced {total_synced} drivers across {len(profile_ids)} profiles"

        except Exception as e:
            sync_logger.error(f"Batch sync error: {e}")
            return False, f"Batch sync error: {str(e)}"

    # ==================== BACKGROUND SYNC ====================

    def start_auto_sync(self, interval_seconds: int = None):
        """Start automatic background synchronization"""
        if self._sync_thread and self._sync_thread.is_alive():
            sync_logger.warning("Auto sync already running")
            return

        self._stop_sync = False
        interval = interval_seconds or self.config.get('sync_interval_seconds', 300)

        def sync_loop():
            while not self._stop_sync:
                try:
                    # Perform sync
                    self.batch_sync_drivers()

                    # Process offline queue if available
                    if self.offline_queue:
                        self.offline_queue.process_queue(self)

                except Exception as e:
                    sync_logger.error(f"Auto sync error: {e}")

                # Wait for next sync
                for _ in range(interval):
                    if self._stop_sync:
                        break
                    time.sleep(1)

        self._sync_thread = threading.Thread(target=sync_loop, daemon=True)
        self._sync_thread.start()
        sync_logger.info(f"Started auto sync with {interval}s interval")

    def stop_auto_sync(self):
        """Stop automatic background synchronization"""
        self._stop_sync = True
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        sync_logger.info("Stopped auto sync")

    # ==================== STATISTICS ====================

    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        return {
            **self._sync_stats,
            'last_sync_time': self._last_sync_time,
            'is_syncing': self._is_syncing,
            'server_url': self.server_url,
            'has_api_key': bool(self.api_key)
        }

    def reset_stats(self):
        """Reset synchronization statistics"""
        self._sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'drivers_synced': 0,
            'last_error': None
        }


# Convenience function for getting a sync service instance
_sync_service_instance = None

def get_driver_sync_service(vehicle_manager=None, offline_queue=None) -> DriverSyncService:
    """Get or create the driver sync service singleton"""
    global _sync_service_instance

    if _sync_service_instance is None:
        _sync_service_instance = DriverSyncService(
            vehicle_manager=vehicle_manager,
            offline_queue=offline_queue
        )
    elif vehicle_manager:
        _sync_service_instance.vehicle_manager = vehicle_manager

    return _sync_service_instance


if __name__ == "__main__":
    # Test the sync service
    logging.basicConfig(level=logging.INFO)

    service = DriverSyncService()

    print("Server connection:", service.check_server_connection())
    print("Sync stats:", service.get_sync_stats())
