"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Directory Manager

Predict OBD - Directory Manager
Handles first-run setup, directory creation, and integrity verification.

This module ensures the application is self-deploying:
- Creates all required directories on first run
- Verifies directory structure on subsequent runs
- Repairs missing directories without duplication
- Handles edge cases and corruption recovery
"""

import os
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from config import get_config, PredictConfig

logger = logging.getLogger(__name__)


class DirectoryManager:
    """
    Manages application directory structure.
    Ensures idempotent creation and verification.
    """

    def __init__(self, config: Optional[PredictConfig] = None):
        self.config = config or get_config()
        self._installation_started = False

    def initialize(self) -> bool:
        """
        Main entry point - initialize the application directory structure.

        Returns True if initialization successful, False otherwise.
        """
        try:
            if self.is_first_run():
                logger.info("First run detected - performing full installation")
                return self._perform_first_run()
            else:
                logger.info("Existing installation detected - verifying integrity")
                return self._verify_and_repair()

        except Exception as e:
            logger.error(f"Directory initialization failed: {e}")
            return False

    def is_first_run(self) -> bool:
        """
        Check if this is the first application run.

        Returns True if installation.json doesn't exist or is incomplete.
        """
        installation_file = self.config.INSTALLATION_FILE

        if not installation_file.exists():
            return True

        try:
            with open(installation_file, 'r') as f:
                data = json.load(f)
                return not data.get('installation_complete', False)
        except (json.JSONDecodeError, IOError):
            # Corrupted file - treat as first run
            logger.warning("Corrupted installation.json - treating as first run")
            return True

    def _perform_first_run(self) -> bool:
        """
        Perform complete first-run installation.

        Steps:
        1. Create all required directories
        2. Migrate existing data from legacy locations
        3. Create all required files with defaults
        4. Mark installation as complete
        """
        logger.info("=" * 50)
        logger.info("FIRST RUN INSTALLATION")
        logger.info("=" * 50)
        logger.info(f"Root directory: {self.config.ROOT_DIR}")
        logger.info(f"Data directory: {self.config.DATA_DIR}")

        # Step 1: Create directories
        logger.info("Step 1: Creating directory structure...")
        dirs_created, dirs_existed = self._create_all_directories()
        logger.info(f"  Created: {dirs_created}, Already existed: {dirs_existed}")

        # Step 2: Migrate legacy data
        logger.info("Step 2: Migrating legacy data...")
        migrated = self._migrate_legacy_data()
        logger.info(f"  Migrated {migrated} files")

        # Step 3: Create files (only if not migrated)
        logger.info("Step 3: Creating required files...")
        files_created, files_existed = self._create_all_files()
        logger.info(f"  Created: {files_created}, Already existed: {files_existed}")

        # Step 4: Mark installation complete
        logger.info("Step 4: Finalizing installation...")
        self._finalize_installation()

        # Step 5: Clean temp directory
        logger.info("Step 5: Cleaning temporary directory...")
        self._clean_temp_directory()

        logger.info("=" * 50)
        logger.info("INSTALLATION COMPLETE")
        logger.info("=" * 50)

        return True

    def _migrate_legacy_data(self) -> int:
        """
        Migrate data from legacy locations to new structure.
        Returns count of migrated files.
        """
        migrated = 0

        # Legacy paths to check and migrate
        legacy_migrations = [
            # (legacy_path, new_path, description)
            (
                self.config.ROOT_DIR / "config" / "api_keys.json",
                self.config.API_KEYS_FILE,
                "API keys configuration"
            ),
            (
                self.config.get_customer_api_keys_dir("default"),
                self.config.get_customer_api_keys_dir("default"),
                "API key backup files"
            ),
            (
                self.config.ROOT_DIR / "data" / "pdf_queue.json",
                self.config.REPORTS_QUEUE_FILE,
                "PDF queue file"
            ),
        ]

        for legacy_path, new_path, description in legacy_migrations:
            if not legacy_path.exists():
                continue

            if new_path.exists():
                logger.debug(f"  {description}: Already exists at new location, skipping")
                continue

            try:
                # Ensure parent directory exists
                new_path.parent.mkdir(parents=True, exist_ok=True)

                if legacy_path.is_file():
                    # Copy file (don't move - keep legacy for rollback)
                    shutil.copy2(str(legacy_path), str(new_path))
                    logger.info(f"  Migrated {description}: {legacy_path} -> {new_path}")
                    migrated += 1
                elif legacy_path.is_dir():
                    # Copy directory contents
                    for item in legacy_path.iterdir():
                        dest = new_path / item.name
                        if item.is_file() and not dest.exists():
                            shutil.copy2(str(item), str(dest))
                            migrated += 1
                    logger.info(f"  Migrated {description}: {legacy_path} -> {new_path}")

            except Exception as e:
                logger.warning(f"  Failed to migrate {description}: {e}")

        return migrated

    def _verify_and_repair(self) -> bool:
        """
        Verify existing installation and repair if needed.

        Steps:
        1. Verify all directories exist
        2. Repair any missing directories
        3. Verify critical files exist
        4. Clean temporary data
        5. Check for version upgrade
        """
        logger.info("Verifying installation integrity...")

        issues_found = 0
        issues_repaired = 0

        # Verify directories
        for directory in self.config.get_required_directories():
            if not directory.exists():
                logger.warning(f"Missing directory: {directory}")
                issues_found += 1

                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    logger.info(f"  Repaired: {directory}")
                    issues_repaired += 1
                except Exception as e:
                    logger.error(f"  Failed to repair: {e}")

            elif not directory.is_dir():
                # Path exists but is not a directory
                logger.error(f"Path exists but is not a directory: {directory}")
                issues_found += 1

                # Rename the file and create directory
                corrupted_path = directory.with_suffix(
                    f".corrupt.{datetime.now().strftime('%Y%m%dT%H%M%S')}"
                )
                try:
                    shutil.move(str(directory), str(corrupted_path))
                    directory.mkdir(parents=True, exist_ok=True)
                    logger.info(f"  Repaired (renamed corrupt file): {directory}")
                    issues_repaired += 1
                except Exception as e:
                    logger.error(f"  Failed to repair: {e}")

        # Verify critical files
        required_files = self.config.get_required_files()
        for filepath, default_content in required_files.items():
            if not filepath.exists():
                logger.warning(f"Missing file: {filepath}")
                issues_found += 1

                try:
                    # Ensure parent directory exists
                    filepath.parent.mkdir(parents=True, exist_ok=True)

                    # Create file with defaults
                    with open(filepath, 'w') as f:
                        json.dump(default_content, f, indent=2)
                    logger.info(f"  Repaired: {filepath}")
                    issues_repaired += 1
                except Exception as e:
                    logger.error(f"  Failed to repair: {e}")

        # Clean temp directory
        self._clean_temp_directory()

        # Check for version upgrade
        self._check_version_upgrade()

        if issues_found > 0:
            logger.info(f"Found {issues_found} issues, repaired {issues_repaired}")
        else:
            logger.info("Installation integrity verified - no issues found")

        return issues_found == issues_repaired

    def _create_all_directories(self) -> Tuple[int, int]:
        """
        Create all required directories.

        Returns tuple of (created_count, existed_count).
        """
        created = 0
        existed = 0

        for directory in self.config.get_required_directories():
            if directory.exists():
                if directory.is_dir():
                    logger.debug(f"Directory exists: {directory}")
                    existed += 1
                else:
                    # Path exists but is a file - handle as corruption
                    logger.warning(f"Path is file, not directory: {directory}")
                    corrupted_path = directory.with_suffix(
                        f".corrupt.{datetime.now().strftime('%Y%m%dT%H%M%S')}"
                    )
                    shutil.move(str(directory), str(corrupted_path))
                    directory.mkdir(parents=True, exist_ok=True)
                    created += 1
            else:
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {directory}")
                    created += 1
                except PermissionError:
                    logger.error(f"Permission denied creating directory: {directory}")
                    raise
                except Exception as e:
                    logger.error(f"Failed to create directory {directory}: {e}")
                    raise

        return created, existed

    def _create_all_files(self) -> Tuple[int, int]:
        """
        Create all required files with default content.

        Returns tuple of (created_count, existed_count).
        """
        created = 0
        existed = 0

        required_files = self.config.get_required_files()

        for filepath, default_content in required_files.items():
            if filepath.exists():
                logger.debug(f"File exists: {filepath}")
                existed += 1
            else:
                try:
                    # Ensure parent directory exists
                    filepath.parent.mkdir(parents=True, exist_ok=True)

                    # Special handling for installation file
                    if filepath == self.config.INSTALLATION_FILE:
                        default_content = default_content.copy()
                        default_content['installed_at'] = datetime.now().isoformat()
                        default_content['installation_complete'] = False

                    # Write file
                    with open(filepath, 'w') as f:
                        json.dump(default_content, f, indent=2)
                    logger.info(f"Created file: {filepath}")
                    created += 1

                except PermissionError:
                    logger.error(f"Permission denied creating file: {filepath}")
                    raise
                except Exception as e:
                    logger.error(f"Failed to create file {filepath}: {e}")
                    raise

        return created, existed

    def _finalize_installation(self) -> None:
        """Mark installation as complete in installation.json"""
        installation_file = self.config.INSTALLATION_FILE

        try:
            with open(installation_file, 'r') as f:
                data = json.load(f)

            data['installation_complete'] = True
            data['completed_at'] = datetime.now().isoformat()
            data['version'] = self.config.APP_VERSION
            data['schema_version'] = self.config.SCHEMA_VERSION

            with open(installation_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info("Installation marked as complete")

        except Exception as e:
            logger.error(f"Failed to finalize installation: {e}")
            raise

    def _clean_temp_directory(self) -> None:
        """Clean all contents of the temp directory"""
        temp_dir = self.config.TEMP_DIR

        if not temp_dir.exists():
            return

        try:
            for item in temp_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)

            logger.info("Temporary directory cleaned")

        except Exception as e:
            logger.warning(f"Failed to fully clean temp directory: {e}")

    def _check_version_upgrade(self) -> None:
        """Check if application version has changed and handle migration"""
        installation_file = self.config.INSTALLATION_FILE

        if not installation_file.exists():
            return

        try:
            with open(installation_file, 'r') as f:
                data = json.load(f)

            installed_version = data.get('version', '0.0.0')
            installed_schema = data.get('schema_version', '0')

            if installed_version != self.config.APP_VERSION:
                logger.info(f"Version upgrade detected: {installed_version} -> {self.config.APP_VERSION}")
                # Update version in installation file
                data['version'] = self.config.APP_VERSION
                data['last_upgraded'] = datetime.now().isoformat()
                data['upgrade_history'] = data.get('upgrade_history', [])
                data['upgrade_history'].append({
                    'from': installed_version,
                    'to': self.config.APP_VERSION,
                    'at': datetime.now().isoformat()
                })

                with open(installation_file, 'w') as f:
                    json.dump(data, f, indent=2)

            if installed_schema != self.config.SCHEMA_VERSION:
                logger.warning(f"Schema version mismatch: {installed_schema} -> {self.config.SCHEMA_VERSION}")
                logger.warning("Schema migration may be required")
                # Future: Trigger schema migration here

        except Exception as e:
            logger.error(f"Failed to check version upgrade: {e}")

    def get_directory_status(self) -> Dict[str, dict]:
        """
        Get status of all required directories.
        Useful for diagnostics and health checks.
        """
        status = {}

        for directory in self.config.get_required_directories():
            relative_path = str(directory.relative_to(self.config.DATA_DIR))
            status[relative_path] = {
                'path': str(directory),
                'exists': directory.exists(),
                'is_directory': directory.is_dir() if directory.exists() else None,
                'writable': os.access(directory, os.W_OK) if directory.exists() else None
            }

        return status

    def get_file_status(self) -> Dict[str, dict]:
        """
        Get status of all required files.
        Useful for diagnostics and health checks.
        """
        status = {}

        for filepath in self.config.get_required_files().keys():
            try:
                relative_path = str(filepath.relative_to(self.config.DATA_DIR))
            except ValueError:
                relative_path = str(filepath)

            file_status = {
                'path': str(filepath),
                'exists': filepath.exists(),
                'valid_json': None,
                'size_bytes': None
            }

            if filepath.exists():
                file_status['size_bytes'] = filepath.stat().st_size
                try:
                    with open(filepath, 'r') as f:
                        json.load(f)
                    file_status['valid_json'] = True
                except json.JSONDecodeError:
                    file_status['valid_json'] = False
                except:
                    file_status['valid_json'] = None

            status[relative_path] = file_status

        return status

    def create_customer(self, customer_id: str) -> Path:
        """
        Create directory structure for a new customer.

        Returns the customer directory path.
        """
        customer_dir = self.config.get_customer_dir(customer_id)

        # Create customer directories
        directories = [
            customer_dir,
            self.config.get_customer_vehicles_dir(customer_id),
            self.config.get_customer_api_keys_dir(customer_id),
            self.config.get_customer_exports_dir(customer_id),
            self.config.get_customer_reports_dir(customer_id),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        # Create customer profile
        profile_file = self.config.get_customer_profile(customer_id)
        if not profile_file.exists():
            with open(profile_file, 'w') as f:
                json.dump({
                    'customer_id': customer_id,
                    'created_at': datetime.now().isoformat(),
                    'status': 'active'
                }, f, indent=2)

        # Create subscription file with complete structure
        subscription_file = self.config.get_customer_subscription(customer_id)
        if not subscription_file.exists():
            import secrets
            timestamp = datetime.now()
            subscription_id = f"sub_{customer_id}_{timestamp.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"

            with open(subscription_file, 'w') as f:
                json.dump({
                    'subscription_id': subscription_id,
                    'customer_id': customer_id,
                    'plan': 'pending',
                    'status': 'pending',
                    'created_at': timestamp.isoformat(),
                    'start_date': None,
                    'end_date': None,
                    'auto_renew': False,
                    'payment_status': 'pending',
                    'license_key': None,
                    'features': {},
                    'metadata': {},
                    'audit_log': []
                }, f, indent=2)

        logger.info(f"Created customer directory structure: {customer_id}")
        return customer_dir

    def create_vehicle(self, customer_id: str, vehicle_id: str) -> Path:
        """
        Create directory structure for a new vehicle.

        Returns the vehicle directory path.
        """
        vehicle_dir = self.config.get_vehicle_dir(customer_id, vehicle_id)

        # Create vehicle directories
        directories = [
            vehicle_dir,
            self.config.get_vehicle_obd_dir(customer_id, vehicle_id),
            self.config.get_vehicle_obd_dir(customer_id, vehicle_id) / "aggregates",
            self.config.get_vehicle_trips_dir(customer_id, vehicle_id),
            self.config.get_vehicle_service_dir(customer_id, vehicle_id),
            self.config.get_vehicle_predictions_dir(customer_id, vehicle_id),
            self.config.get_vehicle_feedback_dir(customer_id, vehicle_id),
            self.config.get_vehicle_reports_dir(customer_id, vehicle_id),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        # Create vehicle profile
        profile_file = vehicle_dir / "profile.json"
        if not profile_file.exists():
            with open(profile_file, 'w') as f:
                json.dump({
                    'vehicle_id': vehicle_id,
                    'customer_id': customer_id,
                    'created_at': datetime.now().isoformat()
                }, f, indent=2)

        # Create service files
        service_dir = self.config.get_vehicle_service_dir(customer_id, vehicle_id)
        for filename in ['oil_changes.json', 'dtc_history.json', 'maintenance.json']:
            filepath = service_dir / filename
            if not filepath.exists():
                with open(filepath, 'w') as f:
                    json.dump({'records': []}, f, indent=2)

        logger.info(f"Created vehicle directory structure: {customer_id}/{vehicle_id}")
        return vehicle_dir

    def delete_customer(self, customer_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a customer and all their data.

        If soft_delete=True, renames the folder for 30-day recovery.
        If soft_delete=False, permanently deletes all data.
        """
        customer_dir = self.config.get_customer_dir(customer_id)

        if not customer_dir.exists():
            logger.warning(f"Customer directory does not exist: {customer_id}")
            return False

        try:
            if soft_delete:
                # Rename for soft delete
                timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
                deleted_name = f"{customer_id}_deleted_{timestamp}"
                deleted_dir = self.config.CUSTOMERS_DIR / deleted_name
                shutil.move(str(customer_dir), str(deleted_dir))
                logger.info(f"Soft deleted customer: {customer_id} -> {deleted_name}")
            else:
                # Permanent delete
                shutil.rmtree(customer_dir)
                logger.info(f"Permanently deleted customer: {customer_id}")

            # Also handle customer reports
            customer_reports = self.config.get_customer_reports_dir(customer_id)
            if customer_reports.exists():
                if soft_delete:
                    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
                    deleted_reports = self.config.REPORTS_DIR / f"{customer_id}_deleted_{timestamp}"
                    shutil.move(str(customer_reports), str(deleted_reports))
                else:
                    shutil.rmtree(customer_reports)

            return True

        except Exception as e:
            logger.error(f"Failed to delete customer {customer_id}: {e}")
            return False


# ==================== MODULE-LEVEL FUNCTIONS ====================

def initialize_directories() -> bool:
    """
    Initialize application directories.
    Call this at application startup.
    """
    manager = DirectoryManager()
    return manager.initialize()


def get_health_status() -> Dict[str, any]:
    """Get health status of directory structure"""
    manager = DirectoryManager()
    return {
        'directories': manager.get_directory_status(),
        'files': manager.get_file_status(),
        'is_first_run': manager.is_first_run()
    }


# ==================== MAIN (for testing) ====================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Testing Directory Manager...")
    print("=" * 60)

    # Initialize
    success = initialize_directories()
    print(f"\nInitialization: {'SUCCESS' if success else 'FAILED'}")

    # Show status
    print("\n" + "=" * 60)
    print("Health Status:")
    status = get_health_status()

    print(f"\nIs first run: {status['is_first_run']}")

    print("\nDirectories:")
    for path, info in status['directories'].items():
        status_icon = "[OK]" if info['exists'] and info['is_directory'] else "[!!]"
        print(f"  {status_icon} {path}")

    print("\nFiles:")
    for path, info in status['files'].items():
        status_icon = "[OK]" if info['exists'] and info.get('valid_json') else "[!!]"
        print(f"  {status_icon} {path}")
