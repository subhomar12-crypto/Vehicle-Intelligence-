"""
Async SQLAlchemy engine factory.

Creates connection pool with:
- pool_size=5 base connections
- max_overflow=15 burst connections  
- pool_pre_ping=True to detect stale connections
- pool_recycle=3600 to prevent connection aging issues
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None


def get_engine() -> AsyncEngine:
    """Get or create the async engine singleton."""
    global _engine
    if _engine is None:
        raise RuntimeError(
            "Database engine not initialized. Call init_engine() first."
        )
    return _engine


def init_engine(database_url: str, **kwargs) -> AsyncEngine:
    """
    Initialize the async database engine.

    Args:
        database_url: PostgreSQL async connection string
            e.g. postgresql+asyncpg://user:pass@localhost/predict
    """
    global _engine
    if _engine is not None:
        logger.warning("Engine already initialized, returning existing")
        return _engine

    defaults = {
        "pool_size": 5,
        "max_overflow": 15,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "echo": False,
    }
    defaults.update(kwargs)

    _engine = create_async_engine(database_url, **defaults)
    logger.info(
        f"Database engine initialized: pool_size={defaults['pool_size']}, "
        f"max_overflow={defaults['max_overflow']}"
    )
    return _engine


async def close_engine() -> None:
    """Dispose of the engine and close all connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine closed")
