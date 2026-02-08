"""
Application metrics collection.

Simple in-memory metrics for:
- Request counts and latencies
- Error rates
- Business metrics (predictions, exports, etc.)
"""

import logging
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Single metric value with timestamp."""
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    In-memory metrics collector.
    
    Stores metrics in memory with configurable retention.
    For production, integrate with Prometheus or similar.
    """
    
    def __init__(self, max_history: int = 10000):
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timings: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._lock = threading.Lock()
        self._start_time = time.time()
    
    def increment(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Amount to increment
            labels: Optional label dict
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] += value
    
    def gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Current value
            labels: Optional label dict
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
    
    def timing(
        self,
        name: str,
        duration_ms: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Record a timing metric.
        
        Args:
            name: Metric name
            duration_ms: Duration in milliseconds
            labels: Optional label dict
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._timings[key].append({
                "value": duration_ms,
                "timestamp": time.time(),
            })
    
    def timeit(self, name: str, labels: Optional[Dict[str, str]] = None):
        """
        Context manager for timing code blocks.
        
        Usage:
            with metrics.timeit("db_query"):
                result = await db.fetch(...)
        """
        return _TimingContext(self, name, labels)
    
    def histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Record a value in a histogram.
        
        Args:
            name: Metric name
            value: Value to record
            labels: Optional label dict
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._histograms[key].append(value)
            # Keep only last 10000 values
            if len(self._histograms[key]) > 10000:
                self._histograms[key] = self._histograms[key][-10000:]
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """Get counter value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get gauge value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._gauges.get(key, 0.0)
    
    def get_timing_stats(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """Get timing statistics (min, max, avg, p95, p99)."""
        with self._lock:
            key = self._make_key(name, labels)
            values = [v["value"] for v in self._timings[key]]
            
            if not values:
                return {"count": 0}
            
            sorted_values = sorted(values)
            n = len(sorted_values)
            
            return {
                "count": n,
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "avg": sum(sorted_values) / n,
                "p95": sorted_values[int(n * 0.95)],
                "p99": sorted_values[int(n * 0.99)] if n >= 100 else sorted_values[-1],
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as dictionary."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timings": {
                    name: self.get_timing_stats(name)
                    for name in self._timings.keys()
                },
                "uptime_seconds": time.time() - self._start_time,
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timings.clear()
            self._start_time = time.time()
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create metric key from name and labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


class _TimingContext:
    """Context manager for timing code blocks."""
    
    def __init__(
        self,
        collector: MetricsCollector,
        name: str,
        labels: Optional[Dict[str, str]],
    ):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.collector.timing(self.name, duration_ms, self.labels)


# Singleton instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get singleton MetricsCollector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# Convenience functions
def increment_counter(name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
    """Increment a counter metric."""
    get_metrics_collector().increment(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Set a gauge metric."""
    get_metrics_collector().gauge(name, value, labels)


def record_timing(name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record a timing metric."""
    get_metrics_collector().timing(name, duration_ms, labels)


def timeit(name: str, labels: Optional[Dict[str, str]] = None):
    """Context manager for timing."""
    return get_metrics_collector().timeit(name, labels)
