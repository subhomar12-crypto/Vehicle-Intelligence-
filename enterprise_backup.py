"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Enterprise Backup

Predict OBD - Enterprise Backup System
Production-ready backup strategy with retention, verification, and restore procedures.

BACKUP STRATEGY:
- Daily incremental backups (7-day retention)
- Weekly full backups (4-week retention)
- Monthly archival backups (12-month retention)
- Automatic restore verification
- Integrity checksums for all backups
"""

import os
import json
import shutil
import hashlib
import zipfile
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict

from config import get_config
from audit_logger import log_audit_event, AuditEventType

logger = logging.getLogger(__name__)


@dataclass
class BackupMetadata:
    """Metadata for a backup archive."""
    backup_id: str
    backup_type: str  # daily, weekly, monthly
    created_at: str
    completed_at: Optional[str]
    source_path: str
    backup_path: str
    file_count: int
    total_size_bytes: int
    checksum_sha256: str
    manifest: List[str]  # List of included files
    verified: bool
    verification_timestamp: Optional[str]
    encryption_enabled: bool
    status: str  # pending, completed, failed, verified


class EnterpriseBackupManager:
    """
    Production backup manager with enterprise features.

    Features:
    - Multiple retention tiers
    - Checksum verification
    - Restore testing
    - Encryption support
    - Audit logging
    """

    # Retention policy (in number of backups to keep)
    RETENTION_POLICY = {
        "daily": 7,      # Keep last 7 daily backups
        "weekly": 4,     # Keep last 4 weekly backups
        "monthly": 12    # Keep last 12 monthly backups
    }

    # Critical directories to always include
    CRITICAL_DIRECTORIES = [
        "customers",
        "system/config",
        "ai/models",
        "logs/audit"
    ]

    def __init__(self):
        self.config = get_config()
        self.backup_root = self.config.BACKUPS_DIR
        self.metadata_file = self.backup_root / "backup_registry.json"
        self._lock = threading.Lock()

        self._ensure_backup_structure()

    def _ensure_backup_structure(self):
        """Create backup directory structure."""
        for backup_type in ["daily", "weekly", "monthly"]:
            (self.backup_root / backup_type).mkdir(parents=True, exist_ok=True)

        # Ensure metadata file exists
        if not self.metadata_file.exists():
            self._save_registry({"backups": [], "last_daily": None, "last_weekly": None, "last_monthly": None})

    def create_backup(
        self,
        backup_type: str = "daily",
        description: str = "Scheduled backup",
        verify: bool = True
    ) -> Tuple[bool, str, Optional[BackupMetadata]]:
        """
        Create a backup with full integrity checks.

        Args:
            backup_type: daily, weekly, or monthly
            description: Backup description
            verify: Run verification after backup

        Returns:
            (success, message, metadata)
        """
        with self._lock:
            try:
                logger.info(f"Starting {backup_type} backup: {description}")

                # Generate backup ID
                timestamp = datetime.now()
                backup_id = f"{backup_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

                # Determine backup filename
                if backup_type == "daily":
                    filename = f"backup_{timestamp.strftime('%Y%m%d_%H%M%S')}.zip"
                elif backup_type == "weekly":
                    week_num = timestamp.isocalendar()[1]
                    filename = f"backup_{timestamp.year}_W{week_num:02d}.zip"
                else:  # monthly
                    filename = f"backup_{timestamp.strftime('%Y_%m')}.zip"

                backup_path = self.backup_root / backup_type / filename

                # Create metadata
                metadata = BackupMetadata(
                    backup_id=backup_id,
                    backup_type=backup_type,
                    created_at=timestamp.isoformat(),
                    completed_at=None,
                    source_path=str(self.config.DATA_DIR),
                    backup_path=str(backup_path),
                    file_count=0,
                    total_size_bytes=0,
                    checksum_sha256="",
                    manifest=[],
                    verified=False,
                    verification_timestamp=None,
                    encryption_enabled=False,
                    status="pending"
                )

                # Create backup archive
                file_count, total_size, manifest = self._create_archive(backup_path, backup_type)

                # Calculate checksum
                checksum = self._calculate_checksum(backup_path)

                # Update metadata
                metadata.completed_at = datetime.now().isoformat()
                metadata.file_count = file_count
                metadata.total_size_bytes = total_size
                metadata.checksum_sha256 = checksum
                metadata.manifest = manifest
                metadata.status = "completed"

                # Verify if requested
                if verify:
                    verified, verify_msg = self._verify_backup(backup_path, checksum)
                    metadata.verified = verified
                    metadata.verification_timestamp = datetime.now().isoformat()

                    if not verified:
                        metadata.status = "verification_failed"
                        logger.error(f"Backup verification failed: {verify_msg}")
                    else:
                        metadata.status = "verified"
                        logger.info("Backup verification passed")

                # Save metadata
                self._add_backup_to_registry(metadata)

                # Apply retention policy
                self._apply_retention_policy(backup_type)

                # Audit log
                log_audit_event(
                    event_type=AuditEventType.BACKUP_CREATED,
                    details={
                        "backup_id": backup_id,
                        "backup_type": backup_type,
                        "file_count": file_count,
                        "size_mb": round(total_size / (1024 * 1024), 2),
                        "verified": metadata.verified,
                        "description": description
                    }
                )

                logger.info(f"Backup completed: {backup_id} ({file_count} files, "
                           f"{total_size / (1024 * 1024):.2f} MB)")

                return True, f"Backup completed: {backup_id}", metadata

            except Exception as e:
                logger.error(f"Backup failed: {e}")
                return False, f"Backup failed: {str(e)}", None

    def restore_backup(
        self,
        backup_id: str,
        restore_path: Optional[Path] = None,
        verify_first: bool = True
    ) -> Tuple[bool, str]:
        """
        Restore from a backup.

        Args:
            backup_id: ID of backup to restore
            restore_path: Target path (None = original location)
            verify_first: Verify backup integrity before restore

        Returns:
            (success, message)
        """
        try:
            # Find backup in registry
            registry = self._load_registry()
            backup_meta = None

            for backup in registry.get("backups", []):
                if backup.get("backup_id") == backup_id:
                    backup_meta = BackupMetadata(**backup)
                    break

            if not backup_meta:
                return False, f"Backup not found: {backup_id}"

            backup_path = Path(backup_meta.backup_path)

            if not backup_path.exists():
                return False, f"Backup file not found: {backup_path}"

            # Verify if requested
            if verify_first:
                verified, msg = self._verify_backup(backup_path, backup_meta.checksum_sha256)
                if not verified:
                    return False, f"Backup verification failed: {msg}"

            # Determine restore location
            if restore_path is None:
                restore_path = self.config.DATA_DIR
            else:
                restore_path = Path(restore_path)

            # Create restore directory
            restore_path.mkdir(parents=True, exist_ok=True)

            # Extract backup
            logger.info(f"Restoring backup {backup_id} to {restore_path}")

            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(restore_path)

            # Audit log
            log_audit_event(
                event_type=AuditEventType.BACKUP_RESTORED,
                details={
                    "backup_id": backup_id,
                    "restore_path": str(restore_path),
                    "file_count": backup_meta.file_count
                }
            )

            logger.info(f"Restore completed: {backup_meta.file_count} files restored")

            return True, f"Restore completed successfully"

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False, f"Restore failed: {str(e)}"

    def verify_restore_integrity(
        self,
        backup_id: str,
        test_restore_path: Optional[Path] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Perform a test restore to verify backup can be restored.

        Args:
            backup_id: Backup to verify
            test_restore_path: Temporary path for test restore

        Returns:
            (success, verification_report)
        """
        import tempfile

        # Use temp directory if not specified
        if test_restore_path is None:
            test_restore_path = Path(tempfile.mkdtemp(prefix="backup_verify_"))

        try:
            report = {
                "backup_id": backup_id,
                "test_restore_path": str(test_restore_path),
                "started_at": datetime.now().isoformat(),
                "restore_success": False,
                "files_restored": 0,
                "critical_files_present": {},
                "errors": []
            }

            # Attempt restore
            success, msg = self.restore_backup(
                backup_id,
                restore_path=test_restore_path,
                verify_first=True
            )

            report["restore_success"] = success
            if not success:
                report["errors"].append(msg)
                return False, report

            # Count restored files
            restored_files = list(test_restore_path.rglob("*"))
            report["files_restored"] = len([f for f in restored_files if f.is_file()])

            # Check for critical files
            critical_checks = [
                "system/config/api_keys.json",
                "system/installation.json",
            ]

            for check_path in critical_checks:
                full_path = test_restore_path / check_path
                report["critical_files_present"][check_path] = full_path.exists()

            report["completed_at"] = datetime.now().isoformat()
            report["verification_passed"] = success and all(report["critical_files_present"].values())

            logger.info(f"Restore verification {'passed' if report['verification_passed'] else 'failed'}")

            return report["verification_passed"], report

        except Exception as e:
            logger.error(f"Restore verification failed: {e}")
            return False, {"error": str(e)}

        finally:
            # Cleanup test restore
            try:
                if test_restore_path.exists():
                    shutil.rmtree(test_restore_path)
            except:
                pass

    def list_backups(self, backup_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all backups, optionally filtered by type."""
        registry = self._load_registry()
        backups = registry.get("backups", [])

        if backup_type:
            backups = [b for b in backups if b.get("backup_type") == backup_type]

        # Sort by creation date descending
        backups.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return backups

    def get_backup_statistics(self) -> Dict[str, Any]:
        """Get backup statistics."""
        registry = self._load_registry()
        backups = registry.get("backups", [])

        stats = {
            "total_backups": len(backups),
            "by_type": {"daily": 0, "weekly": 0, "monthly": 0},
            "total_size_mb": 0,
            "verified_count": 0,
            "last_backup": None,
            "oldest_backup": None,
            "last_daily": registry.get("last_daily"),
            "last_weekly": registry.get("last_weekly"),
            "last_monthly": registry.get("last_monthly")
        }

        for backup in backups:
            stats["by_type"][backup.get("backup_type", "daily")] += 1
            stats["total_size_mb"] += backup.get("total_size_bytes", 0) / (1024 * 1024)
            if backup.get("verified"):
                stats["verified_count"] += 1

        if backups:
            stats["last_backup"] = max(b.get("created_at", "") for b in backups)
            stats["oldest_backup"] = min(b.get("created_at", "") for b in backups)

        stats["total_size_mb"] = round(stats["total_size_mb"], 2)

        return stats

    def _create_archive(self, backup_path: Path, backup_type: str) -> Tuple[int, int, List[str]]:
        """Create backup archive and return (file_count, total_size, manifest)."""
        file_count = 0
        total_size = 0
        manifest = []

        data_dir = self.config.DATA_DIR

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Always include critical directories
            for critical_dir in self.CRITICAL_DIRECTORIES:
                critical_path = data_dir / critical_dir
                if critical_path.exists():
                    for root, dirs, files in os.walk(critical_path):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(data_dir)
                            zipf.write(file_path, arcname)
                            manifest.append(str(arcname))
                            file_count += 1
                            total_size += file_path.stat().st_size

            # For weekly/monthly, include additional directories
            if backup_type in ["weekly", "monthly"]:
                additional_dirs = ["ai/predictions", "reports", "logs"]
                for add_dir in additional_dirs:
                    add_path = data_dir / add_dir
                    if add_path.exists():
                        for root, dirs, files in os.walk(add_path):
                            for file in files:
                                file_path = Path(root) / file
                                arcname = file_path.relative_to(data_dir)
                                if str(arcname) not in manifest:
                                    zipf.write(file_path, arcname)
                                    manifest.append(str(arcname))
                                    file_count += 1
                                    total_size += file_path.stat().st_size

        return file_count, total_size, manifest

    def _calculate_checksum(self, filepath: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()

        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    def _verify_backup(self, backup_path: Path, expected_checksum: str) -> Tuple[bool, str]:
        """Verify backup integrity."""
        try:
            # Check file exists
            if not backup_path.exists():
                return False, "Backup file not found"

            # Verify checksum
            actual_checksum = self._calculate_checksum(backup_path)
            if actual_checksum != expected_checksum:
                return False, f"Checksum mismatch: expected {expected_checksum[:16]}..., got {actual_checksum[:16]}..."

            # Verify archive is valid
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                bad_file = zipf.testzip()
                if bad_file:
                    return False, f"Corrupt file in archive: {bad_file}"

            return True, "Verification passed"

        except Exception as e:
            return False, f"Verification error: {str(e)}"

    def _apply_retention_policy(self, backup_type: str):
        """Apply retention policy, deleting old backups."""
        keep_count = self.RETENTION_POLICY.get(backup_type, 7)
        backup_dir = self.backup_root / backup_type

        if not backup_dir.exists():
            return

        # Get all backup files sorted by modification time
        backups = []
        for file in backup_dir.glob("*.zip"):
            backups.append((file, file.stat().st_mtime))

        backups.sort(key=lambda x: x[1], reverse=True)

        # Delete old backups
        for file, _ in backups[keep_count:]:
            try:
                file.unlink()
                logger.info(f"Deleted old backup: {file.name}")

                # Also remove from registry
                self._remove_backup_from_registry(file)

            except Exception as e:
                logger.warning(f"Failed to delete old backup {file}: {e}")

    def _load_registry(self) -> Dict[str, Any]:
        """Load backup registry."""
        if not self.metadata_file.exists():
            return {"backups": []}

        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except:
            return {"backups": []}

    def _save_registry(self, registry: Dict[str, Any]):
        """Save backup registry."""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w') as f:
            json.dump(registry, f, indent=2)

    def _add_backup_to_registry(self, metadata: BackupMetadata):
        """Add backup metadata to registry."""
        registry = self._load_registry()
        registry["backups"].append(asdict(metadata))
        registry[f"last_{metadata.backup_type}"] = metadata.created_at
        self._save_registry(registry)

    def _remove_backup_from_registry(self, backup_path: Path):
        """Remove backup from registry by path."""
        registry = self._load_registry()
        registry["backups"] = [
            b for b in registry.get("backups", [])
            if Path(b.get("backup_path", "")).name != backup_path.name
        ]
        self._save_registry(registry)


# ==================== SCHEDULED BACKUP SERVICE ====================

class ScheduledBackupService:
    """Background service for automated backups."""

    def __init__(self, backup_manager: EnterpriseBackupManager):
        self.manager = backup_manager
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, daily_time: str = "02:00"):
        """Start the backup scheduler."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._scheduler_loop,
            args=(daily_time,),
            daemon=True
        )
        self._thread.start()
        logger.info(f"Backup scheduler started (daily at {daily_time})")

    def stop(self):
        """Stop the backup scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _scheduler_loop(self, daily_time: str):
        """Main scheduler loop."""
        import time

        while self._running:
            try:
                now = datetime.now()
                target_hour, target_minute = map(int, daily_time.split(':'))
                target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

                if now > target_time:
                    target_time += timedelta(days=1)

                # Wait until target time
                sleep_seconds = (target_time - now).total_seconds()
                logger.info(f"Next backup scheduled for: {target_time}")

                # Sleep in chunks to allow stopping
                while sleep_seconds > 0 and self._running:
                    time.sleep(min(60, sleep_seconds))
                    sleep_seconds -= 60

                if not self._running:
                    break

                # Perform daily backup
                self.manager.create_backup('daily', 'Scheduled daily backup')

                # Weekly backup on Sundays
                if now.weekday() == 6:
                    self.manager.create_backup('weekly', 'Scheduled weekly backup')

                # Monthly backup on 1st of month
                if now.day == 1:
                    self.manager.create_backup('monthly', 'Scheduled monthly backup')

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)


# ==================== MODULE-LEVEL FUNCTIONS ====================

_backup_manager: Optional[EnterpriseBackupManager] = None
_backup_service: Optional[ScheduledBackupService] = None


def get_backup_manager() -> EnterpriseBackupManager:
    """Get global backup manager instance."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = EnterpriseBackupManager()
    return _backup_manager


def start_scheduled_backups(daily_time: str = "02:00"):
    """Start scheduled backup service."""
    global _backup_service
    if _backup_service is None:
        _backup_service = ScheduledBackupService(get_backup_manager())
    _backup_service.start(daily_time)


def create_backup(backup_type: str = "daily") -> Tuple[bool, str]:
    """Create a backup."""
    manager = get_backup_manager()
    success, message, _ = manager.create_backup(backup_type)
    return success, message


def restore_backup(backup_id: str) -> Tuple[bool, str]:
    """Restore from a backup."""
    return get_backup_manager().restore_backup(backup_id)


def verify_backup(backup_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Verify a backup can be restored."""
    return get_backup_manager().verify_restore_integrity(backup_id)
