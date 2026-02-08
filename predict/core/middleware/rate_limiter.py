"""
Rate limiting middleware using slowapi + Redis backend.
"""

import logging
from typing import Optional, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.
    
    Uses Redis for distributed rate limiting across multiple server instances.
    Falls back to in-memory storage if Redis is unavailable.
    """
    
    def __init__(
        self,
        app,
        redis_client=None,
        default_limit: int = 100,
        default_window: int = 3600,  # 1 hour
    ):
        super().__init__(app)
        self.redis = redis_client
        self.default_limit = default_limit
        self.default_window = default_window
        self._local_cache = {}  # Fallback if Redis unavailable
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before processing request."""
        # Skip rate limiting for certain paths
        if request.url.path in ['/health', '/health/ready', '/docs', '/openapi.json']:
            return await call_next(request)
        
        # Get client identifier (API key preferred, IP fallback)
        client_id = await self._get_client_id(request)
        
        # Check rate limit
        is_allowed, remaining, reset_time = await self._check_rate_limit(
            client_id, request.url.path
        )
        
        if not is_allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": ErrorCode.RATE_LIMIT_EXCEEDED,
                        "message": "Rate limit exceeded. Please try again later.",
                        "details": {
                            "reset_at": reset_time.isoformat() if reset_time else None,
                        },
                    }
                }
            )
            response.headers["X-RateLimit-Limit"] = str(self.default_limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    async def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier from request."""
        # Try API key first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key[:16]}"  # Use first 16 chars of key
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
    
    async def _check_rate_limit(
        self, client_id: str, path: str
    ) -> tuple[bool, int, Optional]:
        """
        Check if request is within rate limit.
        
        Returns:
            (is_allowed, remaining_requests, reset_time)
        """
        key = f"ratelimit:{client_id}:{path.split('/')[1] if len(path) > 1 else 'default'}"
        
        if self.redis:
            try:
                return await self._check_redis(key)
            except Exception as e:
                logger.warning(f"Redis rate limit check failed: {e}, using fallback")
        
        return self._check_memory(key)
    
    async def _check_redis(self, key: str) -> tuple[bool, int, Optional]:
        """Check rate limit using Redis."""
        import asyncio
        from datetime import datetime, timedelta
        
        pipe = self.redis.pipeline()
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.default_window)
        
        # Add current request
        pipe.zadd(key, {str(now.timestamp()): now.timestamp()})
        # Remove old entries outside window
        pipe.zremrangebyscore(key, 0, window_start.timestamp())
        # Count remaining entries
        pipe.zcard(key)
        # Set expiry on key
        pipe.expire(key, self.default_window)
        
        results = await asyncio.to_thread(pipe.execute)
        current_count = results[2]  # zcard result
        
        is_allowed = current_count <= self.default_limit
        remaining = max(0, self.default_limit - current_count)
        reset_time = now + timedelta(seconds=self.default_window)
        
        return is_allowed, remaining, reset_time
    
    def _check_memory(self, key: str) -> tuple[bool, int, Optional]:
        """Check rate limit using in-memory storage (fallback)."""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.default_window)
        
        # Get or create entry
        if key not in self._local_cache:
            self._local_cache[key] = []
        
        # Clean old entries
        self._local_cache[key] = [
            ts for ts in self._local_cache[key] if ts > window_start
        ]
        
        # Add current request
        self._local_cache[key].append(now)
        
        current_count = len(self._local_cache[key])
        is_allowed = current_count <= self.default_limit
        remaining = max(0, self.default_limit - current_count)
        reset_time = now + timedelta(seconds=self.default_window)
        
        return is_allowed, remaining, reset_time


class RateLimitExceededError(APIError):
    """Custom error for rate limit exceeded."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=429,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded. Please try again later.",
            details={"retry_after_seconds": retry_after},
        )
