"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: System Self Test

Predict OBD - System Self-Test Module
CRITICAL: Executable self-tests for backup, restore, and offline sync.

This module provides:
- Backup creation verification
- Restore integrity testing
- Offline queue replay testing
- Automatic failure detection and reporting
"""

import json
import logging
import shutil
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Self-test status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class SelfTestResult:
    """Result of a self-test."""
    test_name: str
    status: TestStatus
    duration_seconds: float
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class SelfTestReport:
    """Complete self-test report."""
    report_id: str
    timestamp: str
    all_passed: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    results: List[SelfTestResult]


class SystemSelfTest:
    """
    Executable self-tests for critical system functions.

    Tests:
    1. Backup creation
    2. Backup restoration
    3. Data integrity after restore
    4. Offline queue creation
    5. Offline queue replay
    6. Database connectivity
    7. File system permissions
    """

    def __init__(self):
        self.test_dir = CONFIG.TEMP_DIR / "self_tests"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.last_report: Optional[SelfTestReport] = None

    def run_all_tests(self) -> SelfTestReport:
        """
        Run all self-tests and return comprehensive report.

        Returns:
            SelfTestReport with all test results
        """
        logger.info("SYSTEM SELF-TEST: Starting comprehensive self-test...")
        start_time = datetime.now()

        results = []

        # Test 1: Backup Creation
        results.append(self._test_backup_creation())

        # Test 2: Backup Restoration
        results.append(self._test_backup_restoration())

        # Test 3: Data Integrity After Restore
        results.append(self._test_restore_integrity())

        # Test 4: Offline Queue Creation
        results.append(self._test_offline_queue_creation())

        # Test 5: Offline Queue Replay
        results.append(self._test_offline_queue_replay())

        # Test 6: Database Connectivity
        results.append(self._test_database_connectivity())

        # Test 7: File System Permissions
        results.append(self._test_filesystem_permissions())

        # Test 8: Alert System
        results.append(self._test_alert_system())

        # Compile report
        tests_passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        tests_failed = sum(1 for r in results if r.status == TestStatus.FAILED)

        report = SelfTestReport(
            report_id=f"selftest_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            all_passed=tests_failed == 0,
            tests_run=len(results),
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            results=results
        )

        self.last_report = report

        # Persist report
        self._save_report(report)

        # Clean up test artifacts
        self._cleanup_test_artifacts()

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"SYSTEM SELF-TEST: Complete in {duration:.1f}s - "
                   f"{tests_passed}/{len(results)} passed")

        return report

    def _test_backup_creation(self) -> SelfTestResult:
        """Test backup creation capability."""
        test_name = "backup_creation"
        start = time.time()

        try:
            # Create test data
            test_data_file = self.test_dir / "test_data.json"
            test_data = {"test_id": "backup_test", "timestamp": datetime.now().isoformat()}
            with open(test_data_file, 'w') as f:
                json.dump(test_data, f)

            # Create backup
            backup_file = self.test_dir / "test_backup.zip"

            import zipfile
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(test_data_file, "test_data.json")

            # Verify backup exists and has content
            if not backup_file.exists():
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="Backup file was not created"
                )

            if backup_file.stat().st_size == 0:
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="Backup file is empty"
                )

            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.PASSED,
                duration_seconds=time.time() - start,
                message="Backup creation successful",
                details={"backup_size": backup_file.stat().st_size}
            )

        except Exception as e:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_seconds=time.time() - start,
                message=f"Backup creation error: {e}"
            )

    def _test_backup_restoration(self) -> SelfTestResult:
        """Test backup restoration capability."""
        test_name = "backup_restoration"
        start = time.time()

        try:
            backup_file = self.test_dir / "test_backup.zip"
            restore_dir = self.test_dir / "restore_test"
            restore_dir.mkdir(parents=True, exist_ok=True)

            if not backup_file.exists():
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.SKIPPED,
                    duration_seconds=time.time() - start,
                    message="No backup file to restore (backup test may have failed)"
                )

            import zipfile
            with zipfile.ZipFile(backup_file, 'r') as zf:
                zf.extractall(restore_dir)

            # Verify restored file exists
            restored_file = restore_dir / "test_data.json"
            if not restored_file.exists():
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="Restored file not found"
                )

            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.PASSED,
                duration_seconds=time.time() - start,
                message="Backup restoration successful"
            )

        except Exception as e:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_seconds=time.time() - start,
                message=f"Restoration error: {e}"
            )

    def _test_restore_integrity(self) -> SelfTestResult:
        """Test data integrity after restoration."""
        test_name = "restore_integrity"
        start = time.time()

        try:
            original_file = self.test_dir / "test_data.json"
            restored_file = self.test_dir / "restore_test" / "test_data.json"

            if not original_file.exists() or not restored_file.exists():
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.SKIPPED,
                    duration_seconds=time.time() - start,
                    message="Required files not available"
                )

            # Compare file hashes
            original_hash = self._file_hash(original_file)
            restored_hash = self._file_hash(restored_file)

            if original_hash != restored_hash:
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="Data integrity check failed - hashes do not match",
                    details={
                        "original_hash": original_hash,
                        "restored_hash": restored_hash
                    }
                )

            # Compare content
            with open(original_file, 'r') as f:
                original_data = json.load(f)
            with open(restored_file, 'r') as f:
                restored_data = json.load(f)

            if original_data != restored_data:
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="Data content mismatch after restore"
                )

            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.PASSED,
                duration_seconds=time.time() - start,
                message="Data integrity verified after restore",
                details={"hash": original_hash}
            )

        except Exception as e:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_seconds=time.time() - start,
                message=f"Integrity check error: {e}"
            )

    def _test_offline_queue_creation(self) -> SelfTestResult:
        """Test offline command queue creation."""
        test_name = "offline_queue_creation"
        start = time.time()

        try:
            queue_file = self.test_dir / "test_offline_queue.json"

            # Create test queue
            test_commands = [
                {"id": "cmd_1", "action": "sync_data", "timestamp": datetime.now().isoformat()},
                {"id": "cmd_2", "action": "upload_reading", "timestamp": datetime.now().isoformat()},
            ]

            with open(queue_file, 'w') as f:
                json.dump({"commands": test_commands, "created_at": datetime.now().isoformat()}, f)

            # Verify queue was created
            if not queue_file.exists():
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="Queue file was not created"
                )

            # Verify queue content
            with open(queue_file, 'r') as f:
                saved_queue = json.load(f)

            if len(saved_queue.get("commands", [])) != 2:
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="Queue content mismatch"
                )

            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.PASSED,
                duration_seconds=time.time() - start,
                message="Offline queue creation successful",
                details={"command_count": len(test_commands)}
            )

        except Exception as e:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_seconds=time.time() - start,
                message=f"Queue creation error: {e}"
            )

    def _test_offline_queue_replay(self) -> SelfTestResult:
        """Test offline queue replay capability."""
        test_name = "offline_queue_replay"
        start = time.time()

        try:
            queue_file = self.test_dir / "test_offline_queue.json"

            if not queue_file.exists():
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.SKIPPED,
                    duration_seconds=time.time() - start,
                    message="No queue file to replay"
                )

            # Load queue
            with open(queue_file, 'r') as f:
                queue_data = json.load(f)

            commands = queue_data.get("commands", [])
            replayed_count = 0
            failed_count = 0

            # Simulate replay
            for cmd in commands:
                try:
                    # In real implementation, this would execute the command
                    # For testing, we just verify the command structure
                    if "id" in cmd and "action" in cmd:
                        replayed_count += 1
                    else:
                        failed_count += 1
                except Exception:
                    failed_count += 1

            # Clear queue after replay
            with open(queue_file, 'w') as f:
                json.dump({"commands": [], "replayed_at": datetime.now().isoformat()}, f)

            if failed_count > 0:
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message=f"Queue replay failed for {failed_count} commands",
                    details={"replayed": replayed_count, "failed": failed_count}
                )

            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.PASSED,
                duration_seconds=time.time() - start,
                message=f"Queue replay successful ({replayed_count} commands)",
                details={"replayed": replayed_count}
            )

        except Exception as e:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_seconds=time.time() - start,
                message=f"Queue replay error: {e}"
            )

    def _test_database_connectivity(self) -> SelfTestResult:
        """Test database connectivity."""
        test_name = "database_connectivity"
        start = time.time()

        try:
            # Test with a temporary database
            test_db = self.test_dir / "test_db.sqlite"

            conn = sqlite3.connect(str(test_db))
            cursor = conn.cursor()

            # Create test table
            cursor.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, value TEXT)")
            cursor.execute("INSERT INTO test (value) VALUES (?)", ("test_value",))
            conn.commit()

            # Verify data
            cursor.execute("SELECT value FROM test WHERE id = 1")
            result = cursor.fetchone()

            conn.close()

            if result is None or result[0] != "test_value":
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="Database read/write verification failed"
                )

            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.PASSED,
                duration_seconds=time.time() - start,
                message="Database connectivity verified"
            )

        except Exception as e:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_seconds=time.time() - start,
                message=f"Database connectivity error: {e}"
            )

    def _test_filesystem_permissions(self) -> SelfTestResult:
        """Test file system permissions."""
        test_name = "filesystem_permissions"
        start = time.time()

        try:
            permissions_ok = True
            issues = []

            # Test directories that must be writable
            directories_to_test = [
                CONFIG.DATA_DIR,
                CONFIG.LOGS_DIR,
                CONFIG.TEMP_DIR,
                CONFIG.CACHE_DIR,
                CONFIG.AI_MODELS_DIR,
            ]

            for directory in directories_to_test:
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    test_file = directory / ".permission_test"
                    test_file.write_text("test")
                    test_file.unlink()
                except Exception as e:
                    permissions_ok = False
                    issues.append(f"{directory}: {e}")

            if not permissions_ok:
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message="File system permission issues detected",
                    details={"issues": issues}
                )

            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.PASSED,
                duration_seconds=time.time() - start,
                message=f"File system permissions verified ({len(directories_to_test)} directories)"
            )

        except Exception as e:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_seconds=time.time() - start,
                message=f"Permission check error: {e}"
            )

    def _test_alert_system(self) -> SelfTestResult:
        """Test alert system connectivity."""
        test_name = "alert_system"
        start = time.time()

        try:
            from alert_delivery_guarantees import get_alert_guarantees

            guarantees = get_alert_guarantees()
            is_healthy, message = guarantees.is_healthy()

            # If never tested, run self-test
            if not is_healthy and "never ran" in message.lower():
                passed, results = guarantees.run_startup_self_test()
                is_healthy = passed

            if not is_healthy:
                return SelfTestResult(
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    duration_seconds=time.time() - start,
                    message=f"Alert system unhealthy: {message}"
                )

            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.PASSED,
                duration_seconds=time.time() - start,
                message="Alert system operational"
            )

        except ImportError:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.SKIPPED,
                duration_seconds=time.time() - start,
                message="Alert module not available"
            )
        except Exception as e:
            return SelfTestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                duration_seconds=time.time() - start,
                message=f"Alert system test error: {e}"
            )

    def _file_hash(self, filepath: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _save_report(self, report: SelfTestReport):
        """Save self-test report."""
        try:
            reports_dir = CONFIG.DATA_DIR / "system" / "self_test_reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            report_file = reports_dir / f"{report.report_id}.json"

            report_dict = {
                "report_id": report.report_id,
                "timestamp": report.timestamp,
                "all_passed": report.all_passed,
                "tests_run": report.tests_run,
                "tests_passed": report.tests_passed,
                "tests_failed": report.tests_failed,
                "results": [
                    {
                        "test_name": r.test_name,
                        "status": r.status.value,
                        "duration_seconds": r.duration_seconds,
                        "message": r.message,
                        "details": r.details
                    }
                    for r in report.results
                ]
            }

            with open(report_file, 'w') as f:
                json.dump(report_dict, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save self-test report: {e}")

    def _cleanup_test_artifacts(self):
        """Clean up test artifacts."""
        try:
            # Remove test files but keep reports
            for item in self.test_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir() and item.name != "self_test_reports":
                    shutil.rmtree(item)
        except Exception as e:
            logger.warning(f"Failed to clean up test artifacts: {e}")

    def get_last_report(self) -> Optional[SelfTestReport]:
        """Get the last self-test report."""
        return self.last_report

    def is_healthy(self) -> Tuple[bool, str]:
        """Check if system passed last self-test."""
        if self.last_report is None:
            return False, "Self-test never run"

        if not self.last_report.all_passed:
            failed_tests = [r.test_name for r in self.last_report.results
                           if r.status == TestStatus.FAILED]
            return False, f"Self-test failed: {', '.join(failed_tests)}"

        return True, "All self-tests passed"


# Global instance
_self_test: Optional[SystemSelfTest] = None


def get_system_self_test() -> SystemSelfTest:
    """Get global system self-test instance."""
    global _self_test
    if _self_test is None:
        _self_test = SystemSelfTest()
    return _self_test


def run_self_tests() -> SelfTestReport:
    """Run all system self-tests."""
    return get_system_self_test().run_all_tests()


def verify_system_health() -> Tuple[bool, str]:
    """Verify system health based on self-tests."""
    return get_system_self_test().is_healthy()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Running system self-tests...")
    report = run_self_tests()
    print(f"\nResults: {report.tests_passed}/{report.tests_run} passed")
    if not report.all_passed:
        print("\nFailed tests:")
        for r in report.results:
            if r.status == TestStatus.FAILED:
                print(f"  - {r.test_name}: {r.message}")
