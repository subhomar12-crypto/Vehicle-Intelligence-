"""
Redis client with graceful fallback.

Provides:
- Async Redis connection
- Automatic reconnection
- Graceful degradation when Redis is unavailable
"""

import logging
from typing import Optional

import redis.asyncio as redis

from predict.core.config import get_config

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> Optional[redis.Redis]:
    """
    Get or create Redis client.
    
    Returns None if Redis is unavailable (graceful degradation).
    """
    global _redis_client
    
    if _redis_client is not None:
        try:
            await _redis_client.ping()
            return _redis_client
        except Exception as e:
            logger.warning(f"Redis connection lost: {e}")
            _redis_client = None
    
    try:
        config = get_config()
        _redis_client = redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
        )
        await _redis_client.ping()
        logger.info("Redis connection established")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        return None


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


class RedisCache:
    """
    Async Redis cache with fallback to in-memory.
    
    Uses Redis when available, falls back to dict() when not.
    """
    
    def __init__(self):
        self._local_cache = {}
        self._redis_available = False
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        redis_client = await get_redis()
        if redis_client:
            try:
                return await redis_client.get(key)
            except Exception as e:
                logger.debug(f"Redis get failed: {e}")
        
        # Fallback to local cache
        return self._local_cache.get(key)
    
    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int = 300,
    ) -> None:
        """Set value in cache with TTL."""
        redis_client = await get_redis()
        if redis_client:
            try:
                await redis_client.setex(key, ttl_seconds, value)
                return
            except Exception as e:
                logger.debug(f"Redis set failed: {e}")
        
        # Fallback to local cache (no TTL enforcement)
        self._local_cache[key] = value
    
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        redis_client = await get_redis()
        if redis_client:
            try:
                await redis_client.delete(key)
            except Exception as e:
                logger.debug(f"Redis delete failed: {e}")
        
        # Also remove from local cache
        self._local_cache.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        redis_client = await get_redis()
        if redis_client:
            try:
                return await redis_client.exists(key) > 0
            except Exception as e:
                logger.debug(f"Redis exists failed: {e}")
        
        return key in self._local_cache


# Global cache instance
cache = RedisCache()
