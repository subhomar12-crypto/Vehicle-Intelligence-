"""
Tests for authentication service.
"""

import pytest
import time


@pytest.mark.asyncio
async def test_hash_password():
    """Test password hashing."""
    from predict.core.security.hashing import hash_password, verify_password
    
    password = "TestPassword123!"
    hashed = hash_password(password)
    
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


@pytest.mark.asyncio
async def test_generate_api_key():
    """Test API key generation."""
    from predict.core.security.hashing import generate_api_key, hash_api_key, verify_api_key
    
    # Generate key
    key = generate_api_key(prefix="test")
    assert key.startswith("test_")
    
    # Hash and verify
    hashed = hash_api_key(key)
    assert verify_api_key(key, hashed) is True
    assert verify_api_key("wrong_key", hashed) is False


@pytest.mark.asyncio
async def test_create_access_token():
    """Test JWT token creation."""
    from predict.core.security.jwt_handler import create_access_token, verify_token
    
    data = {"sub": "123", "email": "test@example.com"}
    token = create_access_token(data)
    
    assert token is not None
    assert isinstance(token, str)
    
    # Verify token
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == "123"
    assert payload["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_expired_token():
    """Test expired token handling."""
    from predict.core.security.jwt_handler import create_access_token, verify_token
    
    # Create token that expired 1 hour ago
    data = {"sub": "123"}
    token = create_access_token(data, expires_delta_seconds=-3600)
    
    # Should return None for expired token
    payload = verify_token(token)
    assert payload is None
