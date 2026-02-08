"""
Async database session management.

Provides:
- async_session_maker: Configured session factory
- get_db_session(): Async context manager for sessions
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from predict.core.db.engine import get_engine

logger = logging.getLogger(__name__)

# Session factory
async_session_maker = async_sessionmaker(
    get_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session as an async context manager.
    
    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    session = async_session_maker()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
