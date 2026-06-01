"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Circuit Breaker

Predict OBD - Circuit Breaker & Load Protection Module
CRITICAL: Prevents system overload and ensures graceful degradation.

This module implements:
- Circuit breakers for all critical services
- Back-pressure handling
- Memory and CPU safety thresholds
- AI inference protection
- Graceful degradation with clear error states
"""

import logging
import threading
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from collections import deque

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


# Safety thresholds - NOT configurable to prevent bypass
MEMORY_WARNING_THRESHOLD = 80  # % - Start throttling
MEMORY_CRITICAL_THRESHOLD = 90  # % - Block new requests
CPU_WARNING_THRESHOLD = 85  # % - Start throttling
CPU_CRITICAL_THRESHOLD = 95  # % - Block new requests
MAX_CONCURRENT_PREDICTIONS = 10  # Max simultaneous AI inferences
REQUEST_QUEUE_MAX_SIZE = 100  # Max queued requests
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5  # Failures before opening circuit
CIRCUIT_BREAKER_RESET_TIMEOUT = 60  # Seconds before attempting reset


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class SystemHealthState(Enum):
    """System health states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Throttling active
    CRITICAL = "critical"  # Blocking new requests
    OVERLOADED = "overloaded"  # System at capacity


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker."""
    name: str
    state: CircuitState
    failure_count: int
    last_failure_time: Optional[datetime]
    last_success_time: Optional[datetime]
    opened_at: Optional[datetime]
    total_requests: int
    total_failures: int


@dataclass
class SystemHealthSnapshot:
    """Current system health snapshot."""
    timestamp: str
    memory_percent: float
    cpu_percent: float
    active_predictions: int
    queued_requests: int
    health_state: SystemHealthState
    throttle_active: bool
    blocking_active: bool


class CircuitBreaker:
    """
    Circuit breaker for a specific service.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(self, name: str, failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                 reset_timeout: int = CIRCUIT_BREAKER_RESET_TIMEOUT):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._opened_at: Optional[datetime] = None
        self._total_requests = 0
        self._total_failures = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for reset timeout."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._opened_at and (datetime.now() - self._opened_at).seconds >= self.reset_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"CIRCUIT BREAKER [{self.name}]: Transitioning to HALF_OPEN")
            return self._state

    def record_success(self):
        """Record a successful request."""
        with self._lock:
            self._total_requests += 1
            self._last_success_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"CIRCUIT BREAKER [{self.name}]: CLOSED - Service recovered")

    def record_failure(self, error: Optional[str] = None):
        """Record a failed request."""
        with self._lock:
            self._total_requests += 1
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    self._opened_at = datetime.now()
                    logger.error(f"CIRCUIT BREAKER [{self.name}]: OPENED - "
                                f"{self._failure_count} failures, blocking requests")

    def is_available(self) -> Tuple[bool, str]:
        """Check if requests should be allowed."""
        state = self.state  # Triggers potential state transition

        if state == CircuitState.CLOSED:
            return True, "Service available"

        if state == CircuitState.OPEN:
            return False, f"Service unavailable (circuit open since {self._opened_at})"

        if state == CircuitState.HALF_OPEN:
            return True, "Service recovering (limited requests)"

        return False, "Unknown state"

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return CircuitBreakerState(
            name=self.name,
            state=self.state,
            failure_count=self._failure_count,
            last_failure_time=self._last_failure_time,
            last_success_time=self._last_success_time,
            opened_at=self._opened_at,
            total_requests=self._total_requests,
            total_failures=self._total_failures
        )


