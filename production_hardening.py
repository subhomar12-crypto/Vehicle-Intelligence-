"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Production Hardening

Predict OBD - Production Hardening Integration Module
======================================================
CRITICAL: This module integrates ALL production hardening safeguards.

This module MUST be imported and initialized at application startup.
It ensures the system CANNOT operate in an unsafe state.

INTEGRATED SAFEGUARDS:
1. Startup Enforcement - System blocks if validation fails
2. Cold-Start Safety - Predictions capped for insufficient data
3. Retraining Safeguards - Model updates cannot break production
4. Circuit Breaker - Load protection prevents overload
5. Accessibility Enforcement - All outputs meet accessibility requirements
6. Alert Delivery Guarantees - Alerts are always delivered or escalated
7. System Self-Test - Backup/restore/sync verified automatically

USAGE:
    from production_hardening import initialize_production_safeguards
    initialize_production_safeguards()  # Call at startup

    # Or use the decorator
    @production_ready
    def main():
        ...
"""

import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class ProductionHardeningStatus:
    """Tracks status of all production hardening components."""

    def __init__(self):
        self.initialized = False
        self.initialization_time: Optional[str] = None
        self.component_status: Dict[str, Dict[str, Any]] = {}
        self.all_safeguards_active = False

    def record_component(self, name: str, status: str, details: Optional[Dict] = None):
        """Record status of a component."""
        self.component_status[name] = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all component statuses."""
        return {
            "initialized": self.initialized,
            "initialization_time": self.initialization_time,
            "all_safeguards_active": self.all_safeguards_active,
            "components": self.component_status
        }


# Global status tracker
_hardening_status = ProductionHardeningStatus()


def initialize_production_safeguards() -> Tuple[bool, Dict[str, Any]]:
    """
    Initialize all production hardening safeguards.

    This function MUST be called at application startup.
    If any critical safeguard fails to initialize, the application should not start.

    Returns:
        (success, status_report)
    """
    global _hardening_status

    logger.info("=" * 60)
    logger.info("PRODUCTION HARDENING: Initializing safeguards...")
    logger.info("=" * 60)

    _hardening_status = ProductionHardeningStatus()
    all_passed = True
    critical_failures = []

    # 1. Initialize Startup Enforcer
    try:
        from startup_enforcer import get_startup_enforcer
        enforcer = get_startup_enforcer()
        is_valid, reason = enforcer.is_validation_current()

        if is_valid:
            _hardening_status.record_component("startup_enforcer", "active", {"reason": reason})
            logger.info("[+] Startup Enforcer: ACTIVE")
        else:
            # Run validation
            passed, results = enforcer.run_validation()
            if passed:
                _hardening_status.record_component("startup_enforcer", "active", {"freshly_validated": True})
                logger.info("[+] Startup Enforcer: ACTIVE (freshly validated)")
            else:
                _hardening_status.record_component("startup_enforcer", "failed", {"reason": reason})
                logger.error("[X] Startup Enforcer: FAILED")
                all_passed = False
                critical_failures.append("Startup validation failed")

    except ImportError as e:
        _hardening_status.record_component("startup_enforcer", "missing", {"error": str(e)})
        logger.error(f"[X] Startup Enforcer: MODULE MISSING - {e}")
        all_passed = False
        critical_failures.append(f"startup_enforcer module missing: {e}")

    # 2. Initialize Cold-Start Safety
    try:
        from cold_start_safety import get_cold_start_enforcer
        enforcer = get_cold_start_enforcer()
        _hardening_status.record_component("cold_start_safety", "active")
        logger.info("[+] Cold-Start Safety: ACTIVE")

    except ImportError as e:
        _hardening_status.record_component("cold_start_safety", "missing", {"error": str(e)})
        logger.error(f"[X] Cold-Start Safety: MODULE MISSING - {e}")
        all_passed = False
        critical_failures.append(f"cold_start_safety module missing: {e}")

    # 3. Initialize Retraining Safeguards
    try:
        from retraining_safeguards import get_retraining_safeguards
        safeguards = get_retraining_safeguards()
        rollback_available, rollback_count = safeguards.verify_rollback_available()
        _hardening_status.record_component("retraining_safeguards", "active", {
            "rollback_available": rollback_available,
            "backup_count": rollback_count
        })
        logger.info(f"[+] Retraining Safeguards: ACTIVE (rollbacks: {rollback_count})")

    except ImportError as e:
        _hardening_status.record_component("retraining_safeguards", "missing", {"error": str(e)})
        logger.warning(f"[!] Retraining Safeguards: MODULE MISSING - {e}")
        # Not critical - system can run without retraining

    # 4. Initialize Circuit Breaker
    try:
        from circuit_breaker import get_load_protector
        protector = get_load_protector()
        health = protector.get_health_snapshot()
        _hardening_status.record_component("circuit_breaker", "active", {
            "health_state": health.health_state.value,
            "memory_percent": health.memory_percent,
            "cpu_percent": health.cpu_percent
        })
        logger.info(f"[+] Circuit Breaker: ACTIVE (state: {health.health_state.value})")

    except ImportError as e:
        _hardening_status.record_component("circuit_breaker", "missing", {"error": str(e)})
        logger.error(f"[X] Circuit Breaker: MODULE MISSING - {e}")
        all_passed = False
        critical_failures.append(f"circuit_breaker module missing: {e}")

    # 5. Initialize Accessibility Enforcer
    try:
        from accessibility_enforcer import get_accessibility_enforcer
        enforcer = get_accessibility_enforcer()
        _hardening_status.record_component("accessibility_enforcer", "active")
        logger.info("[+] Accessibility Enforcer: ACTIVE")

    except ImportError as e:
        _hardening_status.record_component("accessibility_enforcer", "missing", {"error": str(e)})
        logger.warning(f"[!] Accessibility Enforcer: MODULE MISSING - {e}")
        # Not critical for startup

    # 6. Initialize Alert Delivery Guarantees
    try:
        from alert_delivery_guarantees import get_alert_guarantees
        guarantees = get_alert_guarantees()
        is_healthy, message = guarantees.is_healthy()

        if not is_healthy:
            # Run self-test
            passed, results = guarantees.run_startup_self_test()
            is_healthy = passed

        _hardening_status.record_component("alert_delivery", "active" if is_healthy else "degraded", {
            "healthy": is_healthy,
            "message": message
        })

        if is_healthy:
            logger.info("[+] Alert Delivery: ACTIVE")
        else:
            logger.warning(f"[!] Alert Delivery: DEGRADED - {message}")

    except ImportError as e:
        _hardening_status.record_component("alert_delivery", "missing", {"error": str(e)})
        logger.warning(f"[!] Alert Delivery: MODULE MISSING - {e}")

    # 7. Initialize System Self-Test
    try:
        from system_self_test import get_system_self_test
        self_test = get_system_self_test()

        # Run self-tests
        report = self_test.run_all_tests()

        _hardening_status.record_component("system_self_test", "active" if report.all_passed else "failed", {
            "tests_passed": report.tests_passed,
            "tests_failed": report.tests_failed,
            "report_id": report.report_id
        })

        if report.all_passed:
            logger.info(f"[+] System Self-Test: PASSED ({report.tests_passed}/{report.tests_run})")
        else:
            logger.warning(f"[!] System Self-Test: FAILED ({report.tests_failed} failures)")

    except ImportError as e:
        _hardening_status.record_component("system_self_test", "missing", {"error": str(e)})
        logger.warning(f"[!] System Self-Test: MODULE MISSING - {e}")

    # Set final status
    _hardening_status.initialized = True
    _hardening_status.initialization_time = datetime.now().isoformat()
    _hardening_status.all_safeguards_active = all_passed

    logger.info("=" * 60)
    if all_passed:
        logger.info("PRODUCTION HARDENING: All safeguards ACTIVE")
    else:
        logger.error(f"PRODUCTION HARDENING: {len(critical_failures)} critical failures")
        for failure in critical_failures:
            logger.error(f"  - {failure}")
    logger.info("=" * 60)

    return all_passed, _hardening_status.get_summary()


