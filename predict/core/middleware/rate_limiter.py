"""
Rate limiter middleware using Redis with float timestamps.
"""

import logging
import time
from typing import Optional, Dict, Any
from functools import wraps

from fastapi import Request, HTTPException, status

from predict.core.config import get_config

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter using Redis.
    
    Uses time.time() for all timestamp operations.
    """
    
    def __init__(self):
        self.config = get_config()
        self._redis = None
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        logger.debug("RateLimiter initialized")
    
    async def _get_redis(self):
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(
                    self.config.REDIS_URL,
                    decode_responses=True,
                )
            except Exception as e:
                logger.warning(f"Redis not available for rate limiting: {e}")
                return None
        return self._redis
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.
        
        Args:
            key: Rate limit key (e.g., user_id + endpoint)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds
        
        Returns:
            Tuple of (allowed, metadata)
        """
        redis = await self._get_redis()
        now = time.time()
        window_start = now - window_seconds
        
        if redis:
            # Use Redis sliding window
            try:
                pipe = redis.pipeline()
                
                # Remove old entries
                pipe.zremrangebyscore(f"ratelimit:{key}", 0, window_start)
                
                # Count current entries
                pipe.zcard(f"ratelimit:{key}")
                
                # Add current request
                pipe.zadd(f"ratelimit:{key}", {str(now): now})
                
                # Set expiry on the key
                pipe.expire(f"ratelimit:{key}", window_seconds + 1)
                
                results = await pipe.execute()
                current_count = results[1]
                
                allowed = current_count <= limit
                
                metadata = {
                    "limit": limit,
                    "remaining": max(0, limit - current_count),
                    "reset_time": now + window_seconds,
                    "window": window_seconds,
                }
                
                return allowed, metadata
            
            except Exception as e:
                logger.warning(f"Redis rate limit failed: {e}")
                # Fall through to local cache
        
        # Local cache fallback
        return self._check_local_limit(key, limit, window_seconds, now)
    
    def _check_local_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        now: float,
    ) -> tuple[bool, Dict[str, Any]]:
        """Check rate limit using local cache."""
        window_start = now - window_seconds
        
        if key not in self._local_cache:
            self._local_cache[key] = {"requests": [], "created": now}
        
        cache = self._local_cache[key]
        
        # Remove old requests
        cache["requests"] = [t for t in cache["requests"] if t > window_start]
        
        # Add current request
        cache["requests"].append(now)
        
        current_count = len(cache["requests"])
        allowed = current_count <= limit
        
        metadata = {
            "limit": limit,
            "remaining": max(0, limit - current_count),
            "reset_time": now + window_seconds,
            "window": window_seconds,
        }
        
        return allowed, metadata
    
    def limit(
        self,
        requests: int = 100,
        window: int = 60,
        key_func=None,
    ):
        """
        Decorator for rate limiting endpoints.
        
        Args:
            requests: Maximum requests allowed
            window: Time window in seconds
            key_func: Function to extract rate limit key from request
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract request
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                
                if request is None:
                    # No request found, skip rate limiting
                    return await func(*args, **kwargs)
                
                # Build rate limit key
                if key_func:
                    key = key_func(request)
                else:
                    client_ip = self._get_client_ip(request)
                    key = f"{client_ip}:{request.url.path}"
                
                # Check rate limit
                allowed, metadata = await self.is_allowed(key, requests, window)
                
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "Rate limit exceeded",
                            "retry_after": int(metadata["reset_time"] - time.time()),
                            "limit": metadata["limit"],
                            "window": metadata["window"],
                        },
                    )
                
                # Store metadata in request state for response headers
                request.state.rate_limit = metadata
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator
    
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


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
