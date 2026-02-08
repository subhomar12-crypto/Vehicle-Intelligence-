"""
Async database session management.

Provides:
- get_session_maker(): Lazily-initialized session factory
- get_db_session(): Async context manager for sessions
- get_db(): FastAPI dependency for request-scoped sessions
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from predict.core.db.engine import get_engine

logger = logging.getLogger(__name__)

_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or create the session maker (lazy init after engine is ready)."""
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_maker


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session as an async context manager.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    maker = get_session_maker()
    session = maker()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for request-scoped database sessions."""
    async with get_db_session() as session:
        yield session
