"""
Request tracing middleware.
Adds correlation IDs to every request for end-to-end tracing.
"""

import uuid
import time
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Adds X-Request-ID header and logs request timing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Use provided request ID or generate one
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()

        # Store on request state for downstream access
        request.state.request_id = request_id

        response = await call_next(request)

        # Add timing and request ID to response
        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

        # Log request summary
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 1),
            },
        )

        return response
