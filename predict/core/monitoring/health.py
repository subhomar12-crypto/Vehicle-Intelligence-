"""
Health check monitoring system.

Provides comprehensive health checks for:
- Database connectivity
- Redis connectivity
- External service availability
- AI model availability
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db_session
from predict.core.cache.redis_client import get_redis

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheck:
    """Individual health check result."""
    
    def __init__(
        self,
        name: str,
        status: HealthStatus,
        response_time_ms: float,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.name = name
        self.status = status
        self.response_time_ms = response_time_ms
        self.details = details or {}
        self.error = error
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "status": self.status,
            "response_time_ms": round(self.response_time_ms, 2),
            "timestamp": self.timestamp,
        }
        if self.details:
            result["details"] = self.details
        if self.error:
            result["error"] = self.error
        return result


class HealthMonitor:
    """
    Health monitoring system for PREDICT services.
    
    Performs async health checks on all dependent services.
    """
    
    def __init__(self):
        self.checks: Dict[str, callable] = {}
        self.timeout_seconds = 5.0
        self._register_default_checks()
    
    def _register_default_checks(self) -> None:
        """Register default health checks."""
        self.register_check("database", self._check_database)
        self.register_check("redis", self._check_redis)
        self.register_check("ai_models", self._check_ai_models)
    
    def register_check(self, name: str, check_func: callable) -> None:
        """
        Register a health check function.
        
        Args:
            name: Check identifier
            check_func: Async function returning HealthCheck
        """
        self.checks[name] = check_func
        logger.debug(f"Registered health check: {name}")
    
    async def check_all(self) -> Dict[str, Any]:
        """
        Run all health checks concurrently.
        
        Returns:
            Overall health status with individual check results
        """
        start_time = datetime.utcnow()
        
        # Run all checks concurrently
        tasks = [
            self._run_check_with_timeout(name, func)
            for name, func in self.checks.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        check_results = []
        healthy_count = 0
        unhealthy_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                check_results.append({
                    "name": "unknown",
                    "status": HealthStatus.UNKNOWN,
                    "error": str(result),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                unhealthy_count += 1
            else:
                check_results.append(result.to_dict())
                if result.status == HealthStatus.HEALTHY:
                    healthy_count += 1
                elif result.status == HealthStatus.UNHEALTHY:
                    unhealthy_count += 1
        
        # Determine overall status
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif healthy_count == len(check_results):
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
        
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(elapsed_ms, 2),
            "checks": check_results,
        }
    
    async def _run_check_with_timeout(
        self,
        name: str,
        check_func: callable
    ) -> HealthCheck:
        """Run a health check with timeout."""
        start_time = datetime.utcnow()
        
        try:
            result = await asyncio.wait_for(
                check_func(),
                timeout=self.timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=elapsed,
                error="Health check timeout",
            )
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=elapsed,
                error=str(e),
            )
    
    async def _check_database(self) -> HealthCheck:
        """Check database connectivity."""
        start_time = datetime.utcnow()
        
        try:
            async with get_db_session() as session:
                result = await session.execute(text("SELECT 1"))
                row = result.scalar()
                
                elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                return HealthCheck(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=elapsed,
                    details={"connection": "active", "test_query": row},
                )
        
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheck(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=elapsed,
                error=str(e),
            )
    
    async def _check_redis(self) -> HealthCheck:
        """Check Redis connectivity."""
        start_time = datetime.utcnow()
        
        try:
            redis = await get_redis()
            
            if redis is None:
                elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
                return HealthCheck(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=elapsed,
                    details={"connection": "fallback_mode", "note": "Using in-memory cache"},
                )
            
            # Test Redis ping
            await redis.ping()
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return HealthCheck(
                name="redis",
                status=HealthStatus.HEALTHY,
                response_time_ms=elapsed,
                details={"connection": "active"},
            )
        
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheck(
                name="redis",
                status=HealthStatus.DEGRADED,
                response_time_ms=elapsed,
                details={"connection": "fallback_mode"},
                error=str(e),
            )
    
    async def _check_ai_models(self) -> HealthCheck:
        """Check AI model availability."""
        start_time = datetime.utcnow()
        
        try:
            from predict.core.ai import get_unified_ai
            
            ai = get_unified_ai()
            model_status = ai.get_model_status()
            
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Determine status based on available models
            available = sum(
                1 for m in model_status.get("ensemble", {}).get("model_info", [])
                if m.get("available", False)
            )
            
            if available > 0:
                status = HealthStatus.HEALTHY
            else:
                status = HealthStatus.DEGRADED
            
            return HealthCheck(
                name="ai_models",
                status=status,
                response_time_ms=elapsed,
                details=model_status,
            )
        
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheck(
                name="ai_models",
                status=HealthStatus.DEGRADED,
                response_time_ms=elapsed,
                error=str(e),
            )
    
    async def check_service(
        self,
        name: str,
        check_func: callable,
    ) -> HealthCheck:
        """
        Run a single health check.
        
        Args:
            name: Service name
            check_func: Async function that returns True if healthy
        
        Returns:
            HealthCheck result
        """
        start_time = datetime.utcnow()
        
        try:
            is_healthy = await asyncio.wait_for(
                check_func(),
                timeout=self.timeout_seconds
            )
            
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return HealthCheck(
                name=name,
                status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                response_time_ms=elapsed,
            )
        
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=elapsed,
                error=str(e),
            )


# Singleton instance
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get singleton HealthMonitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
