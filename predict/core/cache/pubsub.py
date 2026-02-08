"""
Redis pub/sub for WebSocket scaling.

Enables broadcasting messages across multiple server instances.
"""

import json
import logging
from typing import Callable, Optional

import redis.asyncio as redis

from predict.core.cache.redis_client import get_redis

logger = logging.getLogger(__name__)


class WebSocketPubSub:
    """
    Redis pub/sub for WebSocket message broadcasting.
    
    Use case: Multiple server instances need to broadcast
    to WebSocket clients connected to different instances.
    """
    
    def __init__(self):
        self._pubsub: Optional[redis.client.PubSub] = None
        self._handlers: dict[str, Callable] = {}
    
    async def connect(self) -> bool:
        """Connect to Redis pub/sub."""
        redis_client = await get_redis()
        if not redis_client:
            logger.warning("Redis not available, pub/sub disabled")
            return False
        
        try:
            self._pubsub = redis_client.pubsub()
            logger.info("Redis pub/sub connected")
            return True
        except Exception as e:
            logger.error(f"Failed to connect pub/sub: {e}")
            return False
    
    async def subscribe(self, channel: str, handler: Callable) -> None:
        """
        Subscribe to a channel.
        
        Args:
            channel: Channel name (e.g., "vehicle:123:updates")
            handler: Callback function(message_data)
        """
        if not self._pubsub:
            logger.warning("Pub/sub not connected, subscription skipped")
            return
        
        await self._pubsub.subscribe(channel)
        self._handlers[channel] = handler
        logger.debug(f"Subscribed to channel: {channel}")
    
    async def publish(self, channel: str, message: dict) -> None:
        """
        Publish message to channel.
        
        Args:
            channel: Channel name
            message: Message data (will be JSON serialized)
        """
        redis_client = await get_redis()
        if not redis_client:
            logger.debug(f"Redis unavailable, message not published to {channel}")
            return
        
        try:
            message_json = json.dumps(message)
            await redis_client.publish(channel, message_json)
            logger.debug(f"Published to {channel}: {message}")
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
    
    async def listen(self) -> None:
        """Listen for messages (run in background task)."""
        if not self._pubsub:
            return
        
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    data = json.loads(message["data"])
                    
                    handler = self._handlers.get(channel)
                    if handler:
                        try:
                            await handler(data)
                        except Exception as e:
                            logger.error(f"Handler error for {channel}: {e}")
        except Exception as e:
            logger.error(f"Pub/sub listen error: {e}")
    
    async def close(self) -> None:
        """Close pub/sub connection."""
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None
            logger.info("Redis pub/sub closed")


# Global pub/sub instance
pubsub = WebSocketPubSub()


# Channel name generators
def vehicle_update_channel(vehicle_id: int) -> str:
    """Generate channel name for vehicle updates."""
    return f"vehicle:{vehicle_id}:updates"


def guardian_alert_channel(guardian_id: str) -> str:
    """Generate channel name for guardian alerts."""
    return f"guardian:{guardian_id}:alerts"


def broadcast_channel() -> str:
    """Generate channel for system-wide broadcasts."""
    return "system:broadcast"
