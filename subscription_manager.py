"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Subscription Manager

Predict OBD - Subscription Management System
Handles subscription lifecycle, validation, and enforcement.

SUBSCRIPTION MODEL (Hybrid):
- Manual customer creation by operator
- Manual initial subscription creation
- Automatic renewal when payment succeeds
- Failed payments → expired status
- No self-signup or automatic provisioning
- Offline license validation supported
"""

import json
import hashlib
import secrets
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass, asdict

from config import get_config

logger = logging.getLogger(__name__)


class SubscriptionStatus(Enum):
    """Subscription status states"""
    PENDING = "pending"              # Created but not activated
    ACTIVE = "active"                # Currently valid
    EXPIRED = "expired"              # Past end date or payment failed
    SUSPENDED = "suspended"          # Manually suspended
    CANCELLED = "cancelled"          # User requested cancellation
    TRIAL = "trial"                  # Trial period


class SubscriptionPlan(Enum):
    """Available subscription plans"""
    TRIAL = "trial"                  # 14-day trial
    BASIC = "basic"                  # Basic features
    PREMIUM = "premium"              # All features
    ENTERPRISE = "enterprise"        # Enterprise support


@dataclass
class Subscription:
    """Subscription data model"""
    subscription_id: str
    customer_id: str
    plan: str                        # SubscriptionPlan value
    status: str                      # SubscriptionStatus value
    created_at: str                  # ISO timestamp
    start_date: Optional[str] = None  # ISO date
    end_date: Optional[str] = None    # ISO date
    auto_renew: bool = True
    payment_status: str = "pending"  # pending, succeeded, failed
    license_key: Optional[str] = None  # For offline validation
    features: Dict[str, bool] = None  # Feature flags
    metadata: Dict[str, Any] = None   # Custom data
    audit_log: List[Dict[str, Any]] = None  # Audit trail

    def __post_init__(self):
        if self.features is None:
            self.features = self._get_plan_features(self.plan)
        if self.metadata is None:
            self.metadata = {}
        if self.audit_log is None:
            self.audit_log = []

    @staticmethod
    def _get_plan_features(plan: str) -> Dict[str, bool]:
        """Get default features for a plan"""
        features = {
            "live_data": False,
            "ai_predictions": False,
            "pdf_reports": False,
            "unlimited_vehicles": False,
            "api_access": False,
            "premium_support": False,
            "data_export": False,
            "multi_user": False,
        }

        if plan == SubscriptionPlan.TRIAL.value:
            features.update({
                "live_data": True,
                "ai_predictions": True,
                "pdf_reports": True,
            })
        elif plan == SubscriptionPlan.BASIC.value:
            features.update({
                "live_data": True,
                "pdf_reports": True,
                "data_export": True,
            })
        elif plan == SubscriptionPlan.PREMIUM.value:
            features.update({
                "live_data": True,
                "ai_predictions": True,
                "pdf_reports": True,
                "unlimited_vehicles": True,
                "api_access": True,
                "data_export": True,
            })
        elif plan == SubscriptionPlan.ENTERPRISE.value:
            features.update({k: True for k in features})  # All features

        return features

    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        if self.status != SubscriptionStatus.ACTIVE.value:
            return False

        if self.end_date:
            end = datetime.fromisoformat(self.end_date)
            if datetime.now() > end:
                return False

        return True

    def has_feature(self, feature: str) -> bool:
        """Check if subscription includes a feature"""
        return self.features.get(feature, False)

    def days_remaining(self) -> Optional[int]:
        """Get days remaining in subscription"""
        if not self.end_date:
            return None

        end = datetime.fromisoformat(self.end_date)
        remaining = (end - datetime.now()).days
        return max(0, remaining)

    def add_audit_entry(self, event_type: str, details: Dict[str, Any], actor: str = "system"):
        """Add audit log entry"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "actor": actor,
            "details": details
        }
        self.audit_log.append(entry)


