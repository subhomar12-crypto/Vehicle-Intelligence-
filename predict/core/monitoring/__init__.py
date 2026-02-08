"""
Monitoring and observability for PREDICT.

Provides:
- Health checks for all services
- Circuit breakers for resilience
- Metrics collection

Usage:
    from predict.core.monitoring import (
        get_health_monitor,
        get_circuit_registry,
        get_metrics_collector,
        circuit_breaker,
    )
    
    # Health check
    health = await get_health_monitor().check_all()
    
    # Circuit breaker
    @circuit_breaker("payment_service")
    async def process_payment(...):
        ...
    
    # Metrics
    get_metrics_collector().increment("requests_total")
"""

from predict.core.monitoring.health import (
    HealthMonitor,
    HealthCheck,
    HealthStatus,
    get_health_monitor,
)

from predict.core.monitoring.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_registry,
    circuit_breaker,
)

from predict.core.monitoring.metrics import (
    MetricsCollector,
    get_metrics_collector,
    increment_counter,
    set_gauge,
    record_timing,
    timeit,
)

__all__ = [
    # Health
    "HealthMonitor",
    "HealthCheck",
    "HealthStatus",
    "get_health_monitor",
    
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpen",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_circuit_registry",
    "circuit_breaker",
    
    # Metrics
    "MetricsCollector",
    "get_metrics_collector",
    "increment_counter",
    "set_gauge",
    "record_timing",
    "timeit",
]
