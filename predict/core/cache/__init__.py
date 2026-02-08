"""
Redis caching layer.

Provides:
- Redis client with graceful fallback
- API key caching for <10ms validation
- Pub/sub for WebSocket scaling
"""

from predict.core.cache.redis_client import get_redis, close_redis, cache, RedisCache
from predict.core.cache.api_key_cache import (
    get_cached_api_key,
    cache_api_key,
    invalidate_api_key,
    invalidate_user_keys,
)
from predict.core.cache.pubsub import (
    pubsub,
    WebSocketPubSub,
    vehicle_update_channel,
    guardian_alert_channel,
    broadcast_channel,
)

__all__ = [
    # Redis client
    "get_redis",
    "close_redis",
    "cache",
    "RedisCache",
    # API key cache
    "get_cached_api_key",
    "cache_api_key",
    "invalidate_api_key",
    "invalidate_user_keys",
    # Pub/sub
    "pubsub",
    "WebSocketPubSub",
    "vehicle_update_channel",
    "guardian_alert_channel",
    "broadcast_channel",
]
