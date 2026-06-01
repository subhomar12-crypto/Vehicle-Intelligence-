"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Server API Client

Server API Client for Desktop Application
Provides HTTP client for unified API key management and server communication.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import urllib.request
import urllib.error
import urllib.parse
import ssl
from pathlib import Path

logger = logging.getLogger(__name__)

# Server configuration
# Production server - same as Android app uses
DEFAULT_SERVER_URL = "https://predict.previlium.com"

# Admin key - read from shared .env file
# Both server and desktop read from the same .env file
ENV_FILE = Path("C:/OBDserver/Previlium_OBD_Server/.env")

def _load_admin_key() -> str:
    """Load admin key from .env file."""
    try:
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text().splitlines():
                line = line.strip()
                if line.startswith("DESKTOP_ADMIN_SECRET="):
                    key = line.split("=", 1)[1].strip()
                    if len(key) >= 32:
                        logger.info(f"Loaded admin key from {ENV_FILE}")
                        return key
    except Exception as e:
        logger.warning(f"Could not read .env file: {e}")

    logger.warning("Admin key not found - ensure server .env file exists")
    return "KEY-NOT-FOUND"

ADMIN_KEY = _load_admin_key()


@dataclass
class ApiResponse:
    """Response wrapper for API calls."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: int = 200


class ServerAPIClient:
    """
    HTTP client for server API communication.

    Handles all API key management operations via the server.
    """

    def __init__(
        self,
        server_url: str = DEFAULT_SERVER_URL,
        admin_key: str = ADMIN_KEY,
        timeout: int = 30
    ):
        """
        Initialize the server API client.

        Args:
            server_url: Base URL of the server (e.g., http://localhost:8000)
            admin_key: Admin key for authentication
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.admin_key = admin_key
        self.timeout = timeout

        # Create SSL context that doesn't verify certificates (for local dev)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> ApiResponse:
        """
        Make an HTTP request to the server.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., /api/admin/api-keys)
            data: Request body data (for POST/PUT)

        Returns:
            ApiResponse with success status and data/error
        """
        url = f"{self.server_url}{endpoint}"

        try:
            # Prepare request
            headers = {
                "X-Admin-Key": self.admin_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "PREDICT-Desktop/1.0"  # Required for Cloudflare
            }

            body = None
            if data is not None:
                body = json.dumps(data).encode('utf-8')

            request = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method=method
            )

            # Make request
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=self.ssl_context if url.startswith('https') else None
            ) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                return ApiResponse(
                    success=response_data.get('success', True),
                    data=response_data,
                    status_code=response.status
                )

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('detail', {}).get('error', str(e))
            except:
                error_msg = str(e)

            logger.error(f"HTTP error {e.code} for {method} {endpoint}: {error_msg}")
            return ApiResponse(
                success=False,
                error=error_msg,
                status_code=e.code
            )

        except urllib.error.URLError as e:
            logger.error(f"URL error for {method} {endpoint}: {e}")
            return ApiResponse(
                success=False,
                error=f"Connection failed: {str(e.reason)}",
                status_code=0
            )

        except Exception as e:
            logger.error(f"Request error for {method} {endpoint}: {e}")
            return ApiResponse(
                success=False,
                error=str(e),
                status_code=0
            )

    # -------------------------------------------------
    # API KEY MANAGEMENT METHODS
    # -------------------------------------------------

    def list_api_keys(self) -> ApiResponse:
        """
        List all API keys with customer information.

        Returns:
            ApiResponse with list of API keys
        """
        return self._make_request("GET", "/api/admin/api-keys")

    def create_api_key(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None,
        tier: str = "free",
        role: str = "owner",
        apps: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        profile_id: Optional[int] = None,
        owner_id: Optional[int] = None,
        send_email: bool = True
    ) -> ApiResponse:
        """
        Create a new API key for a customer.

        Args:
            name: Customer name
            email: Customer email
            phone: Customer phone number (optional)
            tier: Subscription tier (free, basic, premium, enterprise)
            role: User role (owner, driver)
            apps: List of apps (default: ['obd', 'guardian'])
            permissions: List of permissions (default based on tier)
            profile_id: Associated vehicle profile ID (optional)
            owner_id: Owner ID from desktop app (optional)
            send_email: Whether to send the API key via email

        Returns:
            ApiResponse with new API key details
        """
        data = {
            "name": name,
            "email": email,
            "tier": tier,
            "role": role,
            "send_email": send_email
        }
        if phone is not None:
            data["phone"] = phone
        if apps is not None:
            data["apps"] = apps
        if permissions is not None:
            data["permissions"] = permissions
        if profile_id is not None:
            data["profile_id"] = profile_id
        if owner_id is not None:
            data["owner_id"] = owner_id

        return self._make_request("POST", "/api/admin/api-keys", data)

    def update_api_key(
        self,
        key_id: str,
        tier: Optional[str] = None,
        apps: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        status: Optional[str] = None,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        profile_id: Optional[int] = None,
        send_notification: bool = True
    ) -> ApiResponse:
        """
        Update an existing API key's properties.

        Args:
            key_id: API key identifier
            tier: New tier (optional)
            apps: New apps list (optional)
            permissions: New permissions list (optional)
            status: New status (active, revoked, suspended) (optional)
            name: New name (optional)
            email: New email (optional)
            phone: New phone number (optional)
            profile_id: New profile ID (optional)
            send_notification: Whether to send email notification (default: True)

        Returns:
            ApiResponse with update status including email_sent flag
        """
        data = {"send_notification": send_notification}
        if tier is not None:
            data["tier"] = tier
        if apps is not None:
            data["apps"] = apps
        if permissions is not None:
            data["permissions"] = permissions
        if status is not None:
            data["status"] = status
        if name is not None:
            data["name"] = name
        if email is not None:
            data["email"] = email
        if phone is not None:
            data["phone"] = phone
        if profile_id is not None:
            data["profile_id"] = profile_id

        return self._make_request("PUT", f"/api/admin/api-keys/{key_id}", data)

    def regenerate_api_key(
        self,
        key_id: str,
        send_email: bool = True
    ) -> ApiResponse:
        """
        Regenerate a new API key value for an existing key entry.

        Args:
            key_id: API key identifier
            send_email: Whether to send the new API key via email

        Returns:
            ApiResponse with new API key
        """
        data = {"send_email": send_email}
        return self._make_request("POST", f"/api/admin/api-keys/{key_id}/regenerate", data)

    def delete_api_key(self, key_id: str) -> ApiResponse:
        """
        Delete/revoke an API key.

        Args:
            key_id: API key identifier

        Returns:
            ApiResponse with deletion status
        """
        return self._make_request("DELETE", f"/api/admin/api-keys/{key_id}")

    def send_api_key_email(self, key_id: str) -> ApiResponse:
        """
        Send API key to customer via email.

        Note: This requires the key to be regenerated first since we only
        store hashes.

        Args:
            key_id: API key identifier

        Returns:
            ApiResponse with email status
        """
        return self._make_request("POST", f"/api/admin/api-keys/{key_id}/send-email")

    # -------------------------------------------------
    # CUSTOMER MANAGEMENT METHODS
    # -------------------------------------------------

    def list_customers_full(self) -> ApiResponse:
        """
        Get all customers with their full API key information.

        Returns:
            ApiResponse with list of customers
        """
        return self._make_request("GET", "/api/admin/customers/full")

    def list_customers(self, limit: int = 100) -> ApiResponse:
        """
        Get all customers (basic info).

        Args:
            limit: Maximum number of customers to return

        Returns:
            ApiResponse with list of customers
        """
        return self._make_request("GET", f"/api/admin/customers?limit={limit}")

    def get_customers_sync(self) -> ApiResponse:
        """
        Get ALL customers with their API key status (including those without keys).
        Used for syncing Android registrations with desktop app.

        Returns:
            ApiResponse with list of customers including:
            - customer_id, name, email, phone
            - has_api_key, key_id, tier
            - vehicles list
            - registered_via (android/desktop)
        """
        return self._make_request("GET", "/api/admin/customers/sync")

    # -------------------------------------------------
    # HEALTH CHECK
    # -------------------------------------------------

    def check_connection(self) -> bool:
        """
        Check if the server is reachable.

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            response = self._make_request("GET", "/api/admin/api-keys")
            return response.status_code in [200, 401]  # 401 means server is up but auth failed
        except:
            return False

    def get_server_status(self) -> ApiResponse:
        """
        Get server status information.

        Returns:
            ApiResponse with server status
        """
        try:
            # Try to hit the root endpoint
            request = urllib.request.Request(
                f"{self.server_url}/",
                headers={"Accept": "application/json"},
                method="GET"
            )

            with urllib.request.urlopen(request, timeout=5) as response:
                return ApiResponse(
                    success=True,
                    data={"status": "online", "url": self.server_url},
                    status_code=response.status
                )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e),
                status_code=0
            )


# Singleton instance
_client: Optional[ServerAPIClient] = None


def get_server_client(
    server_url: str = DEFAULT_SERVER_URL,
    admin_key: str = ADMIN_KEY
) -> ServerAPIClient:
    """
    Get or create the singleton server API client.

    Args:
        server_url: Server URL (only used on first call)
        admin_key: Admin key (only used on first call)

    Returns:
        ServerAPIClient instance
    """
    global _client
    if _client is None:
        _client = ServerAPIClient(server_url, admin_key)
    return _client


def reset_client():
    """Reset the singleton client (for testing or reconfiguration)."""
    global _client
    _client = None


# -------------------------------------------------
# CONVENIENCE FUNCTIONS
# -------------------------------------------------

def list_api_keys(server_url: str = DEFAULT_SERVER_URL) -> List[Dict[str, Any]]:
    """
    Convenience function to list all API keys.

    Args:
        server_url: Server URL

    Returns:
        List of API keys or empty list on error
    """
    client = get_server_client(server_url)
    response = client.list_api_keys()
    if response.success and response.data:
        return response.data.get('api_keys', [])
    return []


def create_api_key(
    name: str,
    email: str,
    tier: str = "free",
    send_email: bool = True,
    server_url: str = DEFAULT_SERVER_URL
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to create an API key.

    Args:
        name: Customer name
        email: Customer email
        tier: Subscription tier
        send_email: Whether to email the key
        server_url: Server URL

    Returns:
        API key data or None on error
    """
    client = get_server_client(server_url)
    response = client.create_api_key(name, email, tier, send_email=send_email)
    if response.success and response.data:
        return response.data
    return None


