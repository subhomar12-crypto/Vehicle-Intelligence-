"""
Tests for authentication endpoints.
"""

import pytest
import time


def test_register_user(client):
    """Test user registration."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "first_name": "New",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data


def test_register_duplicate_email(client):
    """Test registration with duplicate email fails."""
    # First registration
    client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
        },
    )
    
    # Second registration with same email
    response = client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
        },
    )
    assert response.status_code == 400


def test_login_success(client):
    """Test successful login."""
    # Register first
    client.post(
        "/api/auth/register",
        json={
            "email": "login@example.com",
            "password": "SecurePass123!",
        },
    )
    
    # Login
    response = client.post(
        "/api/auth/login",
        json={
            "email": "login@example.com",
            "password": "SecurePass123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword",
        },
    )
    assert response.status_code == 401


def test_protected_endpoint_without_auth(client):
    """Test accessing protected endpoint without authentication."""
    response = client.get("/api/profile")
    assert response.status_code == 401


def test_protected_endpoint_with_auth(client, auth_headers):
    """Test accessing protected endpoint with authentication."""
    response = client.get("/api/profile", headers=auth_headers)
    assert response.status_code == 200
