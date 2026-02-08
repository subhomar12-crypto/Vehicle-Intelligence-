"""
WebSocket service for real-time communication.

Handles:
- WebSocket connection management
- Real-time data broadcasting
- Redis pub/sub for multi-process scaling
"""

import logging
from typing import Dict, Set, Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"WebSocket connected for user {user_id}")

    async def disconnect(self, websocket: WebSocket, user_id: int) -> None:
        """Remove a WebSocket connection."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_to_user(self, user_id: int, data: Dict[str, Any]) -> None:
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

    @property
    def active_count(self) -> int:
        """Number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager
ws_manager = ConnectionManager()
