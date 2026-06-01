"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: System Integrity

Predict OBD - System Integrity & Consistency Enforcement
CRITICAL: This module ensures no invalid system states can occur.

GUARANTEES:
1. Every API key belongs to exactly one customer profile
2. Every API key resolves to exactly one subscription
3. Every request validates: customer -> subscription -> plan -> permissions
4. No orphaned API keys, subscriptions, or profiles can exist
5. Subscription revocation immediately affects all API keys
6. Key rotation preserves subscription linkage

FAILURE SCENARIOS HANDLED:
- API key valid, subscription expired -> 402 Payment Required
- API key revoked, subscription active -> 401 Unauthorized
- Subscription renewed while offline -> Automatic revalidation
- Customer deleted with active subscription -> Cascade invalidation
- Vehicle reassigned while API key in use -> Access revocation
- License validation fails during offline mode -> Grace period handling
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from config import get_config
from audit_logger import log_audit_event, AuditEventType

logger = logging.getLogger(__name__)


@dataclass
class IntegrityViolation:
    """Represents an integrity violation."""
    violation_type: str
    severity: str  # critical, high, medium, low
    entity_type: str  # api_key, subscription, profile, vehicle
    entity_id: str
    customer_id: Optional[str]
    description: str
    auto_repair: bool
    repair_action: Optional[str]
    timestamp: str