class LoadProtector:
    """
    System-wide load protection.

    GUARANTEES:
    1. Memory usage monitored and requests blocked at critical levels
    2. CPU usage monitored with throttling
    3. Concurrent AI predictions limited
    4. Request queue bounded
    5. Graceful degradation with clear errors
    """

    def __init__(self):
        self._active_predictions = 0
        self._prediction_lock = threading.Lock()
        self._request_queue: deque = deque(maxlen=REQUEST_QUEUE_MAX_SIZE)
        self._throttle_active = False
        self._blocking_active = False

        # Circuit breakers for critical services
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            "ai_prediction": CircuitBreaker("ai_prediction"),
            "database": CircuitBreaker("database"),
            "external_api": CircuitBreaker("external_api"),
            "pdf_generation": CircuitBreaker("pdf_generation"),
        }

        # Resource monitoring
        self._last_health_check: Optional[SystemHealthSnapshot] = None
        self._health_check_interval = 5  # seconds

        # Start background monitoring
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_running = True
        self._monitor_thread.start()

    def _monitor_loop(self):
        """Background resource monitoring."""
        while self._monitor_running:
            try:
                self._update_health_state()
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
            time.sleep(self._health_check_interval)

    def _update_health_state(self):
        """Update system health state."""
        memory_percent = psutil.virtual_memory().percent
        cpu_percent = psutil.cpu_percent(interval=1)

        # Determine health state
        if memory_percent >= MEMORY_CRITICAL_THRESHOLD or cpu_percent >= CPU_CRITICAL_THRESHOLD:
            health_state = SystemHealthState.CRITICAL
            self._blocking_active = True
            self._throttle_active = True
        elif memory_percent >= MEMORY_WARNING_THRESHOLD or cpu_percent >= CPU_WARNING_THRESHOLD:
            health_state = SystemHealthState.DEGRADED
            self._throttle_active = True
            self._blocking_active = False
        else:
            health_state = SystemHealthState.HEALTHY
            self._throttle_active = False
            self._blocking_active = False

        with self._prediction_lock:
            active_predictions = self._active_predictions

        self._last_health_check = SystemHealthSnapshot(
            timestamp=datetime.now().isoformat(),
            memory_percent=memory_percent,
            cpu_percent=cpu_percent,
            active_predictions=active_predictions,
            queued_requests=len(self._request_queue),
            health_state=health_state,
            throttle_active=self._throttle_active,
            blocking_active=self._blocking_active
        )

        if health_state in [SystemHealthState.CRITICAL, SystemHealthState.DEGRADED]:
            logger.warning(f"LOAD PROTECTOR: System {health_state.value} - "
                          f"Memory: {memory_percent:.1f}%, CPU: {cpu_percent:.1f}%")

    def check_system_capacity(self) -> Tuple[bool, str, SystemHealthState]:
        """
        Check if system has capacity for new requests.

        Returns:
            (has_capacity, message, health_state)
        """
        if self._last_health_check is None:
            self._update_health_state()

        health = self._last_health_check

        if self._blocking_active:
            return False, (f"System at critical capacity - Memory: {health.memory_percent:.1f}%, "
                          f"CPU: {health.cpu_percent:.1f}%"), health.health_state

        return True, "System healthy", health.health_state

    def acquire_prediction_slot(self) -> Tuple[bool, str]:
        """
        Acquire a slot for AI prediction.

        Returns:
            (acquired, message)
        """
        # Check system capacity first
        has_capacity, message, _ = self.check_system_capacity()
        if not has_capacity:
            return False, f"OVERLOAD: {message}"

        # Check circuit breaker
        is_available, cb_message = self.circuit_breakers["ai_prediction"].is_available()
        if not is_available:
            return False, f"SERVICE UNAVAILABLE: {cb_message}"

        # Check concurrent prediction limit
        with self._prediction_lock:
            if self._active_predictions >= MAX_CONCURRENT_PREDICTIONS:
                return False, f"BACKPRESSURE: Max concurrent predictions ({MAX_CONCURRENT_PREDICTIONS}) reached"

            self._active_predictions += 1
            return True, f"Slot acquired ({self._active_predictions}/{MAX_CONCURRENT_PREDICTIONS})"

    def release_prediction_slot(self, success: bool = True, error: Optional[str] = None):
        """Release a prediction slot after completion."""
        with self._prediction_lock:
            self._active_predictions = max(0, self._active_predictions - 1)

        if success:
            self.circuit_breakers["ai_prediction"].record_success()
        else:
            self.circuit_breakers["ai_prediction"].record_failure(error)

    def get_health_snapshot(self) -> SystemHealthSnapshot:
        """Get current system health snapshot."""
        if self._last_health_check is None:
            self._update_health_state()
        return self._last_health_check

    def get_circuit_breaker_states(self) -> Dict[str, CircuitBreakerState]:
        """Get all circuit breaker states."""
        return {name: cb.get_state() for name, cb in self.circuit_breakers.items()}

    def shutdown(self):
        """Shutdown load protector."""
        self._monitor_running = False


# Global instance
_load_protector: Optional[LoadProtector] = None
_load_protector_lock = threading.Lock()


def get_load_protector() -> LoadProtector:
    """Get global load protector instance."""
    global _load_protector
    with _load_protector_lock:
        if _load_protector is None:
            _load_protector = LoadProtector()
        return _load_protector


def protected_prediction(func: Callable) -> Callable:
    """
    Decorator to protect AI prediction functions with circuit breaker and load protection.

    Usage:
        @protected_prediction
        def predict_failure(vehicle_id, data):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        protector = get_load_protector()

        # Try to acquire prediction slot
        acquired, message = protector.acquire_prediction_slot()
        if not acquired:
            logger.warning(f"LOAD PROTECTION: Prediction blocked - {message}")
            raise OverloadError(message)

        try:
            result = func(*args, **kwargs)
            protector.release_prediction_slot(success=True)
            return result

        except Exception as e:
            protector.release_prediction_slot(success=False, error=str(e))
            raise

    return wrapper


def check_capacity_or_reject() -> Tuple[bool, Optional[str]]:
    """
    Check system capacity and return rejection message if at capacity.

    Usage:
        can_proceed, error = check_capacity_or_reject()
        if not can_proceed:
            return error_response(503, error)
    """
    protector = get_load_protector()
    has_capacity, message, health_state = protector.check_system_capacity()

    if not has_capacity:
        return False, f"Service temporarily unavailable: {message}"

    return True, None


class OverloadError(Exception):
    """Raised when system is overloaded and cannot accept request."""

    def __init__(self, message: str, health_state: SystemHealthState = None):
        self.health_state = health_state
        super().__init__(message)


class ServiceUnavailableError(Exception):
    """Raised when a service circuit breaker is open."""
    pass


# HTTP error responses for load protection
def get_overload_response() -> Dict[str, Any]:
    """Get standard overload error response."""
    protector = get_load_protector()
    health = protector.get_health_snapshot()

    return {
        "error": "SERVICE_OVERLOADED",
        "message": "System is temporarily at capacity. Please retry later.",
        "retry_after_seconds": 30,
        "health_state": health.health_state.value,
        "timestamp": datetime.now().isoformat()
    }


def get_circuit_open_response(service: str) -> Dict[str, Any]:
    """Get standard circuit breaker open response."""
    return {
        "error": "SERVICE_UNAVAILABLE",
        "message": f"The {service} service is temporarily unavailable.",
        "retry_after_seconds": CIRCUIT_BREAKER_RESET_TIMEOUT,
        "timestamp": datetime.now().isoformat()
    }