def get_hardening_status() -> Dict[str, Any]:
    """Get current production hardening status."""
    return _hardening_status.get_summary()


def production_ready(func):
    """
    Decorator to ensure production safeguards are active before function runs.

    Usage:
        @production_ready
        def start_server():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _hardening_status.initialized:
            success, status = initialize_production_safeguards()
            if not success:
                raise RuntimeError(
                    f"Production safeguards initialization failed. "
                    f"Cannot start application in unsafe state."
                )
        return func(*args, **kwargs)
    return wrapper


def verify_production_ready() -> Tuple[bool, str]:
    """
    Verify system is production ready.

    Returns:
        (is_ready, message)
    """
    if not _hardening_status.initialized:
        return False, "Production safeguards not initialized"

    if not _hardening_status.all_safeguards_active:
        failed = [name for name, info in _hardening_status.component_status.items()
                  if info["status"] in ["failed", "missing"]]
        return False, f"Failed components: {', '.join(failed)}"

    return True, "All production safeguards active"


# ==================== HEALTH CHECK ENDPOINT ====================

def get_health_check() -> Dict[str, Any]:
    """
    Get health check data for monitoring endpoints.

    Returns:
        Dict suitable for JSON response
    """
    status = _hardening_status.get_summary()

    # Aggregate health
    is_healthy = status["all_safeguards_active"] if status["initialized"] else False

    # Get component health
    component_health = {}
    for name, info in status.get("components", {}).items():
        component_health[name] = info["status"] == "active"

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "initialized": status["initialized"],
        "initialization_time": status["initialization_time"],
        "safeguards_active": status["all_safeguards_active"],
        "components": component_health,
        "timestamp": datetime.now().isoformat()
    }


# ==================== AUTO-INITIALIZATION ====================

def _auto_initialize():
    """Auto-initialize on module import if enabled."""
    import os
    if os.environ.get("PREDICT_OBD_AUTO_INIT", "0") == "1":
        initialize_production_safeguards()


# Uncomment to enable auto-initialization
# _auto_initialize()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("Initializing production safeguards...")
    success, status = initialize_production_safeguards()

    print(f"\nStatus: {'SUCCESS' if success else 'FAILED'}")
    print(f"Components initialized: {len(status['components'])}")

    for name, info in status['components'].items():
        symbol = "[+]" if info["status"] == "active" else "[X]"
        print(f"  {symbol} {name}: {info['status']}")
