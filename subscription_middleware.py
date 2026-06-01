"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Subscription Middleware

Subscription Enforcement Middleware
Validates subscriptions and enforces access control on all API endpoints.
"""

import logging
from fastapi import Request, HTTPException
from typing import Optional, Callable

from subscription_manager import get_subscription_manager, SubscriptionStatus
from audit_logger import get_audit_logger, AuditEventType

logger = logging.getLogger(__name__)


class SubscriptionEnforcer:
    """
    Enforces subscription requirements on API endpoints.

    Usage:
        @app.post("/api/endpoint")
        async def endpoint(request: Request):
            # Subscription is automatically validated by middleware
            customer_id = request.state.customer_id
            ...
    """

    def __init__(self):
        self.subscription_manager = get_subscription_manager()
        self.audit_logger = get_audit_logger()

        # Endpoints that don't require subscription
        self.public_endpoints = {
            "/health",
            "/health/ready",
            "/health/live",
            "/api/v1/status",
            "/",
            "/docs",
            "/redoc",
            "/openapi.json"
        }

        # Feature requirements for endpoints
        self.endpoint_features = {
            "/api/live/stream": "live_data",
            "/api/v1/predictions/current": "ai_predictions",
            "/api/service/report/generate": "pdf_reports",
            "/api/profile/update": "api_access",
        }

    async def enforce_subscription(
        self,
        request: Request,
        call_next: Callable
    ):
        """
        Middleware to enforce subscription on all endpoints.

        Attaches customer_id and subscription to request.state for downstream use.
        """
        path = request.url.path

        # Skip public endpoints
        if path in self.public_endpoints or path.startswith("/dashboard/"):
            return await call_next(request)

        # Extract customer_id from API key
        customer_id = await self._get_customer_id_from_request(request)

        if not customer_id:
            # Log access denial
            self.audit_logger.log_event(
                event_type=AuditEventType.ACCESS_DENIED,
                customer_id="unknown",
                details={
                    "reason": "missing_api_key",
                    "path": path,
                    "method": request.method
                }
            )

            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Authentication required",
                    "message": "Missing or invalid API key"
                }
            )

        # Validate subscription
        required_feature = self.endpoint_features.get(path)
        is_valid, reason, subscription = self.subscription_manager.validate_subscription(
            customer_id,
            required_feature
        )

        if not is_valid:
            # Log access denial
            self.audit_logger.log_event(
                event_type=AuditEventType.ACCESS_DENIED,
                customer_id=customer_id,
                details={
                    "reason": reason,
                    "path": path,
                    "method": request.method,
                    "required_feature": required_feature
                }
            )

            # Return appropriate error based on reason
            if "expired" in reason.lower() or "not active" in reason.lower():
                status_code = 402  # Payment Required
                error_type = "subscription_expired"
                message = "Your subscription has expired. Please renew to continue using this service."
            elif "feature" in reason.lower():
                status_code = 403  # Forbidden
                error_type = "feature_not_available"
                message = f"This feature is not included in your plan. {reason}"
            else:
                status_code = 403  # Forbidden
                error_type = "subscription_invalid"
                message = f"Subscription validation failed: {reason}"

            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": error_type,
                    "message": message,
                    "subscription_status": subscription.status if subscription else "unknown"
                }
            )

        # Attach customer_id and subscription to request
        request.state.customer_id = customer_id
        request.state.subscription = subscription

        # Log successful access
        self.audit_logger.log_event(
            event_type=AuditEventType.API_ACCESS,
            customer_id=customer_id,
            details={
                "path": path,
                "method": request.method,
                "subscription_plan": subscription.plan,
                "feature_checked": required_feature
            }
        )

        # Continue processing request
        return await call_next(request)

    async def _get_customer_id_from_request(self, request: Request) -> Optional[str]:
        """
        Extract customer_id from API key in request.

        Checks:
        1. X-API-Key header
        2. Authorization header (Bearer token)
        """
        import json
        import hashlib
        from pathlib import Path

        # Try X-API-Key header first
        api_key = request.headers.get("X-API-Key")

        # Try Authorization header
        if not api_key:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header.replace("Bearer ", "").strip()

        if not api_key:
            return None

        # Look up customer_id from API key
        try:
            from config import get_config
            config = get_config()
            api_keys_file = config.API_KEYS_FILE

            if not api_keys_file.exists():
                logger.warning("API keys file not found")
                return None

            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)

            # Hash the provided API key
            key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

            # Find matching customer
            for key_id, key_data in api_keys.items():
                if key_data.get("key_hash") == key_hash:
                    customer_id = key_data.get("customer_id")
                    if not customer_id:
                        # Fallback: use profile_id as customer_id (migration support)
                        customer_id = str(key_data.get("profile_id", ""))
                    return customer_id

            return None

        except Exception as e:
            logger.error(f"Error looking up customer from API key: {e}")
            return None

    def check_feature_access(
        self,
        request: Request,
        required_feature: str
    ) -> bool:
        """
        Check if request has access to a specific feature.

        Use this in endpoint handlers for fine-grained feature control.
        """
        subscription = getattr(request.state, "subscription", None)

        if not subscription:
            return False

        return subscription.has_feature(required_feature)


# Global enforcer instance
_enforcer: Optional[SubscriptionEnforcer] = None


def get_subscription_enforcer() -> SubscriptionEnforcer:
    """Get global subscription enforcer instance"""
    global _enforcer
    if _enforcer is None:
        _enforcer = SubscriptionEnforcer()
    return _enforcer


def require_feature(feature: str):
    """
    Decorator to require a specific feature for an endpoint.

    Usage:
        @app.post("/api/premium-endpoint")
        @require_feature("premium_feature")
        async def premium_endpoint(request: Request):
            ...
    """
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            enforcer = get_subscription_enforcer()

            if not enforcer.check_feature_access(request, feature):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "feature_not_available",
                        "message": f"Feature '{feature}' not included in your plan"
                    }
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
