"""
Circuit breaker pattern for resilient external service calls.

Prevents cascade failures by temporarily blocking requests
to failing services.
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 30.0      # Seconds before half-open
    half_open_max_calls: int = 3        # Test calls in half-open
    success_threshold: int = 2          # Successes to close


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0


class CircuitBreaker:
    """
    Circuit breaker for external service resilience.
    
    States:
        CLOSED: Normal operation, requests pass through
        OPEN: Service failing, requests blocked immediately
        HALF_OPEN: Testing recovery with limited requests
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker '{name}' initialized ({self.state})")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args, **kwargs: Function arguments
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: Original exception if call fails
        """
        async with self._lock:
            await self._update_state()
            
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpen(
                    f"Circuit '{self.name}' is OPEN - service unavailable"
                )
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpen(
                        f"Circuit '{self.name}' HALF_OPEN limit reached"
                    )
                self.half_open_calls += 1
        
        # Execute call outside lock
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _update_state(self) -> None:
        """Update circuit state based on time and stats."""
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if self.stats.last_failure_time:
                elapsed = time.time() - self.stats.last_failure_time
                if elapsed >= self.config.recovery_timeout:
                    await self._transition_to(CircuitState.HALF_OPEN)
                    self.half_open_calls = 0
    
    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self.stats.successes += 1
            self.stats.last_success_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Check if we can close the circuit
                recent_successes = self.stats.successes
                if recent_successes >= self.config.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)
                    self.stats = CircuitBreakerStats()  # Reset stats
    
    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self.stats.failures += 1
            self.stats.last_failure_time = time.time()
            
            if self.state == CircuitState.CLOSED:
                if self.stats.failures >= self.config.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)
            
            elif self.state == CircuitState.HALF_OPEN:
                # Back to open on any failure in half-open
                await self._transition_to(CircuitState.OPEN)
    
    async def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state."""
        if self.state != new_state:
            logger.warning(
                f"Circuit '{self.name}' state: {self.state} -> {new_state}"
            )
            self.state = new_state
            self.stats.state_changes += 1
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit state."""
        return {
            "name": self.name,
            "state": self.state,
            "stats": {
                "failures": self.stats.failures,
                "successes": self.stats.successes,
                "state_changes": self.stats.state_changes,
                "last_failure": self.stats.last_failure_time,
                "last_success": self.stats.last_success_time,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            },
        }
    
    async def force_open(self) -> None:
        """Manually open the circuit."""
        async with self._lock:
            await self._transition_to(CircuitState.OPEN)
    
    async def force_close(self) -> None:
        """Manually close the circuit."""
        async with self._lock:
            await self._transition_to(CircuitState.CLOSED)
            self.stats = CircuitBreakerStats()
            self.half_open_calls = 0


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerRegistry:
    """Registry of circuit breakers."""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    def list_circuits(self) -> Dict[str, Dict[str, Any]]:
        """List all circuit breakers and their states."""
        return {
            name: breaker.get_state()
            for name, breaker in self._breakers.items()
        }


# Global registry
_circuit_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry."""
    global _circuit_registry
    if _circuit_registry is None:
        _circuit_registry = CircuitBreakerRegistry()
    return _circuit_registry


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
):
    """
    Decorator to apply circuit breaker to a function.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening
        recovery_timeout: Seconds before recovery attempt
    
    Usage:
        @circuit_breaker("payment_service")
        async def process_payment(...):
            ...
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
    )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            registry = get_circuit_registry()
            breaker = registry.get_or_create(name, config)
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
