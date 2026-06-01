"""
Health check API routes with float timestamps.
"""

import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db as get_db_session
from predict.core.monitoring.health import get_health_monitor

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("")
async def health_check(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Basic health check endpoint.
    
    Returns 200 if all systems are operational.
    """
    start = time.perf_counter()
    
    monitor = get_health_monitor()
    health = await monitor.get_full_health()
    
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    # Add response time
    health["response_time_ms"] = elapsed_ms
    
    return health


@router.get("/detailed")
async def detailed_health_check(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Detailed health check with component status.
    
    Returns comprehensive health information for all systems.
    """
    monitor = get_health_monitor()
    
    # Get full health
    health = await monitor.get_full_health()
    
    # Add history
    health["recent_checks"] = monitor.get_health_history(limit=5)
    
    return health


@router.get("/live")
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.
    
    Returns 200 if the application is running.
    """
    return {
        "status": "alive",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": time.time(),
    }


@router.get("/ready")
async def readiness_probe(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Kubernetes readiness probe endpoint.
    
    Returns 200 if the application is ready to serve traffic.
    """
    monitor = get_health_monitor()
    health = await monitor.get_full_health()
    
    if health["status"] in ["healthy", "degraded"]:
        return {
            "status": "ready",
            "health": health["status"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": time.time(),
        }
    else:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "health": health["status"],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "timestamp_unix": time.time(),
            },
        )
