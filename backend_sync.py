"""
Backend Sync Module for PREDICT Desktop App

This module synchronizes data from the Desktop app to the Backend server:
- Registers owners (fleet managers) in backend customers table
- Registers drivers under fleet managers
- Pushes real-time OBD data to backend
- Maintains data consistency between Desktop and Backend

Author: PREDICT Team
Created: January 2026
"""

import requests
import hashlib
import sqlite3
import time
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class BackendSync:
    """
    Sync Desktop app data to backend server.
    Ensures owners, vehicles, and drivers are registered in backend.
    """

    def __init__(self, backend_url: str, admin_key: str, desktop_db_path: str):
        """
        Initialize the backend sync module.

        Args:
            backend_url: Backend server URL (e.g., "https://predict.previlium.com")
            admin_key: Desktop admin authentication key
            desktop_db_path: Path to Desktop app's vehicle_profiles.db
        """
        self.backend_url = backend_url.rstrip('/')
        self.admin_key = admin_key
        self.desktop_db_path = desktop_db_path

        self.session = requests.Session()
        self.session.headers.update({
            "X-Admin-Key": admin_key,
            "Content-Type": "application/json"
        })

        # Cache for owner_id -> backend_customer_id mapping
        self._owner_cache: Dict[int, int] = {}

        # Cache for profile_id -> backend_customer_id mapping
        self._driver_cache: Dict[int, int] = {}

    def _get_desktop_conn(self) -> sqlite3.Connection:
        """Get connection to Desktop app's vehicle_profiles.db"""
        conn = sqlite3.connect(self.desktop_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def sync_owner(self, owner_id: int) -> Optional[int]:
        """
        Sync an owner from Desktop app to backend.

        Args:
            owner_id: Owner ID from Desktop app

        Returns:
            Backend customer_id, or None if sync failed
        """
        # Check cache first
        if owner_id in self._owner_cache:
            return self._owner_cache[owner_id]

        try:
            conn = self._get_desktop_conn()
            cur = conn.cursor()

            # Get owner data from Desktop app
            cur.execute("SELECT * FROM owners WHERE owner_id = ?", (owner_id,))
            owner = cur.fetchone()

            if not owner:
                logger.warning(f"Owner {owner_id} not found in Desktop app")
                conn.close()
                return None

            # Get owner's API key from any vehicle profile they own
            cur.execute("""
                SELECT api_key FROM vehicle_profiles
                WHERE owner_id = ? AND api_key IS NOT NULL AND api_key != ''
                LIMIT 1
            """, (owner_id,))
            api_key_row = cur.fetchone()
            conn.close()

            if not api_key_row or not api_key_row["api_key"]:
                logger.error(f"Owner {owner['name']} (ID: {owner_id}) has no API key configured")
                return None

            # Register in backend
            # Convert Row to dict for easier access
            owner_dict = dict(owner)
            payload = {
                "name": owner_dict["name"],
                "email": owner_dict.get("email") or f"owner{owner_id}@previlium.com",
                "phone": owner_dict.get("phone") or "",
                "api_key": api_key_row["api_key"],
                "tier": "premium",
                "owner_id": owner_id
            }

            response = self.session.post(
                f"{self.backend_url}/api/admin/register-owner",
                json=payload,
                timeout=30
            )

            if response.ok:
                data = response.json()
                customer_id = data.get("customer_id")

                # Cache the mapping
                self._owner_cache[owner_id] = customer_id

                logger.info(f"✓ Synced owner: {owner['name']} (owner_id: {owner_id} → customer_id: {customer_id})")
                return customer_id
            else:
                logger.error(f"✗ Failed to register owner {owner['name']}: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"✗ Exception syncing owner {owner_id}: {str(e)}")
            return None

    def sync_driver(self, profile_id: int, fleet_manager_customer_id: int) -> Optional[int]:
        """
        Sync a driver/vehicle from Desktop app to backend.

        Args:
            profile_id: Vehicle profile ID from Desktop app
            fleet_manager_customer_id: Backend customer_id of the fleet manager

        Returns:
            Backend customer_id for the driver, or None if sync failed
        """
        # Check cache first
        if profile_id in self._driver_cache:
            return self._driver_cache[profile_id]

        try:
            conn = self._get_desktop_conn()
            cur = conn.cursor()

            # Get vehicle profile
            cur.execute("SELECT * FROM vehicle_profiles WHERE profile_id = ?", (profile_id,))
            vehicle = cur.fetchone()

            if not vehicle:
                logger.warning(f"Profile {profile_id} not found in Desktop app")
                conn.close()
                return None

            # Convert Row to dict for easier access
            vehicle_dict = dict(vehicle)

            # Generate API key if not exists
            api_key = vehicle_dict.get("api_key")
            if not api_key or api_key == "":
                import secrets
                api_key = f"DRIVER-{secrets.token_urlsafe(16)}"

                # Update Desktop app with generated API key
                cur.execute(
                    "UPDATE vehicle_profiles SET api_key = ? WHERE profile_id = ?",
                    (api_key, profile_id)
                )
                conn.commit()
                logger.info(f"  Generated API key for profile {profile_id}: {api_key}")

            conn.close()

            # Register in backend
            # Convert Row to dict for easier access
            vehicle_dict = dict(vehicle)
            payload = {
                "name": vehicle_dict["name"],
                "email": vehicle_dict.get("customer_email") or f"driver{profile_id}@previlium.com",
                "phone": vehicle_dict.get("customer_phone") or "",
                "api_key": api_key,
                "tier": "pro",
                "fleet_manager_id": fleet_manager_customer_id,
                "car_make": vehicle_dict.get("make") or "",
                "car_model": vehicle_dict.get("model") or "",
                "car_year": vehicle_dict.get("year"),
                "car_plate": vehicle_dict.get("license_plate") or "",
                "profile_id": profile_id
            }

            response = self.session.post(
                f"{self.backend_url}/api/admin/register-driver",
                json=payload,
                timeout=30
            )

            if response.ok:
                data = response.json()
                customer_id = data.get("customer_id")

                # Cache the mapping
                self._driver_cache[profile_id] = customer_id

                vehicle_info = f"{vehicle_dict.get('year', '')} {vehicle_dict.get('make', '')} {vehicle_dict.get('model', '')}".strip()
                logger.info(f"  ✓ Synced driver: {vehicle_dict['name']} - {vehicle_info} (profile_id: {profile_id} → customer_id: {customer_id})")
                return customer_id
            else:
                logger.error(f"  ✗ Failed to register driver {vehicle['name']}: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"  ✗ Exception syncing driver {profile_id}: {str(e)}")
            return None

    def sync_all_owners_and_drivers(self) -> Dict[str, int]:
        """
        Full sync of all owners and their vehicles/drivers to backend.

        Returns:
            Dict with sync statistics: {
                "owners_synced": int,
                "drivers_synced": int,
                "owners_failed": int,
                "drivers_failed": int
            }
        """
        stats = {
            "owners_synced": 0,
            "drivers_synced": 0,
            "owners_failed": 0,
            "drivers_failed": 0
        }

        try:
            conn = self._get_desktop_conn()
            cur = conn.cursor()

            # Get all owners
            cur.execute("SELECT * FROM owners ORDER BY owner_id")
            owners = cur.fetchall()

            logger.info(f"\n{'='*60}")
            logger.info(f"Starting full sync: {len(owners)} owners found")
            logger.info(f"{'='*60}\n")

            for owner in owners:
                owner_id = owner["owner_id"]
                owner_name = owner["name"]

                logger.info(f"Syncing owner: {owner_name} (ID: {owner_id})")

                # Sync owner to backend
                backend_customer_id = self.sync_owner(owner_id)
                if not backend_customer_id:
                    logger.error(f"  ✗ Failed to sync owner {owner_name}")
                    stats["owners_failed"] += 1
                    continue

                stats["owners_synced"] += 1

                # Get all vehicles for this owner
                cur.execute("""
                    SELECT * FROM vehicle_profiles WHERE owner_id = ?
                    ORDER BY profile_id
                """, (owner_id,))
                vehicles = cur.fetchall()

                logger.info(f"  Found {len(vehicles)} vehicle(s) for {owner_name}")

                for vehicle in vehicles:
                    profile_id = vehicle["profile_id"]
                    vehicle_name = vehicle["name"]

                    driver_customer_id = self.sync_driver(profile_id, backend_customer_id)
                    if driver_customer_id:
                        stats["drivers_synced"] += 1
                    else:
                        logger.error(f"    ✗ Failed to sync driver/vehicle: {vehicle_name}")
                        stats["drivers_failed"] += 1

                logger.info("")  # Empty line between owners

            conn.close()

            logger.info(f"{'='*60}")
            logger.info(f"Sync completed!")
            logger.info(f"  Owners synced: {stats['owners_synced']}/{stats['owners_synced'] + stats['owners_failed']}")
            logger.info(f"  Drivers synced: {stats['drivers_synced']}/{stats['drivers_synced'] + stats['drivers_failed']}")
            logger.info(f"{'='*60}\n")

        except Exception as e:
            logger.error(f"✗ Exception during full sync: {str(e)}")

        return stats

    def push_obd_data(self, profile_id: int, obd_records: List[Dict]) -> bool:
        """
        Push OBD data from Desktop app to backend.

        Args:
            profile_id: Vehicle profile ID
            obd_records: List of OBD records to push, each record should have:
                {
                    "timestamp": float,
                    "speed": float,
                    "rpm": float,
                    "engine_load": float,
                    ...
                }

        Returns:
            True if push succeeded, False otherwise
        """
        if not obd_records:
            return True  # Nothing to push

        try:
            payload = {
                "profile_id": profile_id,
                "records": obd_records
            }

            response = self.session.post(
                f"{self.backend_url}/api/admin/obd-data",
                json=payload,
                timeout=10
            )

            if response.ok:
                logger.debug(f"Pushed {len(obd_records)} OBD records for profile {profile_id}")
                return True
            else:
                logger.warning(f"Failed to push OBD data for profile {profile_id}: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Exception pushing OBD data for profile {profile_id}: {str(e)}")
            return False


# Convenience function for testing
def main():
    """Test the backend sync module"""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Configuration
    BACKEND_URL = "https://predict.previlium.com"
    ADMIN_KEY = "PREDICT-DESKTOP-ADMIN-KEY-2026"
    DESKTOP_DB_PATH = r"C:\D Drive\Predict\data\vehicle_profiles.db"

    # Check if database exists
    if not Path(DESKTOP_DB_PATH).exists():
        print(f"✗ Desktop database not found: {DESKTOP_DB_PATH}")
        print("  Please ensure the Desktop app has been run at least once.")
        sys.exit(1)

    # Create sync instance
    syncer = BackendSync(BACKEND_URL, ADMIN_KEY, DESKTOP_DB_PATH)

    # Run full sync
    print("\nStarting backend sync...\n")
    stats = syncer.sync_all_owners_and_drivers()

    # Print results
    print("\n" + "="*60)
    print("SYNC RESULTS")
    print("="*60)
    print(f"Owners synced:   {stats['owners_synced']}")
    print(f"Owners failed:   {stats['owners_failed']}")
    print(f"Drivers synced:  {stats['drivers_synced']}")
    print(f"Drivers failed:  {stats['drivers_failed']}")
    print("="*60 + "\n")

    if stats['owners_failed'] > 0 or stats['drivers_failed'] > 0:
        print("[!] Some items failed to sync. Check the logs above for details.")
        sys.exit(1)
    else:
        print("[OK] All items synced successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