def update_api_key(
    key_id: str,
    updates: Dict[str, Any],
    send_notification: bool = True,
    server_url: str = DEFAULT_SERVER_URL
) -> bool:
    """
    Convenience function to update an API key.

    Args:
        key_id: API key identifier
        updates: Dict of fields to update
        send_notification: Whether to send email notification
        server_url: Server URL

    Returns:
        True if successful, False otherwise
    """
    client = get_server_client(server_url)
    response = client.update_api_key(
        key_id,
        tier=updates.get('tier'),
        apps=updates.get('apps'),
        permissions=updates.get('permissions'),
        status=updates.get('status'),
        name=updates.get('name'),
        email=updates.get('email'),
        phone=updates.get('phone'),
        profile_id=updates.get('profile_id'),
        send_notification=send_notification
    )
    return response.success


def regenerate_api_key(
    key_id: str,
    send_email: bool = True,
    server_url: str = DEFAULT_SERVER_URL
) -> Optional[str]:
    """
    Convenience function to regenerate an API key.

    Args:
        key_id: API key identifier
        send_email: Whether to email the new key
        server_url: Server URL

    Returns:
        New API key string or None on error
    """
    client = get_server_client(server_url)
    response = client.regenerate_api_key(key_id, send_email)
    if response.success and response.data:
        return response.data.get('new_api_key')
    return None


