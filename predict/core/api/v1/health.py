"""
Health check endpoints.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db
from predict.core.version import APP_VERSION

router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    """
    Detailed readiness check.
    
    Returns 200 only if all dependencies are healthy.
    Used by Kubernetes probes and load balancers.
    """
    checks = {}
    
    # Database check
    try:
        result = await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "latency_ms": 0}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}
    
    # Overall status
    all_ok = all(c.get("status") == "ok" for c in checks.values())
    
    return {
        "status": "ready" if all_ok else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/live")
async def health_live():
    """
    Liveness probe.
    
    Returns 200 if the application is running.
    Kubernetes uses this to restart unhealthy pods.
    """
    return {"status": "alive"}
