"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Api Key Sync

API Key Sync Module
Automatically synchronizes API keys between Desktop and Server

============================================================================
DEPRECATION WARNING:
============================================================================
This module is DEPRECATED as of January 2026.

The API key management system has been refactored to use the server as the
single source of truth. All API key operations now go through the server API
endpoints instead of file-based synchronization.

New approach:
- Server stores all API keys in api_keys.json (source of truth)
- Desktop app loads keys from server API (/api/admin/api-keys)
- Changes are synced to server immediately via PUT /api/admin/api-keys/{key_id}
- Server sends email notifications automatically on changes
- No local file synchronization needed

Please use server_api_client.py for all API key operations.

This file is retained for backwards compatibility only and may be removed
in future versions.
============================================================================
"""

import os
import json
import shutil
import logging
import warnings

# Show deprecation warning when module is imported
warnings.warn(
    "api_key_sync.py is deprecated. Use server_api_client.py for API key operations.",
    DeprecationWarning,
    stacklevel=2
)
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Import config for path management
try:
    from config import get_config
    CONFIG = get_config()
    DESKTOP_API_KEYS_PATH = str(CONFIG.API_KEYS_FILE)
    # Try to get server path from config if available
    OBD_SERVER_PATH = CONFIG.get_obd_server_path() if hasattr(CONFIG, 'get_obd_server_path') else None
except:
    CONFIG = None
    DESKTOP_API_KEYS_PATH = r"c:\D Drive\Predict\PredictData\system\config\api_keys.json"
    OBD_SERVER_PATH = None

# Server paths - these are the actual OBDserver locations that need updating
# These are intentionally hard-coded as they represent external server locations
SERVER_PATHS = []
if OBD_SERVER_PATH:
    SERVER_PATHS.append(str(Path(OBD_SERVER_PATH) / "config" / "api_keys.json"))
# Always include legacy paths as fallback for older installations
SERVER_PATHS.extend([
    r"C:\OBDserver\config\api_keys.json",
    r"C:\OBDserver\Previlium_OBD_Server\config\api_keys.json"
])
# Remove duplicates while preserving order
SERVER_PATHS = list(dict.fromkeys(SERVER_PATHS))


def sync_api_keys_to_server(
    desktop_keys_path: Optional[str] = None,
    server_paths: Optional[List[str]] = None,
    backup: bool = True
) -> Dict[str, Any]:
    """
    Sync API keys from desktop to server locations.

    Args:
        desktop_keys_path: Path to desktop API keys file (uses default if None)
        server_paths: List of server paths to sync to (uses defaults if None)
        backup: Whether to create backups before syncing

    Returns:
        Dictionary with sync results
    """
    desktop_path = desktop_keys_path or DESKTOP_API_KEYS_PATH
    servers = server_paths or SERVER_PATHS

    result = {
        "success": False,
        "synced_servers": [],
        "failed_servers": [],
        "keys_synced": 0,
        "timestamp": datetime.now().isoformat(),
        "errors": []
    }

    try:
        # Load desktop keys
        if not os.path.exists(desktop_path):
            result["errors"].append(f"Desktop keys file not found: {desktop_path}")
            logger.error(f"Desktop keys file not found: {desktop_path}")
            return result

        with open(desktop_path, 'r') as f:
            desktop_keys = json.load(f)

        result["keys_synced"] = len(desktop_keys)

        # Sync to each server location
        for server_path in servers:
            try:
                # Create backup if requested
                if backup and os.path.exists(server_path):
                    backup_path = f"{server_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(server_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")

                # Ensure server directory exists
                os.makedirs(os.path.dirname(server_path), exist_ok=True)

                # Load existing server keys
                server_keys = {}
                if os.path.exists(server_path):
                    with open(server_path, 'r') as f:
                        server_keys = json.load(f)

                # Merge desktop keys into server keys (desktop takes precedence)
                # This ensures any new keys from desktop are added to server
                for key_id, key_data in desktop_keys.items():
                    # Remove encrypted/hidden fields that are desktop-only
                    clean_key_data = {k: v for k, v in key_data.items()
                                     if k not in ['key_encrypted', 'key_hidden']}
                    server_keys[key_id] = clean_key_data

                # Save merged keys to server
                with open(server_path, 'w') as f:
                    json.dump(server_keys, f, indent=2)

                result["synced_servers"].append(server_path)
                logger.info(f"Successfully synced keys to: {server_path}")

            except Exception as e:
                error_msg = f"Failed to sync to {server_path}: {str(e)}"
                result["failed_servers"].append(server_path)
                result["errors"].append(error_msg)
                logger.error(error_msg)

        # Mark as success if at least one server was synced
        result["success"] = len(result["synced_servers"]) > 0

    except Exception as e:
        error_msg = f"Sync failed: {str(e)}"
        result["errors"].append(error_msg)
        logger.error(error_msg)

    return result


def sync_single_key_to_server(
    key_id: str,
    key_data: Dict[str, Any],
    server_paths: Optional[List[str]] = None
) -> bool:
    """
    Sync a single API key to server locations.

    Args:
        key_id: The key identifier
        key_data: The key data dictionary
        server_paths: List of server paths (uses defaults if None)

    Returns:
        True if synced to at least one server
    """
    servers = server_paths or SERVER_PATHS
    synced = False

    # Remove desktop-only fields
    clean_key_data = {k: v for k, v in key_data.items()
                     if k not in ['key_encrypted', 'key_hidden']}

    for server_path in servers:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(server_path), exist_ok=True)

            # Load existing server keys
            server_keys = {}
            if os.path.exists(server_path):
                with open(server_path, 'r') as f:
                    server_keys = json.load(f)

            # Add/update the key
            server_keys[key_id] = clean_key_data

            # Save back
            with open(server_path, 'w') as f:
                json.dump(server_keys, f, indent=2)

            logger.info(f"Synced key {key_id} to {server_path}")
            synced = True

        except Exception as e:
            logger.error(f"Failed to sync key {key_id} to {server_path}: {e}")

    return synced


def get_sync_status() -> Dict[str, Any]:
    """
    Get the current sync status between desktop and servers.

    Returns:
        Dictionary with sync status information
    """
    status = {
        "desktop_keys": 0,
        "server_keys": {},
        "in_sync": False,
        "missing_on_servers": [],
        "checked_at": datetime.now().isoformat()
    }

    try:
        # Load desktop keys
        if os.path.exists(DESKTOP_API_KEYS_PATH):
            with open(DESKTOP_API_KEYS_PATH, 'r') as f:
                desktop_keys = json.load(f)
            status["desktop_keys"] = len(desktop_keys)
            desktop_key_ids = set(desktop_keys.keys())
        else:
            desktop_key_ids = set()

        # Check each server
        all_in_sync = True
        for server_path in SERVER_PATHS:
            server_info = {
                "path": server_path,
                "exists": os.path.exists(server_path),
                "key_count": 0,
                "missing_keys": []
            }

            if server_info["exists"]:
                with open(server_path, 'r') as f:
                    server_keys = json.load(f)
                server_info["key_count"] = len(server_keys)
                server_key_ids = set(server_keys.keys())

                # Find missing keys
                missing = desktop_key_ids - server_key_ids
                server_info["missing_keys"] = list(missing)

                if missing:
                    all_in_sync = False
                    status["missing_on_servers"].extend(missing)
            else:
                all_in_sync = False

            status["server_keys"][server_path] = server_info

        status["in_sync"] = all_in_sync and status["desktop_keys"] > 0

    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        status["error"] = str(e)

    return status


class ApiKeySync:
    """
    High-level API for syncing API keys with role/apps support.

    Usage:
        sync = ApiKeySync()
        sync.sync_api_key(api_key, key_data)
    """

    def __init__(self, server_paths: Optional[List[str]] = None):
        self.server_paths = server_paths or SERVER_PATHS

    def sync_api_key(self, api_key: str, key_data: Dict[str, Any]) -> bool:
        """
        Sync a single API key with full metadata to server.

        Args:
            api_key: The actual API key string
            key_data: Dictionary containing:
                - name: Key name
                - role: owner/driver/admin
                - apps: list like ['obd', 'guardian']
                - tier: free/premium/admin
                - permissions: list of permissions
                - profile_id: associated profile ID
                - owner_id: owner ID (if role=owner)
                - driver_id: driver ID (if role=driver)

        Returns:
            True if synced successfully
        """
        import hashlib
        from datetime import datetime

        # Generate key ID and hash
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        import secrets
        unique_suffix = secrets.token_hex(4)
        key_id = f"key_{timestamp}_{unique_suffix}"

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Build full key data with new fields
        full_key_data = {
            'key_hash': key_hash,
            'name': key_data.get('name', 'Unknown'),
            'role': key_data.get('role', 'owner'),
            'apps': key_data.get('apps', ['obd', 'guardian']),
            'tier': key_data.get('tier', 'free'),
            'profile_id': key_data.get('profile_id'),
            'profile_name': key_data.get('name', ''),
            'owner_id': key_data.get('owner_id'),
            'driver_id': key_data.get('driver_id'),
            'permissions': key_data.get('permissions', ['vehicle_data', 'predict']),
            'created': datetime.now().isoformat(),
            'status': 'active'
        }

        return sync_single_key_to_server(key_id, full_key_data, self.server_paths)

    def revoke_api_key(self, key_hash: str) -> bool:
        """
        Revoke an API key by its hash.

        Args:
            key_hash: The SHA256 hash of the API key

        Returns:
            True if revoked successfully
        """
        revoked = False

        for server_path in self.server_paths:
            try:
                if not os.path.exists(server_path):
                    continue

                with open(server_path, 'r') as f:
                    server_keys = json.load(f)

                # Find and update key by hash
                for key_id, key_data in server_keys.items():
                    if key_data.get('key_hash') == key_hash:
                        server_keys[key_id]['status'] = 'revoked'
                        revoked = True
                        break

                if revoked:
                    with open(server_path, 'w') as f:
                        json.dump(server_keys, f, indent=2)
                    logger.info(f"Revoked key with hash {key_hash[:16]}...")

            except Exception as e:
                logger.error(f"Failed to revoke key in {server_path}: {e}")

        return revoked

    def get_all_keys(self) -> List[Dict[str, Any]]:
        """
        Get all API keys from the first available server.

        Returns:
            List of key data dictionaries
        """
        for server_path in self.server_paths:
            try:
                if os.path.exists(server_path):
                    with open(server_path, 'r') as f:
                        server_keys = json.load(f)
                    return [
                        {**data, 'key_id': key_id}
                        for key_id, data in server_keys.items()
                    ]
            except Exception as e:
                logger.error(f"Failed to load keys from {server_path}: {e}")

        return []

    def update_key_apps(self, key_hash: str, apps: List[str]) -> bool:
        """
        Update the allowed apps for an API key.

        Args:
            key_hash: The SHA256 hash of the API key
            apps: New list of allowed apps ['obd', 'guardian']

        Returns:
            True if updated successfully
        """
        updated = False

        for server_path in self.server_paths:
            try:
                if not os.path.exists(server_path):
                    continue

                with open(server_path, 'r') as f:
                    server_keys = json.load(f)

                for key_id, key_data in server_keys.items():
                    if key_data.get('key_hash') == key_hash:
                        server_keys[key_id]['apps'] = apps
                        updated = True
                        break

                if updated:
                    with open(server_path, 'w') as f:
                        json.dump(server_keys, f, indent=2)
                    logger.info(f"Updated apps for key {key_hash[:16]}... to {apps}")

            except Exception as e:
                logger.error(f"Failed to update key apps in {server_path}: {e}")

        return updated


if __name__ == "__main__":
    # Test sync
    logging.basicConfig(level=logging.INFO)
    print("Testing API Key Sync...")
    print("-" * 60)

    # Check status
    print("\n1. Checking sync status...")
    status = get_sync_status()
    print(f"   Desktop keys: {status['desktop_keys']}")
    print(f"   In sync: {status['in_sync']}")
    if status.get('missing_on_servers'):
        print(f"   Missing on servers: {len(set(status['missing_on_servers']))} keys")

    # Perform sync
    print("\n2. Syncing keys to servers...")
    result = sync_api_keys_to_server()
    print(f"   Success: {result['success']}")
    print(f"   Keys synced: {result['keys_synced']}")
    print(f"   Servers synced: {len(result['synced_servers'])}")
    if result['errors']:
        print(f"   Errors: {result['errors']}")

    print("\n" + "-" * 60)
    print("Sync test complete!")
