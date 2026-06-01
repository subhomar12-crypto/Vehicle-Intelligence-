"""
WebSocket service for real-time communication.

Handles:
- WebSocket connection management
- Real-time data broadcasting
- Redis pub/sub for multi-process scaling
"""

import logging
from typing import Dict, Set, Any, Union

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[Union[int, str], Set[WebSocket]] = {}
        self.channels: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: Union[int, str]) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        # Support both int user_id and string channel names
        key = user_id
        if key not in self.active_connections:
            self.active_connections[key] = set()
        self.active_connections[key].add(websocket)

        # Also track by string channel if it's a string
        if isinstance(user_id, str):
            if user_id not in self.channels:
                self.channels[user_id] = set()
            self.channels[user_id].add(websocket)

        logger.info(f"WebSocket connected: {user_id}")

    async def disconnect(self, websocket: WebSocket, user_id: Union[int, str]) -> None:
        """Remove a WebSocket connection."""
        key = user_id
        if key in self.active_connections:
            self.active_connections[key].discard(websocket)
            if not self.active_connections[key]:
                del self.active_connections[key]

        if isinstance(user_id, str) and user_id in self.channels:
            self.channels[user_id].discard(websocket)
            if not self.channels[user_id]:
                del self.channels[user_id]

        logger.info(f"WebSocket disconnected: {user_id}")

    async def send_to_user(self, user_id: Union[int, str], data: Dict[str, Any]) -> None:
        """Send data to all connections for a user."""
        connections = self.active_connections.get(user_id, set())
        for ws in list(connections):
            try:
                await ws.send_json(data)
            except Exception:
                connections.discard(ws)

    async def broadcast(self, data: Dict[str, Any]) -> None:
        """Broadcast data to all connected users."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, data)

    async def broadcast_to_channel(self, channel: str, data: Dict[str, Any]) -> None:
        """Broadcast data to all connections in a specific channel."""
        connections = self.channels.get(channel, set())
        for ws in list(connections):
            try:
                await ws.send_json(data)
            except Exception:
                connections.discard(ws)

    @property
    def active_count(self) -> int:
        """Number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager
ws_manager = ConnectionManager()
