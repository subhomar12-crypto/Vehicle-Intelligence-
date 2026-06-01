"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Customer & Vehicle Data Isolation

Customer & Vehicle Data Isolation Enforcement
Ensures strict data separation and deterministic path mapping.

CRITICAL REQUIREMENTS:
- VIN → vehicle directory mapping must be deterministic
- No shared files between customers
- All data strictly isolated by customer_id
- Safe customer deletion (soft delete with 30-day recovery)
- Safe vehicle reassignment
"""

import re
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from config import get_config

logger = logging.getLogger(__name__)


class IsolationEnforcer:
    """
    Enforces strict customer and vehicle data isolation.

    Rules:
    1. Each customer has dedicated directory: PredictData/customers/{customer_id}/
    2. Each vehicle mapped deterministically by VIN
    3. No file sharing between customers
    4. All operations verify ownership
    """

    def __init__(self):
        self.config = get_config()

    def get_vehicle_id_from_vin(self, vin: str) -> str:
        """
        Generate deterministic vehicle_id from VIN.

        VIN → vehicle_id mapping is:
        - Deterministic (same VIN = same ID)
        - URL-safe
        - Collision-resistant

        Args:
            vin: 17-character VIN

        Returns:
            Deterministic vehicle_id
        """
        # Validate VIN format
        if not self._is_valid_vin(vin):
            raise ValueError(f"Invalid VIN format: {vin}")

        # Normalize VIN (uppercase, strip whitespace)
        normalized_vin = vin.strip().upper()

        # Generate deterministic hash
        # Use first 12 chars of SHA256 for collision resistance while keeping readable length
        hash_obj = hashlib.sha256(normalized_vin.encode())
        hash_hex = hash_obj.hexdigest()[:12]

        # Format: vin_{last4}_{hash}
        # Example: vin_9186_a1b2c3d4e5f6
        last_4 = normalized_vin[-4:]
        vehicle_id = f"vin_{last_4}_{hash_hex}"

        return vehicle_id

    def get_vehicle_directory(
        self,
        customer_id: str,
        vin: str,
        create: bool = False
    ) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        Get vehicle directory with ownership verification.

        Args:
            customer_id: Customer who owns the vehicle
            vin: Vehicle VIN
            create: Create directory if it doesn't exist

        Returns:
            (success, directory_path, error_message)
        """
        try:
            # Validate customer exists
            customer_dir = self.config.get_customer_dir(customer_id)
            if not customer_dir.exists():
                return False, None, f"Customer {customer_id} does not exist"

            # Get deterministic vehicle_id
            vehicle_id = self.get_vehicle_id_from_vin(vin)

            # Get vehicle directory
            vehicle_dir = self.config.get_vehicle_dir(customer_id, vehicle_id)

            # Verify ownership if directory exists
            if vehicle_dir.exists():
                if not self._verify_vehicle_ownership(vehicle_dir, customer_id, vin):
                    return False, None, "Vehicle ownership verification failed"

            # Create if requested
            if create and not vehicle_dir.exists():
                self._create_vehicle_directory(customer_id, vehicle_id, vin)

            return True, vehicle_dir, None

        except Exception as e:
            logger.error(f"Error getting vehicle directory: {e}")
            return False, None, str(e)

    def verify_customer_owns_vehicle(
        self,
        customer_id: str,
        vehicle_id: str
    ) -> bool:
        """
        Verify that a customer owns a specific vehicle.

        Args:
            customer_id: Customer to verify
            vehicle_id: Vehicle to verify

        Returns:
            True if customer owns vehicle
        """
        vehicle_dir = self.config.get_vehicle_dir(customer_id, vehicle_id)

        if not vehicle_dir.exists():
            return False

        # Check profile file
        profile_file = vehicle_dir / "profile.json"
        if not profile_file.exists():
            return False

        try:
            import json
            with open(profile_file, 'r') as f:
                profile = json.load(f)

            return profile.get("customer_id") == customer_id

        except:
            return False

    def list_customer_vehicles(self, customer_id: str) -> List[Dict[str, Any]]:
        """List all vehicles owned by a customer"""
        vehicles_dir = self.config.get_customer_vehicles_dir(customer_id)

        if not vehicles_dir.exists():
            return []

        vehicles = []
        for vehicle_dir in vehicles_dir.iterdir():
            if not vehicle_dir.is_dir():
                continue

            profile_file = vehicle_dir / "profile.json"
            if not profile_file.exists():
                continue

            try:
                import json
                with open(profile_file, 'r') as f:
                    profile = json.load(f)

                vehicles.append({
                    "vehicle_id": vehicle_dir.name,
                    "vin": profile.get("vin"),
                    "make": profile.get("make"),
                    "model": profile.get("model"),
                    "year": profile.get("year"),
                    "created_at": profile.get("created_at")
                })

            except:
                continue

        return vehicles

    def reassign_vehicle(
        self,
        vehicle_id: str,
        from_customer_id: str,
        to_customer_id: str,
        operator: str = "system"
    ) -> Tuple[bool, str]:
        """
        Safely reassign a vehicle from one customer to another.

        Args:
            vehicle_id: Vehicle to reassign
            from_customer_id: Current owner
            to_customer_id: New owner
            operator: Who performed the reassignment

        Returns:
            (success, message)
        """
        import shutil
        import json

        try:
            # Verify source ownership
            if not self.verify_customer_owns_vehicle(from_customer_id, vehicle_id):
                return False, "Source customer does not own this vehicle"

            # Verify target customer exists
            to_customer_dir = self.config.get_customer_dir(to_customer_id)
            if not to_customer_dir.exists():
                return False, f"Target customer {to_customer_id} does not exist"

            # Get paths
            source_dir = self.config.get_vehicle_dir(from_customer_id, vehicle_id)
            target_dir = self.config.get_vehicle_dir(to_customer_id, vehicle_id)

            # Check target doesn't already exist
            if target_dir.exists():
                return False, "Vehicle already exists for target customer"

            # Move vehicle directory
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_dir), str(target_dir))

            # Update vehicle profile
            profile_file = target_dir / "profile.json"
            if profile_file.exists():
                with open(profile_file, 'r') as f:
                    profile = json.load(f)

                profile["customer_id"] = to_customer_id
                profile["reassigned_at"] = datetime.now().isoformat()
                profile["reassigned_by"] = operator
                profile["previous_customer_id"] = from_customer_id

                with open(profile_file, 'w') as f:
                    json.dump(profile, f, indent=2)

            # Audit log the reassignment
            from audit_logger import log_audit_event, AuditEventType
            log_audit_event(
                event_type=AuditEventType.VEHICLE_REMOVED,
                customer_id=from_customer_id,
                details={
                    "vehicle_id": vehicle_id,
                    "reassigned_to": to_customer_id,
                    "operator": operator
                }
            )
            log_audit_event(
                event_type=AuditEventType.VEHICLE_ADDED,
                customer_id=to_customer_id,
                details={
                    "vehicle_id": vehicle_id,
                    "reassigned_from": from_customer_id,
                    "operator": operator
                }
            )

            logger.info(f"Vehicle {vehicle_id} reassigned from {from_customer_id} to {to_customer_id}")

            return True, "Vehicle reassigned successfully"

        except Exception as e:
            logger.error(f"Failed to reassign vehicle: {e}")
            return False, f"Reassignment failed: {str(e)}"

    def delete_customer_data(
        self,
        customer_id: str,
        soft_delete: bool = True,
        deleted_by: str = "operator"
    ) -> Tuple[bool, str]:
        """
        Delete all customer data (GDPR compliance).

        Args:
            customer_id: Customer to delete
            soft_delete: If True, rename for 30-day recovery. If False, permanent.
            deleted_by: Operator who performed deletion

        Returns:
            (success, message)
        """
        from directory_manager import DirectoryManager

        try:
            manager = DirectoryManager()

            # Audit log deletion
            from audit_logger import log_audit_event, AuditEventType
            log_audit_event(
                event_type=AuditEventType.CUSTOMER_DELETED,
                customer_id=customer_id,
                details={
                    "soft_delete": soft_delete,
                    "operator": deleted_by
                }
            )

            # Perform deletion
            success = manager.delete_customer(customer_id, soft_delete=soft_delete)

            if success:
                if soft_delete:
                    message = f"Customer {customer_id} soft-deleted (30-day recovery available)"
                else:
                    message = f"Customer {customer_id} permanently deleted"

                logger.info(message)
                return True, message
            else:
                return False, "Deletion failed"

        except Exception as e:
            logger.error(f"Failed to delete customer {customer_id}: {e}")
            return False, f"Deletion failed: {str(e)}"

    def _is_valid_vin(self, vin: str) -> bool:
        """Validate VIN format (17 alphanumeric, excluding I, O, Q)"""
        VIN_PATTERN = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$', re.IGNORECASE)
        return bool(VIN_PATTERN.match(vin.strip()))

    def _verify_vehicle_ownership(
        self,
        vehicle_dir: Path,
        customer_id: str,
        vin: str
    ) -> bool:
        """Verify vehicle belongs to customer and matches VIN"""
        import json

        profile_file = vehicle_dir / "profile.json"
        if not profile_file.exists():
            return False

        try:
            with open(profile_file, 'r') as f:
                profile = json.load(f)

            # Verify customer ownership
            if profile.get("customer_id") != customer_id:
                logger.warning(f"Ownership mismatch: expected {customer_id}, got {profile.get('customer_id')}")
                return False

            # Verify VIN matches
            if profile.get("vin"):
                if profile.get("vin").upper() != vin.strip().upper():
                    logger.warning(f"VIN mismatch: expected {vin}, got {profile.get('vin')}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error verifying ownership: {e}")
            return False

    def _create_vehicle_directory(
        self,
        customer_id: str,
        vehicle_id: str,
        vin: str
    ):
        """Create vehicle directory structure"""
        import json
        from datetime import datetime
        from directory_manager import DirectoryManager

        manager = DirectoryManager()
        vehicle_dir = manager.create_vehicle(customer_id, vehicle_id)

        # Update profile with VIN
        profile_file = vehicle_dir / "profile.json"
        with open(profile_file, 'r') as f:
            profile = json.load(f)

        profile["vin"] = vin.strip().upper()

        with open(profile_file, 'w') as f:
            json.dump(profile, f, indent=2)

        logger.info(f"Created vehicle directory: {customer_id}/{vehicle_id}")


# ==================== MODULE-LEVEL FUNCTIONS ====================

_enforcer: Optional[IsolationEnforcer] = None


def get_isolation_enforcer() -> IsolationEnforcer:
    """Get global isolation enforcer instance"""
    global _enforcer
    if _enforcer is None:
        _enforcer = IsolationEnforcer()
    return _enforcer


def get_vehicle_path(customer_id: str, vin: str, create: bool = False) -> Optional[Path]:
    """Convenience function to get vehicle directory"""
    enforcer = get_isolation_enforcer()
    success, path, error = enforcer.get_vehicle_directory(customer_id, vin, create=create)
    return path if success else None
