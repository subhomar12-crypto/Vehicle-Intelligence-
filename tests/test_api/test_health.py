"""
Tests for health check endpoints.
"""

import pytest


def test_health_check(client):
    """Test basic health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_health_check_detailed(client):
    """Test detailed health check endpoint."""
    response = client.get("/api/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]
