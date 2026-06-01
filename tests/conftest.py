"""
Shared test fixtures for PREDICT.

Provides:
- Database session with rollback after each test
- Test client for API testing
- Mock services
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a database engine for testing."""
    from predict.core.db.base import Base
    
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session with automatic rollback."""
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session() as session:
        yield session
        # Rollback after test
        await session.rollback()


@pytest.fixture
def client(db_session):
    """Create a test client with overridden dependencies."""
    from fastapi.testclient import TestClient
    from predict.core.api.app import create_app
    from predict.core.api.deps import get_db_session
    
    app = create_app()
    
    # Override dependency
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db_session] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clear overrides
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    """Return a mock user dictionary."""
    return {
        "id": 1,
        "email": "test@example.com",
        "tier": "pro",
        "is_active": True,
        "is_admin": False,
    }


@pytest.fixture
def mock_admin():
    """Return a mock admin user dictionary."""
    return {
        "id": 2,
        "email": "admin@example.com",
        "tier": "enterprise",
        "is_active": True,
        "is_admin": True,
    }


@pytest.fixture
def mock_vehicle_data():
    """Return mock OBD vehicle data."""
    return {
        "timestamp": 1704067200.0,
        "rpm": 2500.0,
        "speed": 60.0,
        "coolant_temp": 90.0,
        "battery_voltage": 13.5,
        "engine_load": 45.0,
        "maf_rate": 15.0,
        "throttle_position": 30.0,
        "intake_temp": 35.0,
    }


@pytest.fixture
def auth_headers(mock_user):
    """Generate authentication headers for testing."""
    from predict.core.security.jwt_handler import create_access_token
    
    token = create_access_token({"sub": str(mock_user["id"]), "email": mock_user["email"]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing-only")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("TESTING", "true")


# Mark all tests as async by default
def pytest_collection_modifyitems(items):
    """Add asyncio marker to all test functions."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
