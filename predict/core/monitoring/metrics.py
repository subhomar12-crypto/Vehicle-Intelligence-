"""
Metrics collection service with float timestamps.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and aggregates application metrics.
    
    Uses time.time() for all timestamps.
    """
    
    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._start_time = time.time()
        logger.debug("MetricsCollector initialized")
    
    def increment(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        key = self._format_key(name, tags)
        self._counters[key] += value
    
    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        key = self._format_key(name, tags)
        self._gauges[key] = value
    
    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram value."""
        key = self._format_key(name, tags)
        self._histograms[key].append(value)
        
        # Keep only last 1000 values
        if len(self._histograms[key]) > 1000:
            self._histograms[key] = self._histograms[key][-1000:]
    
    def _format_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """Format metric key with tags."""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        # Calculate histogram statistics
        histogram_stats = {}
        for key, values in self._histograms.items():
            if values:
                import statistics
                histogram_stats[key] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                }
        
        uptime_sec = time.time() - self._start_time
        
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": histogram_stats,
            "uptime_seconds": uptime_sec,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": time.time(),
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._start_time = time.time()
        logger.info("Metrics reset")


# Singleton instance
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get metrics collector singleton."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def record_request_duration(duration_ms: float, endpoint: str, status_code: int) -> None:
    """Record API request duration."""
    metrics = get_metrics()
    metrics.histogram("http_request_duration_ms", duration_ms, {
        "endpoint": endpoint,
        "status": str(status_code),
    })
    metrics.increment("http_requests_total", tags={
        "endpoint": endpoint,
        "status": str(status_code),
    })


def record_prediction(component: str, risk_score: float, confidence: float) -> None:
    """Record prediction metrics."""
    metrics = get_metrics()
    metrics.increment("predictions_total", tags={"component": component})
    metrics.histogram("prediction_risk_score", risk_score, tags={"component": component})
    metrics.histogram("prediction_confidence", confidence, tags={"component": component})
