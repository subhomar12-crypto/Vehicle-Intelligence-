"""
Audit middleware for logging all requests with float timestamps.
"""

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from predict.core.db.session import get_db_session

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all API requests for audit purposes.
    
    Uses time.time() for timestamps (float seconds since epoch).
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log audit data."""
        start_time = time.perf_counter()
        
        # Get request details
        method = request.method
        path = request.url.path
        client_ip = self._get_client_ip(request)
        user_id = self._get_user_id(request)
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
        
        # Calculate timing
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Log audit entry
        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        logger.info(
            f"{method} {path} - {status_code} - {elapsed_ms:.2f}ms - "
            f"{client_ip} - user={user_id}"
        )
        
        # Store in database (async background task)
        try:
            await self._store_audit_log(
                method=method,
                path=path,
                status_code=status_code,
                client_ip=client_ip,
                user_id=user_id,
                elapsed_ms=elapsed_ms,
                timestamp=time.time(),
            )
        except Exception as e:
            logger.warning(f"Failed to store audit log: {e}")
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_user_id(self, request: Request) -> Optional[int]:
        """Extract user ID from request state."""
        if hasattr(request.state, "user") and request.state.user:
            return getattr(request.state.user, "id", None)
        return None
    
    async def _store_audit_log(
        self,
        method: str,
        path: str,
        status_code: int,
        client_ip: str,
        user_id: Optional[int],
        elapsed_ms: float,
        timestamp: float,
    ) -> None:
        """Store audit log in database."""
        # This would typically use a background task
        # For now, just log it
        pass