class SubscriptionManager:
    """
    Manages subscription lifecycle and validation.

    Features:
    - Manual customer and subscription creation
    - Automatic renewal handling
    - Offline license validation
    - Audit logging
    - Feature flag enforcement
    """

    def __init__(self):
        self.config = get_config()
        self._subscription_cache: Dict[str, Subscription] = {}

    def _get_subscription_file(self, customer_id: str) -> Path:
        """Get path to customer's subscription file"""
        return self.config.get_customer_subscription(customer_id)

    def create_subscription(
        self,
        customer_id: str,
        plan: SubscriptionPlan,
        duration_days: int = 30,
        start_immediately: bool = False,
        created_by: str = "operator"
    ) -> Tuple[bool, str, Optional[Subscription]]:
        """
        Manually create a subscription (operator action).

        Args:
            customer_id: Customer identifier
            plan: Subscription plan
            duration_days: Subscription duration
            start_immediately: Activate immediately
            created_by: Operator who created this

        Returns:
            (success, message, subscription_object)
        """
        try:
            # Check if customer directory exists
            customer_dir = self.config.get_customer_dir(customer_id)
            if not customer_dir.exists():
                return False, f"Customer {customer_id} does not exist", None

            # Check if subscription already exists
            sub_file = self._get_subscription_file(customer_id)
            if sub_file.exists():
                # Load existing subscription
                existing = self.load_subscription(customer_id)
                if existing and existing.is_active():
                    return False, f"Customer {customer_id} already has active subscription", None

            # Generate subscription ID and license key
            subscription_id = self._generate_subscription_id(customer_id)
            license_key = self._generate_license_key(customer_id, plan.value)

            # Calculate dates
            now = datetime.now()
            if start_immediately:
                start_date = now.date().isoformat()
                end_date = (now + timedelta(days=duration_days)).date().isoformat()
                status = SubscriptionStatus.ACTIVE
                payment_status = "succeeded"  # Manual creation = immediate payment
            else:
                start_date = None
                end_date = None
                status = SubscriptionStatus.PENDING
                payment_status = "pending"

            # Create subscription object
            subscription = Subscription(
                subscription_id=subscription_id,
                customer_id=customer_id,
                plan=plan.value,
                status=status.value,
                created_at=now.isoformat(),
                start_date=start_date,
                end_date=end_date,
                auto_renew=True,
                payment_status=payment_status,
                license_key=license_key
            )

            # Add audit entry
            subscription.add_audit_entry(
                event_type="subscription_created",
                details={
                    "plan": plan.value,
                    "duration_days": duration_days,
                    "start_immediately": start_immediately
                },
                actor=created_by
            )

            # Save subscription
            self._save_subscription(subscription)

            logger.info(f"Subscription created: {subscription_id} for customer {customer_id}")

            return True, f"Subscription created successfully", subscription

        except Exception as e:
            logger.error(f"Failed to create subscription for {customer_id}: {e}")
            return False, f"Failed to create subscription: {str(e)}", None

    def activate_subscription(
        self,
        customer_id: str,
        payment_confirmation: Optional[str] = None,
        activated_by: str = "operator"
    ) -> Tuple[bool, str]:
        """
        Activate a pending subscription (manual operator action).

        Args:
            customer_id: Customer identifier
            payment_confirmation: Payment confirmation code
            activated_by: Operator who activated

        Returns:
            (success, message)
        """
        try:
            subscription = self.load_subscription(customer_id)
            if not subscription:
                return False, f"No subscription found for customer {customer_id}"

            if subscription.status != SubscriptionStatus.PENDING.value:
                return False, f"Subscription is not pending (status: {subscription.status})"

            # Calculate dates based on plan
            duration_days = 30  # Default
            if subscription.plan == SubscriptionPlan.TRIAL.value:
                duration_days = 14
            elif subscription.plan == SubscriptionPlan.BASIC.value:
                duration_days = 30
            elif subscription.plan in [SubscriptionPlan.PREMIUM.value, SubscriptionPlan.ENTERPRISE.value]:
                duration_days = 30

            now = datetime.now()
            subscription.start_date = now.date().isoformat()
            subscription.end_date = (now + timedelta(days=duration_days)).date().isoformat()
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.payment_status = "succeeded"

            # Add audit entry
            subscription.add_audit_entry(
                event_type="subscription_activated",
                details={
                    "payment_confirmation": payment_confirmation,
                    "start_date": subscription.start_date,
                    "end_date": subscription.end_date
                },
                actor=activated_by
            )

            # Save subscription
            self._save_subscription(subscription)

            logger.info(f"Subscription activated: {subscription.subscription_id}")

            return True, "Subscription activated successfully"

        except Exception as e:
            logger.error(f"Failed to activate subscription for {customer_id}: {e}")
            return False, f"Failed to activate subscription: {str(e)}"

    def renew_subscription(
        self,
        customer_id: str,
        payment_succeeded: bool,
        payment_details: Optional[Dict[str, Any]] = None,
        renewed_by: str = "system"
    ) -> Tuple[bool, str]:
        """
        Renew subscription automatically or manually.

        Args:
            customer_id: Customer identifier
            payment_succeeded: Whether payment succeeded
            payment_details: Payment transaction details
            renewed_by: Who triggered renewal

        Returns:
            (success, message)
        """
        try:
            subscription = self.load_subscription(customer_id)
            if not subscription:
                return False, f"No subscription found for customer {customer_id}"

            if payment_succeeded:
                # Extend subscription
                if subscription.end_date:
                    end = datetime.fromisoformat(subscription.end_date)
                    new_end = end + timedelta(days=30)
                else:
                    new_end = datetime.now() + timedelta(days=30)

                subscription.end_date = new_end.date().isoformat()
                subscription.status = SubscriptionStatus.ACTIVE.value
                subscription.payment_status = "succeeded"

                # Audit log
                subscription.add_audit_entry(
                    event_type="subscription_renewed",
                    details={
                        "new_end_date": subscription.end_date,
                        "payment_details": payment_details or {}
                    },
                    actor=renewed_by
                )

                logger.info(f"Subscription renewed: {subscription.subscription_id}")
                message = "Subscription renewed successfully"
            else:
                # Payment failed - mark as expired
                subscription.status = SubscriptionStatus.EXPIRED.value
                subscription.payment_status = "failed"

                # Audit log
                subscription.add_audit_entry(
                    event_type="renewal_failed",
                    details={
                        "reason": "payment_failed",
                        "payment_details": payment_details or {}
                    },
                    actor=renewed_by
                )

                logger.warning(f"Subscription renewal failed: {subscription.subscription_id}")
                message = "Subscription expired due to payment failure"

            # Save subscription
            self._save_subscription(subscription)

            return True, message

        except Exception as e:
            logger.error(f"Failed to renew subscription for {customer_id}: {e}")
            return False, f"Failed to renew subscription: {str(e)}"

    def validate_subscription(
        self,
        customer_id: str,
        required_feature: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Subscription]]:
        """
        Validate customer's subscription status.

        Args:
            customer_id: Customer identifier
            required_feature: Optional feature to check

        Returns:
            (is_valid, reason_if_invalid, subscription_object)
        """
        try:
            subscription = self.load_subscription(customer_id)

            if not subscription:
                return False, "No subscription found", None

            if not subscription.is_active():
                return False, f"Subscription not active (status: {subscription.status})", subscription

            if required_feature:
                if not subscription.has_feature(required_feature):
                    return False, f"Feature '{required_feature}' not included in plan", subscription

            return True, None, subscription

        except Exception as e:
            logger.error(f"Subscription validation error for {customer_id}: {e}")
            return False, f"Validation error: {str(e)}", None

    def validate_offline_license(
        self,
        license_key: str,
        customer_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate offline license key.

        Args:
            license_key: License key to validate
            customer_id: Customer identifier

        Returns:
            (is_valid, reason_if_invalid)
        """
        try:
            subscription = self.load_subscription(customer_id)

            if not subscription:
                return False, "No subscription found"

            if subscription.license_key != license_key:
                return False, "Invalid license key"

            # Check if subscription is active
            if not subscription.is_active():
                return False, f"License expired or inactive (status: {subscription.status})"

            return True, None

        except Exception as e:
            logger.error(f"License validation error: {e}")
            return False, f"Validation error: {str(e)}"

    def get_subscription_info(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription information for display"""
        subscription = self.load_subscription(customer_id)
        if not subscription:
            return None

        return {
            "subscription_id": subscription.subscription_id,
            "customer_id": subscription.customer_id,
            "plan": subscription.plan,
            "status": subscription.status,
            "is_active": subscription.is_active(),
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "days_remaining": subscription.days_remaining(),
            "auto_renew": subscription.auto_renew,
            "payment_status": subscription.payment_status,
            "license_key": subscription.license_key,
            "features": subscription.features
        }

    def get_audit_log(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get subscription audit log"""
        subscription = self.load_subscription(customer_id)
        if not subscription:
            return []

        return subscription.audit_log

    def load_subscription(self, customer_id: str) -> Optional[Subscription]:
        """Load subscription from file"""
        # Check cache first
        if customer_id in self._subscription_cache:
            return self._subscription_cache[customer_id]

        sub_file = self._get_subscription_file(customer_id)
        if not sub_file.exists():
            return None

        try:
            with open(sub_file, 'r') as f:
                data = json.load(f)

            subscription = Subscription(**data)

            # Cache it
            self._subscription_cache[customer_id] = subscription

            return subscription

        except Exception as e:
            logger.error(f"Failed to load subscription for {customer_id}: {e}")
            return None

    def _save_subscription(self, subscription: Subscription):
        """Save subscription to file"""
        sub_file = self._get_subscription_file(subscription.customer_id)
        sub_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(sub_file, 'w') as f:
                json.dump(asdict(subscription), f, indent=2)

            # Update cache
            self._subscription_cache[subscription.customer_id] = subscription

        except Exception as e:
            logger.error(f"Failed to save subscription: {e}")
            raise

    def _generate_subscription_id(self, customer_id: str) -> str:
        """Generate unique subscription ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = secrets.token_hex(4)
        return f"sub_{customer_id}_{timestamp}_{random_suffix}"

    def _generate_license_key(self, customer_id: str, plan: str) -> str:
        """Generate offline license key"""
        # Create deterministic but secure license key
        data = f"{customer_id}:{plan}:{secrets.token_hex(16)}"
        hash_obj = hashlib.sha256(data.encode())
        license_hash = hash_obj.hexdigest()[:32].upper()

        # Format as XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
        parts = [license_hash[i:i+4] for i in range(0, len(license_hash), 4)]
        return "-".join(parts)

    def expire_subscription(
        self,
        customer_id: str,
        reason: str = "manual_expiration",
        expired_by: str = "operator"
    ) -> Tuple[bool, str]:
        """Manually expire a subscription"""
        try:
            subscription = self.load_subscription(customer_id)
            if not subscription:
                return False, f"No subscription found for customer {customer_id}"

            subscription.status = SubscriptionStatus.EXPIRED.value

            # Add audit entry
            subscription.add_audit_entry(
                event_type="subscription_expired",
                details={"reason": reason},
                actor=expired_by
            )

            # Save subscription
            self._save_subscription(subscription)

            logger.info(f"Subscription expired: {subscription.subscription_id}")

            return True, "Subscription expired successfully"

        except Exception as e:
            logger.error(f"Failed to expire subscription for {customer_id}: {e}")
            return False, f"Failed to expire subscription: {str(e)}"

    def cancel_subscription(
        self,
        customer_id: str,
        reason: str = "customer_request",
        cancelled_by: str = "customer"
    ) -> Tuple[bool, str]:
        """Cancel a subscription (customer or operator request)"""
        try:
            subscription = self.load_subscription(customer_id)
            if not subscription:
                return False, f"No subscription found for customer {customer_id}"

            subscription.status = SubscriptionStatus.CANCELLED.value
            subscription.auto_renew = False

            # Add audit entry
            subscription.add_audit_entry(
                event_type="subscription_cancelled",
                details={"reason": reason},
                actor=cancelled_by
            )

            # Save subscription
            self._save_subscription(subscription)

            logger.info(f"Subscription cancelled: {subscription.subscription_id}")

            return True, "Subscription cancelled successfully"

        except Exception as e:
            logger.error(f"Failed to cancel subscription for {customer_id}: {e}")
            return False, f"Failed to cancel subscription: {str(e)}"


# ==================== MODULE-LEVEL FUNCTIONS ====================

_subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    """Get global subscription manager instance"""
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager()
    return _subscription_manager


def validate_subscription(customer_id: str, required_feature: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Convenience function for subscription validation"""
    manager = get_subscription_manager()
    is_valid, reason, _ = manager.validate_subscription(customer_id, required_feature)
    return is_valid, reason


def validate_license(license_key: str, customer_id: str) -> Tuple[bool, Optional[str]]:
    """Convenience function for offline license validation"""
    manager = get_subscription_manager()
    return manager.validate_offline_license(license_key, customer_id)


# ==================== API KEY GENERATION ====================

def generate_api_key_for_subscription(
    customer_id: str,
    plan: str,
    profile_id: Optional[int] = None,
    profile_name: str = "Default"
) -> str:
    """
    Generate an API key for a subscription.

    Maps subscription plans to API key tiers:
    - trial -> Free tier (F_xxxxx)
    - basic -> Free tier (F_xxxxx)
    - professional -> Premium tier (P_xxxxx)
    - enterprise -> Premium tier (P_xxxxx)

    Args:
        customer_id: Customer identifier
        plan: Subscription plan
        profile_id: Vehicle profile ID (optional)
        profile_name: Vehicle profile name

    Returns:
        Generated API key
    """
    import secrets
    import hashlib
    from server_tab_v2 import ApiKeyTier, SimpleEncryption

    # Map plan to API tier
    plan_to_tier = {
        "trial": "free",
        "basic": "free",
        "professional": "premium",
        "premium": "premium",
        "enterprise": "premium"
    }

    tier = plan_to_tier.get(plan.lower(), "free")

    # Generate API key
    api_key = ApiKeyTier.generate_key(tier)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Get config for paths
    try:
        config = get_config()
        api_keys_file = str(config.API_KEYS_FILE)
    except:
        api_keys_file = "config/api_keys.json"

    # Load existing keys
    import os
    import json
    from datetime import datetime

    api_keys = {}
    if os.path.exists(api_keys_file):
        with open(api_keys_file, 'r') as f:
            api_keys = json.load(f)

    # Create unique key identifier
    key_id = f"key_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"

    # Encrypt the key for storage
    admin_password = "YOUR_ADMIN_PASSWORD"  # Admin password
    key_encrypted = SimpleEncryption.encrypt(api_key, admin_password)

    # Get tier info
    tier_info = ApiKeyTier.get_tier_info(tier)

    # Add new key
    api_keys[key_id] = {
        "key_hash": key_hash,
        "key_encrypted": key_encrypted,
        "key_hidden": f"{tier_info['prefix']}{'•' * (tier_info['key_length'] - len(tier_info['prefix']))}",
        "name": f"{customer_id} - {plan.capitalize()} Subscription",
        "tier": tier,
        "profile_id": profile_id,
        "profile_name": profile_name,
        "permissions": tier_info["permissions"],
        "created": datetime.now().isoformat(),
        "status": "active",
        "customer_id": customer_id,
        "subscription_plan": plan
    }

    # Save keys
    os.makedirs(os.path.dirname(api_keys_file), exist_ok=True)
    with open(api_keys_file, 'w') as f:
        json.dump(api_keys, f, indent=2)

    # Auto-sync to server
    try:
        from api_key_sync import sync_single_key_to_server
        sync_single_key_to_server(key_id, api_keys[key_id])
        logger.info(f"API key auto-synced to server: {key_id}")
    except Exception as sync_error:
        logger.warning(f"Failed to auto-sync API key to server: {sync_error}")

    # Save backup file
    try:
        if config:
            keys_folder = str(config.get_customer_api_keys_dir(customer_id))
        else:
            keys_folder = f"API_KEYS/{customer_id}"

        os.makedirs(keys_folder, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        key_filename = os.path.join(keys_folder, f"{customer_id}_{plan}_{timestamp}_apikey.txt")

        with open(key_filename, 'w') as f:
            f.write("╔════════════════════════════════════════════════════════════╗\n")
            f.write("║         PREDICT OBD - API KEY CREDENTIALS                    ║\n")
            f.write("╚════════════════════════════════════════════════════════════╝\n\n")
            f.write(f"Customer:    {customer_id}\n")
            f.write(f"Plan:        {plan.upper()}\n")
            f.write(f"Tier:        {tier.upper()}\n")
            f.write(f"Profile:     {profile_name}\n")
            f.write(f"Generated:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("─" * 64 + "\n")
            f.write("API KEY (keep this secret!):\n")
            f.write("─" * 64 + "\n")
            f.write(f"{api_key}\n")
            f.write("─" * 64 + "\n\n")
            f.write("SETUP INSTRUCTIONS:\n")
            f.write("1. Open Predict OBD Android app\n")
            f.write("2. Go to Settings → Server Connection\n")
            f.write("3. Enter Server IP and Port 8000\n")
            f.write("4. Paste this API key\n")
            f.write("5. Save and enjoy!\n")
    except Exception as e:
        logger.warning(f"Could not save API key backup file: {e}")

    logger.info(f"Generated API key for customer {customer_id}, plan {plan}, tier {tier}")

    return api_key
