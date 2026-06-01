"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Vehicle Data Migration Script - Migrates existing data to organized folder structure.

This script migrates existing vehicle data from flat storage to the new
hierarchical Make/Model/Year folder structure.

Usage:
    python migrate_vehicle_data.py [--dry-run] [--verbose]
"""

import os
import sys
import json
import shutil
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vehicle_data_organizer import VehicleDataOrganizer, get_vehicle_organizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VehicleDataMigrator:
    """
    Migrates existing vehicle data to the new organized folder structure.
    """

    def __init__(self, base_path: str = "./PredictData", dry_run: bool = False):
        self.base_path = base_path
        self.dry_run = dry_run
        self.organizer = get_vehicle_organizer(base_path)

        # Migration statistics
        self.stats = {
            'vehicles_found': 0,
            'vehicles_migrated': 0,
            'vehicles_skipped': 0,
            'vehicles_failed': 0,
            'obd_files_moved': 0,
            'prediction_files_moved': 0,
            'errors': []
        }

        # Old data paths to check
        self.old_paths = {
            'obd_data': os.path.join(base_path, 'obd_data'),
            'predictions': os.path.join(base_path, 'predictions'),
            'baselines': os.path.join(base_path, 'ai_baselines'),
            'profiles': os.path.join(base_path, 'profiles'),
        }

    def discover_vehicles_from_database(self) -> List[Dict[str, Any]]:
        """
        Discover vehicles from the database.
        Returns list of vehicle profiles.
        """
        vehicles = []

        # Try to import and use database module
        try:
            from database import VehicleDatabase
            db = VehicleDatabase()

            # Get all profiles
            profiles = db.get_all_profiles()
            for profile in profiles:
                vehicles.append({
                    'profile_id': profile.get('profile_id'),
                    'owner_id': profile.get('owner_id'),
                    'make': profile.get('make', 'Unknown'),
                    'model': profile.get('model', 'Unknown'),
                    'year': profile.get('year', 0),
                    'license_plate': profile.get('license_plate', ''),
                    'vin': profile.get('vin', ''),
                    'name': profile.get('name', ''),
                    'last_seen': profile.get('last_seen'),
                    'source': 'database'
                })

            logger.info(f"Found {len(vehicles)} vehicles in database")

        except Exception as e:
            logger.warning(f"Could not read from database: {e}")

        return vehicles

    def discover_vehicles_from_files(self) -> List[Dict[str, Any]]:
        """
        Discover vehicles from existing file structures.
        Returns list of vehicle profiles found in files.
        """
        vehicles = []

        # Check old profiles directory
        profiles_path = self.old_paths.get('profiles')
        if profiles_path and os.path.exists(profiles_path):
            for filename in os.listdir(profiles_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(profiles_path, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            profile = json.load(f)
                        vehicles.append({
                            **profile,
                            'source': 'profile_file',
                            'source_path': filepath
                        })
                    except Exception as e:
                        logger.warning(f"Error reading profile {filepath}: {e}")

        # Check OBD data directory for profile IDs
        obd_path = self.old_paths.get('obd_data')
        if obd_path and os.path.exists(obd_path):
            known_ids = {v.get('profile_id') for v in vehicles if v.get('profile_id')}

            for item in os.listdir(obd_path):
                item_path = os.path.join(obd_path, item)
                if os.path.isdir(item_path):
                    # Check if this is a profile ID we don't have
                    try:
                        profile_id = int(item) if item.isdigit() else item
                        if profile_id not in known_ids:
                            # Try to extract info from OBD files
                            info = self._extract_info_from_obd_files(item_path)
                            if info:
                                vehicles.append({
                                    'profile_id': profile_id,
                                    'make': info.get('make', 'Unknown'),
                                    'model': info.get('model', 'Unknown'),
                                    'year': info.get('year', 0),
                                    'source': 'obd_directory',
                                    'source_path': item_path
                                })
                    except Exception as e:
                        logger.warning(f"Error processing OBD directory {item}: {e}")

        logger.info(f"Found {len(vehicles)} vehicles from files")
        return vehicles

    def _extract_info_from_obd_files(self, obd_dir: str) -> Optional[Dict[str, Any]]:
        """Extract vehicle info from OBD reading files."""
        # Look for any JSON file with vehicle info
        for root, dirs, files in os.walk(obd_dir):
            for filename in files:
                if filename.endswith('.json'):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        # Check for vehicle info in the data
                        if isinstance(data, dict):
                            make = data.get('make') or data.get('vehicle_make')
                            model = data.get('model') or data.get('vehicle_model')
                            year = data.get('year') or data.get('vehicle_year')

                            if make or model or year:
                                return {
                                    'make': make or 'Unknown',
                                    'model': model or 'Unknown',
                                    'year': int(year) if year else 0
                                }
                    except Exception:
                        pass
        return None

    def migrate_vehicle(self, vehicle: Dict[str, Any]) -> bool:
        """
        Migrate a single vehicle to the new structure.

        Returns True if successful, False otherwise.
        """
        profile_id = vehicle.get('profile_id')
        make = vehicle.get('make', 'Unknown')
        model = vehicle.get('model', 'Unknown')
        year = vehicle.get('year', 0)

        if not profile_id:
            logger.warning(f"Skipping vehicle without profile_id: {vehicle}")
            self.stats['vehicles_skipped'] += 1
            return False

        # Validate make/model/year
        if make == 'Unknown' or model == 'Unknown' or year == 0:
            logger.warning(f"Vehicle {profile_id} has incomplete info: {make} {model} {year}")
            # Still try to migrate with available info

        logger.info(f"Migrating vehicle {profile_id}: {make} {model} {year}")

        try:
            if self.dry_run:
                logger.info(f"  [DRY RUN] Would register vehicle {profile_id}")
                logger.info(f"  [DRY RUN] Would create folder: vehicles/{make}/{model}/{year}/vehicle_{profile_id}")
            else:
                # Register vehicle with the organizer
                location = self.organizer.register_vehicle(
                    profile_id=str(profile_id),
                    make=make,
                    model=model,
                    year=year,
                    owner_id=vehicle.get('owner_id'),
                    license_plate=vehicle.get('license_plate'),
                    vin=vehicle.get('vin')
                )

                if location:
                    logger.info(f"  Created folder: {location.folder_path}")

                    # Migrate OBD data
                    obd_count = self._migrate_obd_data(profile_id, location.folder_path)
                    self.stats['obd_files_moved'] += obd_count

                    # Migrate prediction data
                    pred_count = self._migrate_prediction_data(profile_id, location.folder_path)
                    self.stats['prediction_files_moved'] += pred_count

                    # Migrate baseline data
                    self._migrate_baseline_data(profile_id, location.folder_path)

                    logger.info(f"  Migrated {obd_count} OBD files, {pred_count} prediction files")

            self.stats['vehicles_migrated'] += 1
            return True

        except Exception as e:
            logger.error(f"Failed to migrate vehicle {profile_id}: {e}")
            self.stats['vehicles_failed'] += 1
            self.stats['errors'].append({
                'vehicle_id': profile_id,
                'error': str(e)
            })
            return False

    def _migrate_obd_data(self, profile_id: Any, new_folder: str) -> int:
        """Migrate OBD data files to new location."""
        count = 0
        old_obd_path = os.path.join(self.old_paths['obd_data'], str(profile_id))

        if not os.path.exists(old_obd_path):
            return 0

        new_obd_path = os.path.join(new_folder, 'obd_readings')
        os.makedirs(new_obd_path, exist_ok=True)

        # Walk through old OBD directory
        for root, dirs, files in os.walk(old_obd_path):
            for filename in files:
                if filename.endswith('.json'):
                    old_file = os.path.join(root, filename)
                    # Determine relative path for organization
                    rel_path = os.path.relpath(root, old_obd_path)

                    if rel_path == '.':
                        # File is directly in profile folder - organize by month
                        try:
                            with open(old_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            timestamp = data.get('timestamp', '')
                            if timestamp:
                                # Extract month folder from timestamp
                                month = timestamp[:7].replace('-', '-')  # YYYY-MM
                                month_folder = os.path.join(new_obd_path, month)
                                os.makedirs(month_folder, exist_ok=True)
                                new_file = os.path.join(month_folder, filename)
                            else:
                                new_file = os.path.join(new_obd_path, filename)
                        except Exception:
                            new_file = os.path.join(new_obd_path, filename)
                    else:
                        # Preserve existing folder structure
                        new_subdir = os.path.join(new_obd_path, rel_path)
                        os.makedirs(new_subdir, exist_ok=True)
                        new_file = os.path.join(new_subdir, filename)

                    # Copy file (don't delete original for safety)
                    try:
                        shutil.copy2(old_file, new_file)
                        count += 1
                    except Exception as e:
                        logger.warning(f"Failed to copy {old_file}: {e}")

        return count

    def _migrate_prediction_data(self, profile_id: Any, new_folder: str) -> int:
        """Migrate prediction files to new location."""
        count = 0
        old_pred_path = os.path.join(self.old_paths['predictions'], str(profile_id))

        if not os.path.exists(old_pred_path):
            return 0

        new_pred_path = os.path.join(new_folder, 'predictions')
        os.makedirs(new_pred_path, exist_ok=True)

        for filename in os.listdir(old_pred_path):
            if filename.endswith('.json'):
                old_file = os.path.join(old_pred_path, filename)
                new_file = os.path.join(new_pred_path, filename)

                try:
                    shutil.copy2(old_file, new_file)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to copy {old_file}: {e}")

        return count

    def _migrate_baseline_data(self, profile_id: Any, new_folder: str):
        """Migrate AI baseline data."""
        old_baseline_file = os.path.join(
            self.old_paths['baselines'],
            f"{profile_id}_baseline.json"
        )

        if not os.path.exists(old_baseline_file):
            return

        new_baseline_path = os.path.join(new_folder, 'ai_data')
        os.makedirs(new_baseline_path, exist_ok=True)

        new_file = os.path.join(new_baseline_path, 'baseline.json')

        try:
            shutil.copy2(old_baseline_file, new_file)
            logger.debug(f"Migrated baseline for {profile_id}")
        except Exception as e:
            logger.warning(f"Failed to copy baseline {old_baseline_file}: {e}")

    def run_migration(self) -> Dict[str, Any]:
        """
        Run the full migration process.

        Returns migration results and statistics.
        """
        logger.info("=" * 60)
        logger.info("Starting Vehicle Data Migration")
        logger.info(f"Base path: {self.base_path}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 60)

        # Step 1: Discover vehicles from database
        logger.info("\nStep 1: Discovering vehicles from database...")
        db_vehicles = self.discover_vehicles_from_database()

        # Step 2: Discover vehicles from files
        logger.info("\nStep 2: Discovering vehicles from files...")
        file_vehicles = self.discover_vehicles_from_files()

        # Step 3: Merge and deduplicate
        logger.info("\nStep 3: Merging vehicle lists...")
        all_vehicles = self._merge_vehicles(db_vehicles, file_vehicles)
        self.stats['vehicles_found'] = len(all_vehicles)

        logger.info(f"Total unique vehicles to migrate: {len(all_vehicles)}")

        # Step 4: Migrate each vehicle
        logger.info("\nStep 4: Migrating vehicles...")
        for i, vehicle in enumerate(all_vehicles, 1):
            logger.info(f"\n[{i}/{len(all_vehicles)}] Processing vehicle...")
            self.migrate_vehicle(vehicle)

        # Step 5: Generate summary
        logger.info("\n" + "=" * 60)
        logger.info("Migration Complete")
        logger.info("=" * 60)
        logger.info(f"Vehicles found:    {self.stats['vehicles_found']}")
        logger.info(f"Vehicles migrated: {self.stats['vehicles_migrated']}")
        logger.info(f"Vehicles skipped:  {self.stats['vehicles_skipped']}")
        logger.info(f"Vehicles failed:   {self.stats['vehicles_failed']}")
        logger.info(f"OBD files moved:   {self.stats['obd_files_moved']}")
        logger.info(f"Prediction files:  {self.stats['prediction_files_moved']}")

        if self.stats['errors']:
            logger.warning(f"\nErrors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:
                logger.warning(f"  - Vehicle {error['vehicle_id']}: {error['error']}")

        # Save migration report
        if not self.dry_run:
            self._save_migration_report()

        return self.stats

    def _merge_vehicles(
        self,
        db_vehicles: List[Dict],
        file_vehicles: List[Dict]
    ) -> List[Dict]:
        """Merge vehicle lists and remove duplicates."""
        merged = {}

        # Database vehicles take priority
        for v in db_vehicles:
            pid = v.get('profile_id')
            if pid:
                merged[str(pid)] = v

        # Add file vehicles if not already present
        for v in file_vehicles:
            pid = v.get('profile_id')
            if pid and str(pid) not in merged:
                merged[str(pid)] = v

        return list(merged.values())

    def _save_migration_report(self):
        """Save migration report to file."""
        report_path = os.path.join(self.base_path, 'migration_report.json')

        report = {
            'migration_timestamp': datetime.now().isoformat(),
            'statistics': self.stats,
            'base_path': self.base_path
        }

        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            logger.info(f"\nMigration report saved to: {report_path}")
        except Exception as e:
            logger.error(f"Failed to save migration report: {e}")


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description='Migrate vehicle data to organized folder structure'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--base-path',
        default='./PredictData',
        help='Base data path (default: ./PredictData)'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run migration
    migrator = VehicleDataMigrator(
        base_path=args.base_path,
        dry_run=args.dry_run
    )

    results = migrator.run_migration()

    # Exit with error code if any failures
    if results['vehicles_failed'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
