"""
Tests for database repository pattern.
"""

import pytest
import time


@pytest.mark.asyncio
async def test_user_repository_create(db_session):
    """Test creating a user."""
    from predict.core.db.repositories.user_repo import UserRepository
    
    repo = UserRepository(db_session)
    
    user_data = {
        "email": "repotest@example.com",
        "password_hash": "hashed_password",
        "tier": "free",
    }
    
    user = await repo.create(user_data)
    
    assert user.id is not None
    assert user.email == "repotest@example.com"


@pytest.mark.asyncio
async def test_user_repository_get_by_id(db_session):
    """Test getting user by ID."""
    from predict.core.db.repositories.user_repo import UserRepository
    
    repo = UserRepository(db_session)
    
    # Create user
    user = await repo.create({
        "email": "getbyid@example.com",
        "password_hash": "hash",
        "tier": "free",
    })
    
    # Get by ID
    found = await repo.get_by_id(user.id)
    assert found is not None
    assert found.email == "getbyid@example.com"


@pytest.mark.asyncio
async def test_user_repository_get_by_email(db_session):
    """Test getting user by email."""
    from predict.core.db.repositories.user_repo import UserRepository
    
    repo = UserRepository(db_session)
    
    # Create user
    await repo.create({
        "email": "getbyemail@example.com",
        "password_hash": "hash",
        "tier": "free",
    })
    
    # Get by email
    found = await repo.get_by_email("getbyemail@example.com")
    assert found is not None
    assert found.email == "getbyemail@example.com"


@pytest.mark.asyncio
async def test_user_repository_update(db_session):
    """Test updating a user."""
    from predict.core.db.repositories.user_repo import UserRepository
    
    repo = UserRepository(db_session)
    
    # Create user
    user = await repo.create({
        "email": "update@example.com",
        "password_hash": "hash",
        "tier": "free",
    })
    
    # Update
    updated = await repo.update(user.id, {"tier": "pro"})
    assert updated.tier == "pro"


@pytest.mark.asyncio
async def test_user_repository_delete(db_session):
    """Test deleting a user."""
    from predict.core.db.repositories.user_repo import UserRepository
    
    repo = UserRepository(db_session)
    
    # Create user
    user = await repo.create({
        "email": "delete@example.com",
        "password_hash": "hash",
        "tier": "free",
    })
    
    # Delete
    result = await repo.delete(user.id)
    assert result is True
    
    # Verify deleted
    found = await repo.get_by_id(user.id)
    assert found is None


@pytest.mark.asyncio
async def test_vehicle_repository_create(db_session):
    """Test creating a vehicle profile."""
    from predict.core.db.repositories.vehicle_repo import VehicleProfileRepository
    
    repo = VehicleProfileRepository(db_session)
    
    vehicle_data = {
        "user_id": 1,
        "vin": "1HGCM82633A123456",
        "make": "Honda",
        "model": "Accord",
        "year": 2020,
    }
    
    vehicle = await repo.create(vehicle_data)
    
    assert vehicle.id is not None
    assert vehicle.vin == "1HGCM82633A123456"


@pytest.mark.asyncio
async def test_base_repository_count(db_session):
    """Test base repository count method."""
    from predict.core.db.repositories.user_repo import UserRepository
    
    repo = UserRepository(db_session)
    
    # Initial count
    initial_count = await repo.count()
    
    # Create users
    await repo.create({
        "email": "count1@example.com",
        "password_hash": "hash",
        "tier": "free",
    })
    await repo.create({
        "email": "count2@example.com",
        "password_hash": "hash",
        "tier": "free",
    })
    
    # Verify count
    new_count = await repo.count()
    assert new_count == initial_count + 2