def delete_api_key(key_id: str, server_url: str = DEFAULT_SERVER_URL) -> bool:
    """
    Convenience function to delete an API key.

    Args:
        key_id: API key identifier
        server_url: Server URL

    Returns:
        True if successful, False otherwise
    """
    client = get_server_client(server_url)
    response = client.delete_api_key(key_id)
    return response.success


# =============================================================================
# UNIFIED USER MANAGEMENT METHODS
# =============================================================================

class UnifiedUserClient:
    """
    Client for unified user management API.

    This is the new system where server is the single source of truth
    for all API keys, entitlements, and rate limits.
    """

    def __init__(
        self,
        server_url: str = DEFAULT_SERVER_URL,
        admin_key: str = ADMIN_KEY,
        timeout: int = 30
    ):
        self.server_url = server_url.rstrip('/')
        self.admin_key = admin_key
        self.timeout = timeout

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> ApiResponse:
        """Make an HTTP request to the server."""
        url = f"{self.server_url}{endpoint}"

        try:
            headers = {
                "X-Admin-Key": self.admin_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "PREDICT-Desktop/1.0"  # Required for Cloudflare
            }

            body = None
            if data is not None:
                body = json.dumps(data).encode('utf-8')

            request = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method=method
            )

            # Create SSL context for HTTPS
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(request, timeout=self.timeout, context=ssl_context if url.startswith('https') else None) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                return ApiResponse(
                    success=response_data.get('success', True),
                    data=response_data,
                    status_code=response.status
                )

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('detail', {}).get('error', str(e))
            except:
                error_msg = str(e)

            return ApiResponse(
                success=False,
                error=error_msg,
                status_code=e.code
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e),
                status_code=0
            )

    # -------------------------------------------------
    # USER MANAGEMENT
    # -------------------------------------------------

    def list_users(self) -> ApiResponse:
        """
        List all users with full details.

        Returns:
            ApiResponse with list of users including entitlements, limits, API key info
        """
        return self._make_request("GET", "/api/admin/users")

    def create_user(
        self,
        email: str,
        name: str,
        phone: Optional[str] = None,
        role: str = "owner",
        tier: str = "free",
        owner_user_id: Optional[int] = None,
        send_email: bool = True
    ) -> ApiResponse:
        """
        Create a new user with API key.

        Args:
            email: User's email
            name: User's name
            phone: User's phone (optional)
            role: 'owner', 'driver', or 'admin'
            tier: 'free', 'premium', or 'admin'
            owner_user_id: For drivers - their owner's user_id
            send_email: Whether to send welcome email with API key

        Returns:
            ApiResponse with new user details and API key
        """
        data = {
            "email": email,
            "name": name,
            "role": role,
            "tier": tier,
            "send_email": send_email
        }
        if phone:
            data["phone"] = phone
        if owner_user_id:
            data["owner_user_id"] = owner_user_id

        return self._make_request("POST", "/api/admin/users", data)

    def update_user(
        self,
        user_id: int,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        status: Optional[str] = None,
        send_notification: bool = True
    ) -> ApiResponse:
        """
        Update user details.

        Args:
            user_id: User's ID
            name: New name (optional)
            email: New email (optional)
            phone: New phone (optional)
            status: 'active' or 'suspended' (optional)
            send_notification: Send email notification (default: True)

        Returns:
            ApiResponse with update status
        """
        data = {"send_notification": send_notification}
        if name is not None:
            data["name"] = name
        if email is not None:
            data["email"] = email
        if phone is not None:
            data["phone"] = phone
        if status is not None:
            data["status"] = status

        return self._make_request("PUT", f"/api/admin/users/{user_id}", data)

    def delete_user(self, user_id: int) -> ApiResponse:
        """
        Delete (soft-delete) a user.

        Args:
            user_id: User's ID

        Returns:
            ApiResponse with deletion status
        """
        return self._make_request("DELETE", f"/api/admin/users/{user_id}")

    # -------------------------------------------------
    # ENTITLEMENTS
    # -------------------------------------------------

    def set_entitlements(
        self,
        user_id: int,
        entitlements: Dict[str, bool]
    ) -> ApiResponse:
        """
        Set feature entitlements for a user.

        Changes take effect immediately.

        Args:
            user_id: User's ID
            entitlements: Dict of feature -> enabled (e.g., {"llm_chat": True})

        Returns:
            ApiResponse with update status
        """
        return self._make_request(
            "PUT",
            f"/api/admin/users/{user_id}/entitlements",
            {"entitlements": entitlements}
        )

    def set_feature(self, user_id: int, feature: str, enabled: bool) -> ApiResponse:
        """
        Enable or disable a single feature for a user.

        Args:
            user_id: User's ID
            feature: Feature name ('llm_chat', 'predict', etc.)
            enabled: True to enable, False to disable

        Returns:
            ApiResponse with update status
        """
        return self.set_entitlements(user_id, {feature: enabled})

    # -------------------------------------------------
    # RATE LIMITS
    # -------------------------------------------------

    def set_rate_limits(
        self,
        user_id: int,
        limits: Dict[str, Dict[str, Any]]
    ) -> ApiResponse:
        """
        Set rate limits for a user's features.

        Args:
            user_id: User's ID
            limits: Dict of feature -> {max: N, period: 'day'}

        Returns:
            ApiResponse with update status
        """
        return self._make_request(
            "PUT",
            f"/api/admin/users/{user_id}/limits",
            {"limits": limits}
        )

    def set_feature_limit(
        self,
        user_id: int,
        feature: str,
        max_requests: Optional[int],
        period: str = "day"
    ) -> ApiResponse:
        """
        Set rate limit for a single feature.

        Args:
            user_id: User's ID
            feature: Feature name
            max_requests: Max requests allowed (None for unlimited)
            period: 'minute', 'hour', 'day', or 'month'

        Returns:
            ApiResponse with update status
        """
        return self.set_rate_limits(user_id, {
            feature: {"max": max_requests, "period": period}
        })

    # -------------------------------------------------
    # TIER MANAGEMENT
    # -------------------------------------------------

    def apply_tier(self, user_id: int, tier: str) -> ApiResponse:
        """
        Apply a tier preset to a user.

        This sets all entitlements and limits according to the tier.

        Args:
            user_id: User's ID
            tier: 'free', 'premium', or 'admin'

        Returns:
            ApiResponse with tier application status
        """
        return self._make_request("POST", f"/api/admin/users/{user_id}/apply-tier/{tier}")

    # -------------------------------------------------
    # API KEY MANAGEMENT
    # -------------------------------------------------

    def regenerate_key(self, user_id: int, send_email: bool = True) -> ApiResponse:
        """
        Regenerate API key for a user.

        Old key is revoked.

        Args:
            user_id: User's ID
            send_email: Send new key via email (default: True)

        Returns:
            ApiResponse with new API key
        """
        return self._make_request(
            "POST",
            f"/api/admin/users/{user_id}/regenerate-key?send_email={str(send_email).lower()}"
        )

    # -------------------------------------------------
    # USAGE
    # -------------------------------------------------

    def get_usage(self, user_id: int) -> ApiResponse:
        """
        Get current usage statistics for a user.

        Args:
            user_id: User's ID

        Returns:
            ApiResponse with usage stats
        """
        return self._make_request("GET", f"/api/admin/users/{user_id}/usage")

    # -------------------------------------------------
    # DRIVER ASSIGNMENT
    # -------------------------------------------------

    def assign_driver_to_vehicle(
        self,
        driver_user_id: int,
        profile_id: int
    ) -> ApiResponse:
        """
        Assign a driver to a vehicle profile.

        Args:
            driver_user_id: Driver's user ID
            profile_id: Vehicle profile ID

        Returns:
            ApiResponse with assignment status
        """
        return self._make_request(
            "POST",
            f"/api/admin/users/{driver_user_id}/assign-driver",
            {"profile_id": profile_id}
        )


# Singleton instance for unified user client
_unified_client: Optional[UnifiedUserClient] = None


def get_unified_user_client(
    server_url: str = DEFAULT_SERVER_URL,
    admin_key: str = ADMIN_KEY
) -> UnifiedUserClient:
    """
    Get or create the singleton unified user client.

    Args:
        server_url: Server URL (only used on first call)
        admin_key: Admin key (only used on first call)

    Returns:
        UnifiedUserClient instance
    """
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedUserClient(server_url, admin_key)
    return _unified_client
