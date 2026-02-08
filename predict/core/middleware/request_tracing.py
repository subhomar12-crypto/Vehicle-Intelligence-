"""
Request tracing middleware - adds correlation IDs.
"""

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Add correlation ID to each request for tracing."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


def get_request_id(request: Request) -> str:
    """Get the current request's correlation ID."""
    return getattr(request.state, "request_id", "unknown")
