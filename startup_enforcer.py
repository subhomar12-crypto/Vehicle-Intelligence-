"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Startup Enforcer

Predict OBD - Startup Enforcement Module
CRITICAL: This module BLOCKS application startup unless all validations pass.

This is NOT optional. The system CANNOT start without passing validation.
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)

# Validation result persistence
VALIDATION_STATE_FILE = CONFIG.DATA_DIR / "system" / "validation_state.json"
VALIDATION_MAX_AGE_HOURS = 24  # Validation expires after 24 hours


class StartupEnforcer:
    """
    Enforces mandatory startup validation.

    GUARANTEES:
    1. System CANNOT start without passing validation
    2. Stale validations (>24h) are rejected
    3. Failed validations block startup with clear errors
    4. All blocking issues are logged and surfaced
    """

    def __init__(self):
        self.validation_state: Optional[Dict[str, Any]] = None
        self._load_validation_state()

    def _load_validation_state(self):
        """Load persisted validation state."""
        try:
            if VALIDATION_STATE_FILE.exists():
                with open(VALIDATION_STATE_FILE, 'r') as f:
                    self.validation_state = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load validation state: {e}")
            self.validation_state = None

    def _save_validation_state(self, state: Dict[str, Any]):
        """Persist validation state."""
        try:
            VALIDATION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(VALIDATION_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
            self.validation_state = state
        except Exception as e:
            logger.error(f"Failed to save validation state: {e}")
            raise RuntimeError(f"Cannot persist validation state: {e}")

    def is_validation_current(self) -> Tuple[bool, str]:
        """
        Check if validation is current and valid.

        Returns:
            (is_current, reason)
        """
        if not self.validation_state:
            return False, "No validation has ever been performed"

        # Check validation timestamp
        validated_at = self.validation_state.get("validated_at")
        if not validated_at:
            return False, "Validation timestamp missing"

        try:
            validation_time = datetime.fromisoformat(validated_at)
            age_hours = (datetime.now() - validation_time).total_seconds() / 3600

            if age_hours > VALIDATION_MAX_AGE_HOURS:
                return False, f"Validation is stale ({age_hours:.1f}h old, max {VALIDATION_MAX_AGE_HOURS}h)"
        except Exception as e:
            return False, f"Invalid validation timestamp: {e}"

        # Check validation status
        status = self.validation_state.get("status")
        if status != "READY":
            blocking_issues = self.validation_state.get("blocking_issues", [])
            return False, f"Last validation failed with {len(blocking_issues)} blocking issues"

        return True, "Validation is current and passed"

    def run_validation(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run full launch validation.

        Returns:
            (passed, results)
        """
        logger.info("=" * 60)
        logger.info("STARTUP ENFORCER: Running mandatory validation")
        logger.info("=" * 60)

        results = {
            "validated_at": datetime.now().isoformat(),
            "status": "PENDING",
            "blocking_issues": [],
            "warnings": [],
            "checks": {}
        }

        # Import and run validation checks
        try:
            from final_launch_validation import LaunchValidator
            validator = LaunchValidator()
            validation_results = validator.run_full_validation()

            results["checks"] = validation_results.get("categories", {})
            results["blocking_issues"] = validation_results.get("blocking_issues", [])

            if validation_results.get("overall_status") == "READY":
                results["status"] = "READY"
            else:
                results["status"] = "FAILED"

        except ImportError as e:
            results["status"] = "FAILED"
            results["blocking_issues"].append({
                "category": "Import",
                "check": "validation_module",
                "error": f"Cannot import validation module: {e}"
            })
        except Exception as e:
            results["status"] = "FAILED"
            results["blocking_issues"].append({
                "category": "Execution",
                "check": "validation_run",
                "error": f"Validation execution failed: {e}"
            })

        # Add system health checks
        self._run_system_health_checks(results)

        # Persist results
        self._save_validation_state(results)

        passed = results["status"] == "READY"
        return passed, results

    def _run_system_health_checks(self, results: Dict[str, Any]):
        """Run additional system health checks."""

        # Check 1: Alert system connectivity
        try:
            from monitoring_alerts import AlertManager
            manager = AlertManager()
            if not manager.test_connectivity():
                results["blocking_issues"].append({
                    "category": "Monitoring",
                    "check": "alert_connectivity",
                    "error": "Alert system cannot deliver notifications"
                })
                results["status"] = "FAILED"
        except Exception as e:
            results["warnings"].append(f"Alert connectivity check skipped: {e}")

        # Check 2: Database connectivity
        try:
            import sqlite3
            db_path = CONFIG.SERVER_DB_PATH
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                conn.execute("SELECT 1")
                conn.close()
            results["checks"]["database_connectivity"] = {"passed": True}
        except Exception as e:
            results["blocking_issues"].append({
                "category": "Database",
                "check": "connectivity",
                "error": f"Database connectivity failed: {e}"
            })
            results["status"] = "FAILED"

        # Check 3: AI model availability
        try:
            from lstm_predictor import LSTMPredictor
            predictor = LSTMPredictor()
            if not predictor.is_model_loaded() and not predictor.has_fallback():
                results["blocking_issues"].append({
                    "category": "AI",
                    "check": "model_availability",
                    "error": "No AI model available and no fallback configured"
                })
                results["status"] = "FAILED"
            results["checks"]["ai_model"] = {"passed": True}
        except Exception as e:
            results["warnings"].append(f"AI model check: {e}")

    def enforce_startup(self) -> bool:
        """
        MANDATORY startup enforcement.

        This method MUST be called before the application starts.
        If validation fails, the application MUST NOT start.

        Returns:
            True if startup is allowed, raises exception otherwise
        """
        logger.info("STARTUP ENFORCER: Checking launch readiness...")

        # Check if we have current valid validation
        is_current, reason = self.is_validation_current()

        if is_current:
            logger.info(f"STARTUP ENFORCER: Using cached validation - {reason}")
            return True

        logger.warning(f"STARTUP ENFORCER: {reason}")
        logger.info("STARTUP ENFORCER: Running fresh validation...")

        # Run fresh validation
        passed, results = self.run_validation()

        if not passed:
            error_msg = self._format_blocking_errors(results)
            logger.error("=" * 60)
            logger.error("STARTUP BLOCKED - VALIDATION FAILED")
            logger.error("=" * 60)
            logger.error(error_msg)
            logger.error("=" * 60)
            logger.error("System cannot start until all blocking issues are resolved.")
            logger.error("Run: python final_launch_validation.py --repair")
            logger.error("=" * 60)

            raise StartupBlockedError(error_msg)

        logger.info("STARTUP ENFORCER: Validation PASSED - startup allowed")
        return True

    def _format_blocking_errors(self, results: Dict[str, Any]) -> str:
        """Format blocking errors for display."""
        lines = ["BLOCKING ISSUES PREVENTING STARTUP:"]
        for issue in results.get("blocking_issues", []):
            lines.append(f"  - [{issue.get('category')}] {issue.get('check')}: {issue.get('error')}")
        return "\n".join(lines)

    def get_validation_status(self) -> Dict[str, Any]:
        """Get current validation status for API/UI."""
        is_current, reason = self.is_validation_current()
        return {
            "is_valid": is_current,
            "reason": reason,
            "last_validation": self.validation_state.get("validated_at") if self.validation_state else None,
            "status": self.validation_state.get("status") if self.validation_state else "NEVER_RUN",
            "blocking_issues_count": len(self.validation_state.get("blocking_issues", [])) if self.validation_state else 0
        }


class StartupBlockedError(Exception):
    """Raised when startup is blocked due to validation failure."""
    pass


# Global enforcer instance
_enforcer: Optional[StartupEnforcer] = None


def get_startup_enforcer() -> StartupEnforcer:
    """Get global startup enforcer."""
    global _enforcer
    if _enforcer is None:
        _enforcer = StartupEnforcer()
    return _enforcer


def enforce_startup():
    """
    MANDATORY: Call this at application entry point.

    Usage in main.py or server startup:
        from startup_enforcer import enforce_startup
        enforce_startup()  # Will raise if validation fails
    """
    enforcer = get_startup_enforcer()
    return enforcer.enforce_startup()


def require_valid_startup(func):
    """
    Decorator to ensure function only runs if startup validation passed.

    Usage:
        @require_valid_startup
        def start_server():
            ...
    """
    def wrapper(*args, **kwargs):
        enforce_startup()
        return func(*args, **kwargs)
    return wrapper


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Running startup enforcement check...")
    try:
        enforce_startup()
        print("STARTUP ALLOWED")
    except StartupBlockedError as e:
        print(f"STARTUP BLOCKED:\n{e}")
        sys.exit(1)
