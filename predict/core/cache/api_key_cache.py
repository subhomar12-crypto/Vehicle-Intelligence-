"""
API key caching for sub-10ms validation.

Caches validated API keys in Redis with 5-minute TTL.
Invalidates on key changes (revocation, tier update).
"""

import json
import logging
from typing import Optional, Dict, Any

from predict.core.cache.redis_client import cache

logger = logging.getLogger(__name__)

# Cache TTL for API keys (5 minutes)
API_KEY_CACHE_TTL = 300


def _cache_key(api_key: str) -> str:
    """Generate cache key for API key."""
    # Use first 16 chars of key for cache key
    return f"api_key:{api_key[:16]}"


async def get_cached_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """
    Get validated API key data from cache.
    
    Returns:
        Cached key data or None if not in cache
    """
    key = _cache_key(api_key)
    cached = await cache.get(key)
    
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            logger.warning("Invalid cache data for API key")
            await cache.delete(key)
    
    return None


async def cache_api_key(
    api_key: str,
    key_data: Dict[str, Any],
    ttl_seconds: int = API_KEY_CACHE_TTL,
) -> None:
    """
    Cache validated API key data.
    
    Args:
        api_key: The API key (plain text)
        key_data: Validated key data (user_id, tier, permissions, etc.)
        ttl_seconds: Cache TTL (default 5 minutes)
    """
    key = _cache_key(api_key)
    
    # Serialize to JSON
    data_json = json.dumps(key_data)
    
    await cache.set(key, data_json, ttl_seconds)
    logger.debug(f"Cached API key {api_key[:8]}... for {ttl_seconds}s")


async def invalidate_api_key(api_key: str) -> None:
    """
    Invalidate cached API key.
    
    Call this when:
    - Key is revoked
    - Tier is updated
    - Permissions change
    """
    key = _cache_key(api_key)
    await cache.delete(key)
    logger.info(f"Invalidated cache for API key {api_key[:8]}...")


async def invalidate_user_keys(user_id: int) -> None:
    """
    Invalidate all cached keys for a user.
    
    Used when user's tier or permissions are updated.
    """
    # TODO: Implement user-key mapping for bulk invalidation
    # For now, keys will expire naturally
    logger.info(f"Invalidating keys for user {user_id}")


def invalidate_all_api_keys() -> None:
    """
    Invalidate ALL cached API keys (admin only).
    
    Used for system-wide cache clearing.
    """
    # Clear local cache immediately
    from predict.core.cache.redis_client import cache
    cache._local_cache.clear()
    logger.info("All local API key caches cleared")
    
    # Note: Redis pattern deletion would require redis-cli or SCAN
    # For now, we rely on TTL expiration
