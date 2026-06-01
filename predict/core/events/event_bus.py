"""
Lightweight in-process async event bus.

Supports:
- Decorator-based listener registration
- Async and sync listeners
- Error isolation (one listener failure doesn't affect others)
- Event history for debugging
"""

import asyncio
import logging
import time
from collections import deque
from typing import Callable, Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class EventBus:
    """Lightweight in-process async event bus."""

    def __init__(self, history_size: int = 50):
        self._listeners: Dict[str, List[Callable]] = {}
        self._history: deque = deque(maxlen=history_size)

    def on(self, event_name: str):
        """Decorator to register an event listener."""
        def decorator(func):
            self._listeners.setdefault(event_name, []).append(func)
            return func
        return decorator

    def register(self, event_name: str, func: Callable):
        """Imperatively register a listener."""
        self._listeners.setdefault(event_name, []).append(func)

    async def emit(self, event_name: str, data: Dict[str, Any]) -> int:
        """Emit an event to all registered listeners.

        Returns the number of listeners that executed successfully.
        """
        listeners = self._listeners.get(event_name, [])
        if not listeners:
            return 0

        self._history.append({
            "event": event_name,
            "time": time.time(),
            "listener_count": len(listeners),
        })

        success_count = 0
        for listener in listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(data)
                else:
                    listener(data)
                success_count += 1
            except Exception as e:
                logger.error(
                    "Event listener %s error for '%s': %s",
                    getattr(listener, "__name__", "?"), event_name, e,
                )
        return success_count

    def get_history(self) -> List[Dict[str, Any]]:
        """Return recent event history for debugging."""
        return list(self._history)

    def listener_count(self, event_name: Optional[str] = None) -> int:
        """Return number of registered listeners."""
        if event_name:
            return len(self._listeners.get(event_name, []))
        return sum(len(v) for v in self._listeners.values())


# Singleton
event_bus = EventBus()