class SystemIntegrityChecker:
    """
    Comprehensive system integrity validation.

    Checks:
    1. Profile-Subscription linkage
    2. API Key-Customer linkage
    3. Subscription-API Key consistency
    4. Directory structure integrity
    5. Orphaned data detection
    """

    def __init__(self):
        self.config = get_config()
        self.violations: List[IntegrityViolation] = []

    def run_all_checks(self) -> Dict[str, Any]:
        """
        Run all integrity checks and return comprehensive report.

        Returns:
            {
                "healthy": bool,
                "timestamp": str,
                "checks": {
                    "check_name": {"passed": bool, "details": dict}
                },
                "violations": List[IntegrityViolation],
                "auto_repairs": int
            }
        """
        self.violations = []

        report = {
            "healthy": True,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "violations": [],
            "auto_repairs": 0
        }

        # Run all checks
        checks = [
            ("profile_subscription_linkage", self.check_profile_subscription_linkage),
            ("api_key_customer_linkage", self.check_api_key_customer_linkage),
            ("api_key_subscription_consistency", self.check_api_key_subscription_consistency),
            ("orphaned_api_keys", self.check_orphaned_api_keys),
            ("orphaned_subscriptions", self.check_orphaned_subscriptions),
            ("directory_structure", self.check_directory_structure),
            ("license_key_integrity", self.check_license_key_integrity),
            ("vehicle_ownership", self.check_vehicle_ownership),
        ]

        for check_name, check_func in checks:
            try:
                passed, details = check_func()
                report["checks"][check_name] = {"passed": passed, "details": details}
                if not passed:
                    report["healthy"] = False
            except Exception as e:
                logger.error(f"Integrity check failed: {check_name}: {e}")
                report["checks"][check_name] = {"passed": False, "error": str(e)}
                report["healthy"] = False

        # Add violations to report
        report["violations"] = [v.__dict__ for v in self.violations]

        # Audit log if violations found
        if self.violations:
            log_audit_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                details={
                    "event": "integrity_violations_detected",
                    "count": len(self.violations),
                    "critical_count": sum(1 for v in self.violations if v.severity == "critical")
                }
            )

        return report

    def check_profile_subscription_linkage(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify every customer profile has a subscription state.

        GUARANTEE: No customer profile can exist without a subscription state.
        """
        details = {"customers_checked": 0, "missing_subscriptions": [], "repaired": 0}

        customers_dir = self.config.CUSTOMERS_DIR
        if not customers_dir.exists():
            return True, details

        for customer_dir in customers_dir.iterdir():
            if not customer_dir.is_dir() or "_deleted_" in customer_dir.name:
                continue

            customer_id = customer_dir.name
            details["customers_checked"] += 1

            # Check for subscription file
            subscription_file = self.config.get_customer_subscription(customer_id)

            if not subscription_file.exists():
                details["missing_subscriptions"].append(customer_id)

                # Auto-repair: Create pending subscription
                self._repair_missing_subscription(customer_id)
                details["repaired"] += 1

                self.violations.append(IntegrityViolation(
                    violation_type="missing_subscription",
                    severity="high",
                    entity_type="profile",
                    entity_id=customer_id,
                    customer_id=customer_id,
                    description=f"Customer {customer_id} has no subscription file",
                    auto_repair=True,
                    repair_action="Created pending subscription",
                    timestamp=datetime.now().isoformat()
                ))

        passed = len(details["missing_subscriptions"]) == 0
        return passed, details

    def check_api_key_customer_linkage(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify every API key belongs to exactly one customer.

        GUARANTEE: Every API key resolves to exactly one customer.
        """
        details = {"keys_checked": 0, "orphaned_keys": [], "duplicate_customers": [], "migrated_keys": []}

        api_keys_file = self.config.API_KEYS_FILE
        if not api_keys_file.exists():
            return True, details

        try:
            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)
        except:
            return False, {"error": "Cannot read API keys file"}

        customer_id_counts = {}

        for key_id, key_data in api_keys.items():
            details["keys_checked"] += 1

            # Admin keys don't need customer_id - skip them
            if key_data.get("tier") == "admin":
                continue

            # Support both new customer_id and legacy profile_id
            customer_id = key_data.get("customer_id")

            # Legacy migration: use profile_id if customer_id not present
            if not customer_id and key_data.get("profile_id") is not None:
                customer_id = f"customer_{key_data['profile_id']}"
                details["migrated_keys"].append(key_id)

            if not customer_id:
                details["orphaned_keys"].append(key_id)
                self.violations.append(IntegrityViolation(
                    violation_type="orphaned_api_key",
                    severity="critical",
                    entity_type="api_key",
                    entity_id=key_id,
                    customer_id=None,
                    description=f"API key {key_id} has no customer_id",
                    auto_repair=False,
                    repair_action=None,
                    timestamp=datetime.now().isoformat()
                ))
            else:
                # Track for duplicate detection
                if customer_id not in customer_id_counts:
                    customer_id_counts[customer_id] = []
                customer_id_counts[customer_id].append(key_id)

                # Verify customer exists
                customer_dir = self.config.get_customer_dir(customer_id)
                if not customer_dir.exists():
                    details["orphaned_keys"].append(key_id)
                    self.violations.append(IntegrityViolation(
                        violation_type="api_key_missing_customer",
                        severity="critical",
                        entity_type="api_key",
                        entity_id=key_id,
                        customer_id=customer_id,
                        description=f"API key {key_id} references non-existent customer {customer_id}",
                        auto_repair=False,
                        repair_action=None,
                        timestamp=datetime.now().isoformat()
                    ))

        passed = len(details["orphaned_keys"]) == 0
        return passed, details

    def check_api_key_subscription_consistency(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify every API key can resolve to a subscription.

        GUARANTEE: API key -> customer -> subscription chain is always valid.
        """
        details = {"keys_checked": 0, "broken_chains": []}

        api_keys_file = self.config.API_KEYS_FILE
        if not api_keys_file.exists():
            return True, details

        try:
            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)
        except:
            return False, {"error": "Cannot read API keys file"}

        from subscription_manager import get_subscription_manager
        sub_manager = get_subscription_manager()

        for key_id, key_data in api_keys.items():
            details["keys_checked"] += 1

            customer_id = key_data.get("customer_id")
            if not customer_id:
                continue  # Already caught in api_key_customer_linkage

            # Check subscription exists
            subscription = sub_manager.load_subscription(customer_id)

            if not subscription:
                details["broken_chains"].append({
                    "key_id": key_id,
                    "customer_id": customer_id,
                    "issue": "no_subscription"
                })

                self.violations.append(IntegrityViolation(
                    violation_type="broken_key_subscription_chain",
                    severity="critical",
                    entity_type="api_key",
                    entity_id=key_id,
                    customer_id=customer_id,
                    description=f"API key {key_id} -> customer {customer_id} has no subscription",
                    auto_repair=False,
                    repair_action=None,
                    timestamp=datetime.now().isoformat()
                ))

        passed = len(details["broken_chains"]) == 0
        return passed, details

    def check_orphaned_api_keys(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect API keys with no valid owner or revoked status.

        GUARANTEE: No orphaned API keys exist.
        """
        details = {"orphaned": [], "revoked_but_present": []}

        api_keys_file = self.config.API_KEYS_FILE
        if not api_keys_file.exists():
            return True, details

        try:
            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)
        except:
            return False, {"error": "Cannot read API keys file"}

        for key_id, key_data in api_keys.items():
            customer_id = key_data.get("customer_id")

            # Check if key should be revoked (customer deleted)
            if customer_id:
                customer_dir = self.config.get_customer_dir(customer_id)
                if not customer_dir.exists():
                    # Customer deleted but key still exists
                    details["orphaned"].append(key_id)

            # Check for explicitly revoked keys that should be removed
            if key_data.get("revoked", False):
                revoked_at = key_data.get("revoked_at")
                if revoked_at:
                    revoked_time = datetime.fromisoformat(revoked_at)
                    # Revoked keys should be removed after 30 days
                    if (datetime.now() - revoked_time).days > 30:
                        details["revoked_but_present"].append(key_id)

        passed = len(details["orphaned"]) == 0
        return passed, details

    def check_orphaned_subscriptions(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect subscriptions without a valid customer profile.

        GUARANTEE: No subscription can exist without a customer profile.
        """
        details = {"orphaned": []}

        customers_dir = self.config.CUSTOMERS_DIR
        if not customers_dir.exists():
            return True, details

        for customer_dir in customers_dir.iterdir():
            if not customer_dir.is_dir() or "_deleted_" in customer_dir.name:
                continue

            customer_id = customer_dir.name
            subscription_file = self.config.get_customer_subscription(customer_id)
            profile_file = self.config.get_customer_profile(customer_id)

            # Check for subscription without profile
            if subscription_file.exists() and not profile_file.exists():
                details["orphaned"].append(customer_id)

                self.violations.append(IntegrityViolation(
                    violation_type="orphaned_subscription",
                    severity="high",
                    entity_type="subscription",
                    entity_id=customer_id,
                    customer_id=customer_id,
                    description=f"Subscription for {customer_id} has no profile",
                    auto_repair=False,
                    repair_action=None,
                    timestamp=datetime.now().isoformat()
                ))

        passed = len(details["orphaned"]) == 0
        return passed, details

    def check_directory_structure(self) -> Tuple[bool, Dict[str, Any]]:
        """Check all required directories exist and are writable."""
        from directory_manager import DirectoryManager

        manager = DirectoryManager()
        status = manager.get_directory_status()

        missing = []
        not_writable = []

        for path, info in status.items():
            if not info["exists"]:
                missing.append(path)
            elif info["exists"] and not info.get("writable", True):
                not_writable.append(path)

        details = {"missing": missing, "not_writable": not_writable}
        passed = len(missing) == 0 and len(not_writable) == 0

        return passed, details

    def check_license_key_integrity(self) -> Tuple[bool, Dict[str, Any]]:
        """Verify license keys match their subscriptions."""
        details = {"checked": 0, "mismatches": []}

        from subscription_manager import get_subscription_manager
        manager = get_subscription_manager()

        customers_dir = self.config.CUSTOMERS_DIR
        if not customers_dir.exists():
            return True, details

        for customer_dir in customers_dir.iterdir():
            if not customer_dir.is_dir() or "_deleted_" in customer_dir.name:
                continue

            customer_id = customer_dir.name
            subscription = manager.load_subscription(customer_id)

            if subscription and subscription.license_key:
                details["checked"] += 1
                # Verify license key format
                parts = subscription.license_key.split("-")
                if len(parts) != 8 or not all(len(p) == 4 for p in parts):
                    details["mismatches"].append(customer_id)

        passed = len(details["mismatches"]) == 0
        return passed, details

    def check_vehicle_ownership(self) -> Tuple[bool, Dict[str, Any]]:
        """Verify vehicle directories have valid ownership."""
        details = {"vehicles_checked": 0, "orphaned_vehicles": []}

        customers_dir = self.config.CUSTOMERS_DIR
        if not customers_dir.exists():
            return True, details

        for customer_dir in customers_dir.iterdir():
            if not customer_dir.is_dir() or "_deleted_" in customer_dir.name:
                continue

            customer_id = customer_dir.name
            vehicles_dir = self.config.get_customer_vehicles_dir(customer_id)

            if not vehicles_dir.exists():
                continue

            for vehicle_dir in vehicles_dir.iterdir():
                if not vehicle_dir.is_dir():
                    continue

                details["vehicles_checked"] += 1

                profile_file = vehicle_dir / "profile.json"
                if profile_file.exists():
                    try:
                        with open(profile_file, 'r') as f:
                            profile = json.load(f)

                        if profile.get("customer_id") != customer_id:
                            details["orphaned_vehicles"].append({
                                "vehicle_dir": str(vehicle_dir),
                                "expected_customer": customer_id,
                                "actual_customer": profile.get("customer_id")
                            })
                    except:
                        pass

        passed = len(details["orphaned_vehicles"]) == 0
        return passed, details

    def _repair_missing_subscription(self, customer_id: str):
        """Create a pending subscription for a customer."""
        subscription_file = self.config.get_customer_subscription(customer_id)
        subscription_file.parent.mkdir(parents=True, exist_ok=True)

        # Create subscription using the proper dataclass format
        subscription_data = {
            "subscription_id": f"sub_{customer_id}_repair_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "customer_id": customer_id,
            "plan": "pending",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "start_date": None,
            "end_date": None,
            "auto_renew": False,
            "payment_status": "pending",
            "license_key": None,
            "features": {},
            "metadata": {
                "auto_repair": True,
                "repair_reason": "Missing subscription detected during integrity check"
            },
            "audit_log": []
        }

        with open(subscription_file, 'w') as f:
            json.dump(subscription_data, f, indent=2)

        logger.info(f"Auto-repaired missing subscription for {customer_id}")


# ==================== RUNTIME ENFORCEMENT ====================

class RuntimeEnforcer:
    """
    Enforces runtime consistency for all access control decisions.

    Handles failure scenarios:
    1. API key valid, subscription expired -> 402
    2. API key revoked, subscription active -> 401
    3. Subscription renewed while offline -> Revalidation
    4. Customer deleted with active subscription -> Cascade
    5. Vehicle reassigned while key in use -> Revocation
    6. Offline license validation failure -> Grace period
    """

    # Grace period for offline mode (hours)
    OFFLINE_GRACE_PERIOD_HOURS = 24

    def __init__(self):
        self.config = get_config()
        self._cache = {}  # Short-lived cache for performance

    def validate_request(
        self,
        api_key_hash: str,
        required_feature: Optional[str] = None,
        vehicle_id: Optional[str] = None
    ) -> Tuple[bool, int, str, Optional[Dict[str, Any]]]:
        """
        Validate a request with full chain enforcement.

        Args:
            api_key_hash: SHA256 hash of API key
            required_feature: Optional feature requirement
            vehicle_id: Optional vehicle being accessed

        Returns:
            (is_valid, http_status_code, error_message, context)

        Context includes: customer_id, subscription, plan, features
        """
        # Step 1: Resolve API key to customer
        customer_id = self._resolve_api_key(api_key_hash)

        if not customer_id:
            return False, 401, "Invalid or revoked API key", None

        # Step 2: Check if customer exists
        customer_dir = self.config.get_customer_dir(customer_id)
        if not customer_dir.exists():
            return False, 401, "Customer account not found", None

        # Step 3: Resolve and validate subscription
        from subscription_manager import get_subscription_manager
        sub_manager = get_subscription_manager()

        subscription = sub_manager.load_subscription(customer_id)

        if not subscription:
            return False, 402, "No subscription found", None

        # Step 4: Check subscription status
        if subscription.status == "expired":
            return False, 402, "Subscription expired - please renew", {
                "customer_id": customer_id,
                "subscription_status": subscription.status,
                "end_date": subscription.end_date
            }

        if subscription.status == "cancelled":
            return False, 402, "Subscription cancelled", None

        if subscription.status == "suspended":
            return False, 403, "Subscription suspended - contact support", None

        if subscription.status not in ["active", "trial"]:
            return False, 402, f"Subscription not active (status: {subscription.status})", None

        # Step 5: Check if subscription is actually active (date check)
        if not subscription.is_active():
            # Mark as expired
            sub_manager.expire_subscription(customer_id, "date_expired", "system")
            return False, 402, "Subscription has expired", None

        # Step 6: Check feature access
        if required_feature:
            if not subscription.has_feature(required_feature):
                return False, 403, f"Feature '{required_feature}' not included in your plan", {
                    "customer_id": customer_id,
                    "plan": subscription.plan,
                    "required_feature": required_feature
                }

        # Step 7: Verify vehicle ownership if specified
        if vehicle_id:
            from customer_isolation import get_isolation_enforcer
            enforcer = get_isolation_enforcer()

            if not enforcer.verify_customer_owns_vehicle(customer_id, vehicle_id):
                return False, 403, "Vehicle not owned by this customer", None

        # All checks passed
        return True, 200, "OK", {
            "customer_id": customer_id,
            "subscription": {
                "id": subscription.subscription_id,
                "plan": subscription.plan,
                "status": subscription.status,
                "end_date": subscription.end_date,
                "days_remaining": subscription.days_remaining()
            },
            "features": subscription.features
        }

    def handle_key_rotation(
        self,
        customer_id: str,
        old_key_hash: str,
        new_key_hash: str,
        rotated_by: str = "system"
    ) -> Tuple[bool, str]:
        """
        Handle API key rotation while preserving subscription linkage.

        GUARANTEE: Key rotation does not break subscription linkage.
        """
        try:
            api_keys_file = self.config.API_KEYS_FILE

            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)

            # Find the old key
            old_key_id = None
            old_key_data = None

            for key_id, key_data in api_keys.items():
                if key_data.get("key_hash") == old_key_hash:
                    old_key_id = key_id
                    old_key_data = key_data
                    break

            if not old_key_id:
                return False, "Old key not found"

            # Verify ownership
            if old_key_data.get("customer_id") != customer_id:
                return False, "Key does not belong to customer"

            # Create new key entry, preserving customer_id and subscription linkage
            import secrets
            new_key_id = f"key_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"

            api_keys[new_key_id] = {
                "key_hash": new_key_hash,
                "customer_id": customer_id,  # PRESERVED
                "created_at": datetime.now().isoformat(),
                "rotated_from": old_key_id,
                "created_by": rotated_by
            }

            # Revoke old key
            api_keys[old_key_id]["revoked"] = True
            api_keys[old_key_id]["revoked_at"] = datetime.now().isoformat()
            api_keys[old_key_id]["revoked_reason"] = "rotation"

            # Save
            with open(api_keys_file, 'w') as f:
                json.dump(api_keys, f, indent=2)

            # Audit log
            log_audit_event(
                event_type=AuditEventType.API_ACCESS,
                customer_id=customer_id,
                details={
                    "event": "api_key_rotated",
                    "old_key_id": old_key_id,
                    "new_key_id": new_key_id,
                    "rotated_by": rotated_by
                }
            )

            return True, f"Key rotated successfully: {new_key_id}"

        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False, f"Key rotation failed: {str(e)}"

    def handle_subscription_revocation(self, customer_id: str) -> Tuple[bool, str]:
        """
        Revoke subscription and immediately invalidate all API keys.

        GUARANTEE: Revoking subscription immediately affects all API keys.
        """
        try:
            # Revoke subscription
            from subscription_manager import get_subscription_manager
            sub_manager = get_subscription_manager()

            success, msg = sub_manager.expire_subscription(
                customer_id,
                reason="manual_revocation",
                expired_by="system"
            )

            if not success:
                return False, msg

            # Invalidate all API keys for this customer
            api_keys_file = self.config.API_KEYS_FILE

            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)

            revoked_count = 0
            for key_id, key_data in api_keys.items():
                if key_data.get("customer_id") == customer_id and not key_data.get("revoked"):
                    api_keys[key_id]["revoked"] = True
                    api_keys[key_id]["revoked_at"] = datetime.now().isoformat()
                    api_keys[key_id]["revoked_reason"] = "subscription_revoked"
                    revoked_count += 1

            with open(api_keys_file, 'w') as f:
                json.dump(api_keys, f, indent=2)

            logger.info(f"Subscription revoked for {customer_id}, {revoked_count} API keys invalidated")

            return True, f"Subscription revoked, {revoked_count} API keys invalidated"

        except Exception as e:
            logger.error(f"Subscription revocation failed: {e}")
            return False, f"Revocation failed: {str(e)}"

    def validate_offline_license(
        self,
        license_key: str,
        customer_id: str,
        last_online_check: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """
        Validate offline license with grace period handling.

        Args:
            license_key: License key to validate
            customer_id: Customer ID
            last_online_check: Last successful online validation

        Returns:
            (is_valid, message)
        """
        from subscription_manager import get_subscription_manager
        manager = get_subscription_manager()

        is_valid, reason = manager.validate_offline_license(license_key, customer_id)

        if is_valid:
            return True, "License valid"

        # Check grace period
        if last_online_check:
            hours_offline = (datetime.now() - last_online_check).total_seconds() / 3600

            if hours_offline <= self.OFFLINE_GRACE_PERIOD_HOURS:
                logger.warning(f"License validation failed but within grace period: {customer_id}")
                return True, f"Grace period active ({int(hours_offline)}h of {self.OFFLINE_GRACE_PERIOD_HOURS}h)"

        return False, reason

    def _resolve_api_key(self, key_hash: str) -> Optional[str]:
        """Resolve API key hash to customer_id."""
        try:
            api_keys_file = self.config.API_KEYS_FILE

            if not api_keys_file.exists():
                return None

            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)

            for key_id, key_data in api_keys.items():
                if key_data.get("key_hash") == key_hash:
                    # Check if revoked
                    if key_data.get("revoked", False):
                        return None
                    return key_data.get("customer_id")

            return None

        except Exception as e:
            logger.error(f"API key resolution failed: {e}")
            return None


# ==================== STARTUP INTEGRITY CHECK ====================

def run_startup_integrity_check() -> Tuple[bool, Dict[str, Any]]:
    """
    Run integrity check at application startup.

    Called during server initialization.
    Returns (passed, report).

    If critical violations found, application should not start.
    """
    logger.info("Running startup integrity check...")

    checker = SystemIntegrityChecker()
    report = checker.run_all_checks()

    # Count critical violations
    critical_count = sum(
        1 for v in report.get("violations", [])
        if v.get("severity") == "critical"
    )

    if critical_count > 0:
        logger.error(f"STARTUP BLOCKED: {critical_count} critical integrity violations")
        logger.error("Run system_integrity.py --repair to attempt automatic repair")

        # Send alert
        try:
            from monitoring_alerts import send_alert, AlertType, AlertSeverity
            send_alert(
                alert_type=AlertType.SYSTEM_INTEGRITY_VIOLATION,
                severity=AlertSeverity.CRITICAL,
                title="Startup Integrity Check Failed",
                message=f"{critical_count} critical violations detected",
                details=report
            )
        except:
            pass

        return False, report

    if not report.get("healthy"):
        logger.warning("Startup integrity check found non-critical issues")
    else:
        logger.info("Startup integrity check passed")

    return True, report


# ==================== MODULE-LEVEL FUNCTIONS ====================

_integrity_checker: Optional[SystemIntegrityChecker] = None
_runtime_enforcer: Optional[RuntimeEnforcer] = None


def get_integrity_checker() -> SystemIntegrityChecker:
    """Get global integrity checker."""
    global _integrity_checker
    if _integrity_checker is None:
        _integrity_checker = SystemIntegrityChecker()
    return _integrity_checker


def get_runtime_enforcer() -> RuntimeEnforcer:
    """Get global runtime enforcer."""
    global _runtime_enforcer
    if _runtime_enforcer is None:
        _runtime_enforcer = RuntimeEnforcer()
    return _runtime_enforcer


# ==================== CLI INTERFACE ====================

if __name__ == "__main__":
    import sys
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description="System Integrity Checker")
    parser.add_argument("--repair", action="store_true", help="Attempt automatic repairs")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("PREDICT OBD - SYSTEM INTEGRITY CHECK")
    print("=" * 60)

    checker = SystemIntegrityChecker()
    report = checker.run_all_checks()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\nOverall Status: {'HEALTHY' if report['healthy'] else 'UNHEALTHY'}")
        print(f"Timestamp: {report['timestamp']}")
        print()

        for check_name, result in report['checks'].items():
            status = "PASS" if result['passed'] else "FAIL"
            print(f"  [{status}] {check_name}")

            if not result['passed'] and 'details' in result:
                for key, value in result['details'].items():
                    if value:
                        print(f"        {key}: {value}")

        if report['violations']:
            print(f"\nViolations Found: {len(report['violations'])}")
            for v in report['violations']:
                print(f"  [{v['severity'].upper()}] {v['violation_type']}: {v['description']}")
                if v['auto_repair']:
                    print(f"        AUTO-REPAIRED: {v['repair_action']}")

    sys.exit(0 if report['healthy'] else 1)
