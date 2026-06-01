"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Vehicle Profile Manager

Vehicle Profile Manager - Provides vehicle profile access for server endpoints
"""

import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path

from config import get_config
CONFIG = get_config()


class VehicleProfileManager:
    """Manages vehicle profiles for maintenance and service features"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(CONFIG.DATA_DIR / "vehicle_profiles.db")
        self.db_path = db_path

    def get_profile(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a vehicle profile by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT * FROM vehicle_profiles WHERE profile_id = ?
            """, (profile_id,))

            row = cur.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"Error getting profile {profile_id}: {e}")
            return None

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all vehicle profiles"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("SELECT * FROM vehicle_profiles")
            rows = cur.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error getting profiles: {e}")
            return []

    def get_profile_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a vehicle profile by name"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT * FROM vehicle_profiles WHERE name = ?
            """, (name,))

            row = cur.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"Error getting profile by name {name}: {e}")
            return None

    def get_vehicle_mileage(self, profile_id: int) -> float:
        """
        Get current mileage for a vehicle from multiple sources.

        Priority:
        1. Direct odometer reading from OBD data
        2. Profile's stored mileage field
        3. Last service mileage from service history
        4. Return 0.0 if not available
        """
        try:
            # Source 1: Try to get odometer from OBDserver database
            obd_db_path = str(CONFIG.SERVER_DB_PATH)
            if Path(obd_db_path).exists():
                conn = sqlite3.connect(obd_db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                # Get latest record with mileage/odometer data
                cur.execute("""
                    SELECT mileage_km, odometer FROM vehicle_data
                    WHERE profile_id = ? AND (mileage_km > 0 OR odometer > 0)
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (profile_id,))

                row = cur.fetchone()
                conn.close()

                if row:
                    if row['mileage_km'] and row['mileage_km'] > 0:
                        return float(row['mileage_km'])
                    if row['odometer'] and row['odometer'] > 0:
                        return float(row['odometer'])

            # Source 2: Try to get from profile data
            profile = self.get_profile(profile_id)
            if profile:
                if profile.get('current_mileage'):
                    return float(profile['current_mileage'])
                if profile.get('last_odometer'):
                    return float(profile['last_odometer'])

            # Source 3: Get last service mileage from service history
            service_db_path = str(CONFIG.DATA_DIR / "service_history.db")
            if Path(service_db_path).exists():
                conn = sqlite3.connect(service_db_path)
                cur = conn.cursor()

                cur.execute("""
                    SELECT service_km FROM service_records
                    WHERE profile_id = ?
                    ORDER BY service_date DESC, service_km DESC
                    LIMIT 1
                """, (profile_id,))

                row = cur.fetchone()
                conn.close()

                if row and row[0]:
                    return float(row[0])

            return 0.0
        except Exception as e:
            print(f"Error getting mileage: {e}")
            return 0.0

    def get_service_history(self, profile_id: int) -> List[Dict[str, Any]]:
        """Get service history for a vehicle"""
        try:
            # Check if service_history table exists
            service_db_path = str(CONFIG.DATA_DIR / "service_history.db")
            if not Path(service_db_path).exists():
                return []

            conn = sqlite3.connect(service_db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT * FROM service_history
                WHERE profile_id = ?
                ORDER BY service_date DESC
            """, (profile_id,))

            rows = cur.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error getting service history: {e}")
            return []
