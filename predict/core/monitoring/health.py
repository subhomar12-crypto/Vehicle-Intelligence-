"""
Health monitoring service with time-based float timestamps.

Tracks system health, database connectivity, and service status.
"""

import logging
import os
import time
import asyncio
from typing import Dict, Any, Optional, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.config import get_config
from predict.core.db.session import get_db_session

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    System health monitoring with async checks.
    
    Uses time.time() for all timestamps (float seconds since epoch).
    """
    
    def __init__(self):
        self.config = get_config()
        self._health_history: List[Dict[str, Any]] = []
        self._max_history = 100
        self._start_time = time.time()
        logger.debug("HealthMonitor initialized")
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        start = time.perf_counter()

        try:
            async with get_db_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar_one()

            elapsed_ms = (time.perf_counter() - start) * 1000

            return {
                "status": "healthy",
                "response_time_ms": elapsed_ms,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time(),
            }
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity."""
        start = time.perf_counter()

        try:
            import redis.asyncio as aioredis

            redis_url = getattr(self.config, "REDIS_URL", "redis://localhost:6379/0")
            client = aioredis.from_url(redis_url, socket_connect_timeout=3)

            await client.ping()
            await client.aclose()

            elapsed_ms = (time.perf_counter() - start) * 1000

            return {
                "status": "healthy",
                "response_time_ms": elapsed_ms,
                "timestamp": time.time(),
            }

        except (ConnectionError, OSError, ConnectionRefusedError):
            logger.debug("Redis not available (not installed or not running)")
            return {
                "status": "unavailable",
                "error": "Redis not running",
                "timestamp": time.time(),
            }

        except ImportError:
            logger.debug("redis package not installed")
            return {
                "status": "unavailable",
                "error": "redis package not installed",
                "timestamp": time.time(),
            }

        except Exception as e:
            # Catch redis-specific connection errors too
            if "connect" in str(e).lower() or "refused" in str(e).lower():
                logger.debug(f"Redis not available: {e}")
                return {
                    "status": "unavailable",
                    "error": str(e),
                    "timestamp": time.time(),
                }
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time(),
            }
    
    async def check_ai_models(self) -> Dict[str, Any]:
        """Check AI model availability using singleton (no re-init)."""
        try:
            from predict.core.ai.unified_ai_module import get_unified_ai

            ai = get_unified_ai()
            status = ai.get_system_status()

            return {
                "status": "healthy",
                "models": status.get("ensemble", {}),
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"AI model health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time(),
            }
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get CPU and memory metrics using psutil."""
        try:
            import psutil

            # CPU metrics — interval=None returns cached value instantly
            # (non-blocking, avoids stalling the async event loop)
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics (Windows-safe: use drive of cwd)
            disk_path = os.path.splitdrive(os.getcwd())[0] + os.sep if os.name == 'nt' else '/'
            disk = psutil.disk_usage(disk_path)
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "frequency_mhz": cpu_freq.current if cpu_freq else None,
                },
                "memory": {
                    "total_mb": round(memory.total / (1024 * 1024), 2),
                    "available_mb": round(memory.available / (1024 * 1024), 2),
                    "percent": memory.percent,
                    "used_mb": round(memory.used / (1024 * 1024), 2),
                },
                "disk": {
                    "total_gb": round(disk.total / (1024 ** 3), 2),
                    "used_gb": round(disk.used / (1024 ** 3), 2),
                    "free_gb": round(disk.free / (1024 ** 3), 2),
                    "percent": round((disk.used / disk.total) * 100, 2),
                },
                "timestamp": time.time(),
            }
        except ImportError:
            logger.warning("psutil not installed, system metrics unavailable")
            return {
                "cpu": {"percent": None, "count": None, "frequency_mhz": None},
                "memory": {"total_mb": None, "available_mb": None, "percent": None, "used_mb": None},
                "disk": {"total_gb": None, "used_gb": None, "free_gb": None, "percent": None},
                "timestamp": time.time(),
                "error": "psutil not installed",
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {
                "cpu": {"percent": None, "count": None, "frequency_mhz": None},
                "memory": {"total_mb": None, "available_mb": None, "percent": None, "used_mb": None},
                "disk": {"total_gb": None, "used_gb": None, "free_gb": None, "percent": None},
                "timestamp": time.time(),
                "error": str(e),
            }
    
    async def get_full_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health status.
        
        Returns:
            Health status dict with all component checks
        """
        start = time.perf_counter()
        
        # Run all checks concurrently
        db_check, redis_check, ai_check = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_ai_models(),
            return_exceptions=True,
        )
        
        # Handle exceptions
        if isinstance(db_check, Exception):
            db_check = {"status": "error", "error": str(db_check), "timestamp": time.time()}
        if isinstance(redis_check, Exception):
            redis_check = {"status": "error", "error": str(redis_check), "timestamp": time.time()}
        if isinstance(ai_check, Exception):
            ai_check = {"status": "error", "error": str(ai_check), "timestamp": time.time()}
        
        # Determine overall status (ignore "unavailable" services like Redis)
        checks = [db_check.get("status"), redis_check.get("status"), ai_check.get("status")]
        required_checks = [s for s in checks if s != "unavailable"]

        if not required_checks or all(s == "healthy" for s in required_checks):
            overall = "healthy"
        elif any(s == "healthy" for s in required_checks):
            overall = "degraded"
        else:
            overall = "unhealthy"
        
        uptime_sec = time.time() - self._start_time
        
        # Get system metrics (CPU, memory, disk)
        system_metrics = self.get_system_metrics()
        
        # Build services dict
        services = {
            "database": {
                "status": db_check.get("status", "unknown"),
                "response_time_ms": db_check.get("response_time_ms"),
            },
            "redis": {
                "status": redis_check.get("status", "unknown"),
                "response_time_ms": redis_check.get("response_time_ms"),
            },
            "ai_models": {
                "status": ai_check.get("status", "unknown"),
            },
        }
        
        result = {
            "status": overall,
            "version": "3.0.0",
            "uptime_seconds": uptime_sec,
            "uptime_formatted": self._format_duration(uptime_sec),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": time.time(),
            "checks": {
                "database": db_check,
                "redis": redis_check,
                "ai_models": ai_check,
            },
            "services": services,
            "system": system_metrics,
            "response_time_ms": (time.perf_counter() - start) * 1000,
        }
        
        # Store in history
        self._health_history.append(result)
        if len(self._health_history) > self._max_history:
            self._health_history = self._health_history[-self._max_history:]
        
        return result
    
    def _format_duration(self, seconds: float) -> str:
        """Format seconds into human-readable duration."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}h"
        else:
            return f"{seconds/86400:.1f}d"
    
    def get_health_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent health check history."""
        return self._health_history[-limit:]
    
    def is_healthy(self) -> bool:
        """Quick check if system is healthy."""
        if not self._health_history:
            return False
        return self._health_history[-1].get("status") == "healthy"


# Singleton instance
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get health monitor singleton."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
