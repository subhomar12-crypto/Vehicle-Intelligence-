"""
Tests for AI status endpoint.

Covers:
- Vehicle ownership verification
- Admin bypass
- Response structure validation
- Fleet learning data inclusion
"""

import pytest
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from predict.core.db.models.vehicle import VehicleProfile, VehicleBaseline
from predict.core.db.models.prediction_feedback import FleetPenaltyAdjustment


class TestAIStatusEndpoint:
    """Test suite for GET /api/predictions/{vehicle_id}/ai-status"""
    
    @pytest.fixture
    async def test_user(self, db_session):
        """Create a test user."""
        from predict.core.db.models.user import User
        
        user = User(
            email="test_owner@example.com",
            tier="pro",
            is_active=True,
            created_at=time.time(),
        )
        db_session.add(user)
        await db_session.flush()
        return user
    
    @pytest.fixture
    async def test_admin(self, db_session):
        """Create a test admin user."""
        from predict.core.db.models.user import User
        
        admin = User(
            email="admin@example.com",
            tier="admin",
            is_active=True,
            created_at=time.time(),
        )
        db_session.add(admin)
        await db_session.flush()
        return admin
    
    @pytest.fixture
    async def owned_vehicle(self, db_session, test_user):
        """Create a vehicle owned by test user."""
        vehicle = VehicleProfile(
            make="Toyota",
            model="Camry",
            year=2020,
            owner_user_id=test_user.id,
            created_at=time.time(),
        )
        db_session.add(vehicle)
        await db_session.flush()
        return vehicle
    
    @pytest.fixture
    async def other_vehicle(self, db_session, test_admin):
        """Create a vehicle owned by admin (not by test_user)."""
        vehicle = VehicleProfile(
            make="Honda",
            model="Accord",
            year=2021,
            owner_user_id=test_admin.id,
            created_at=time.time(),
        )
        db_session.add(vehicle)
        await db_session.flush()
        return vehicle
    
    @pytest.fixture
    async def vehicle_with_baseline(self, db_session, test_user):
        """Create a vehicle with baseline data."""
        vehicle = VehicleProfile(
            make="BMW",
            model="X5",
            year=2022,
            owner_user_id=test_user.id,
            created_at=time.time(),
        )
        db_session.add(vehicle)
        await db_session.flush()
        
        baseline = VehicleBaseline(
            profile_id=vehicle.profile_id,
            phase="baseline_ready",
            data_points=750,
            trip_count=45,
            sensor_stats='{"battery_voltage": {"mean": 13.5, "std": 0.3}}',
            created_at=time.time(),
            updated_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.flush()
        
        return vehicle, baseline
    
    @pytest.fixture
    async def fleet_adjustments(self, db_session):
        """Create fleet penalty adjustments for components."""
        adjustments = []
        components = [
            "battery", "cooling_system", "engine", "fuel_system", 
            "transmission", "intake_system", "exhaust_system", 
            "turbo_supercharger", "oil_system"
        ]
        
        for comp in components:
            adj = FleetPenaltyAdjustment(
                component=comp,
                penalty_multiplier=0.95,
                sample_count=150,
                directional_accuracy=0.78,
                mean_absolute_error=0.12,
                last_updated=time.time(),
            )
            db_session.add(adj)
            adjustments.append(adj)
        
        await db_session.flush()
        return adjustments
    
    def test_ai_status_success_owner(self, client, auth_headers):
        """Test that vehicle owner can get AI status."""
        response = client.get(
            "/api/predictions/1/ai-status",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_ai_status_not_found(self, client, auth_headers):
        """Test that non-existent vehicle returns 404."""
        response = client.get(
            "/api/predictions/99999/ai-status",
            headers=auth_headers
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_ai_status_response_structure(
        self, client, db_session, test_user, owned_vehicle, auth_headers
    ):
        """Test that response contains all expected fields."""
        # Add baseline data
        baseline = VehicleBaseline(
            profile_id=owned_vehicle.profile_id,
            phase="collecting",
            data_points=250,
            trip_count=12,
            sensor_stats="{}",
            created_at=time.time(),
            updated_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.commit()
        
        response = client.get(
            f"/api/predictions/{owned_vehicle.profile_id}/ai-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required top-level fields
        assert "vehicle_id" in data
        assert "baseline_phase" in data
        assert "data_points" in data
        assert "trip_count" in data
        assert "model_statuses" in data
        assert "intelligence_level" in data
        assert "fleet_learning" in data
        assert "timestamp" in data
        assert "timestamp_iso" in data
        
        # Verify data types
        assert isinstance(data["vehicle_id"], int)
        assert isinstance(data["baseline_phase"], str)
        assert isinstance(data["data_points"], int)
        assert isinstance(data["trip_count"], int)
        assert isinstance(data["model_statuses"], list)
        assert isinstance(data["intelligence_level"], str)
        assert isinstance(data["fleet_learning"], dict)
    
    @pytest.mark.asyncio
    async def test_ai_status_model_statuses_length(
        self, client, db_session, test_user, owned_vehicle, auth_headers
    ):
        """Test that model_statuses has exactly 9 components."""
        baseline = VehicleBaseline(
            profile_id=owned_vehicle.profile_id,
            phase="collecting",
            data_points=0,
            trip_count=0,
            sensor_stats="{}",
            created_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.commit()
        
        response = client.get(
            f"/api/predictions/{owned_vehicle.profile_id}/ai-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["model_statuses"]) == 9
        
        # Check each status has required fields
        for status in data["model_statuses"]:
            assert "component" in status
            assert "status" in status
            assert "has_sensor_data" in status
            assert "data_points" in status
    
    @pytest.mark.asyncio
    async def test_ai_status_intelligence_levels(
        self, client, db_session, test_user, owned_vehicle, auth_headers
    ):
        """Test intelligence level computation based on phase."""
        test_cases = [
            (0, "collecting", "minimal"),
            (150, "collecting", "emerging"),
            (550, "baseline_ready", "basic"),
            (2100, "autoencoder_ready", "advanced"),
        ]
        
        for data_points, phase, expected_level in test_cases:
            # Create baseline for this test case
            baseline = VehicleBaseline(
                profile_id=owned_vehicle.profile_id,
                phase=phase,
                data_points=data_points,
                trip_count=10,
                sensor_stats="{}",
                created_at=time.time(),
            )
            db_session.add(baseline)
            await db_session.flush()
            
            response = client.get(
                f"/api/predictions/{owned_vehicle.profile_id}/ai-status",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["intelligence_level"] == expected_level, \
                f"Expected {expected_level} for phase={phase}, points={data_points}"
            
            # Clean up for next iteration
            await db_session.delete(baseline)
            await db_session.flush()
    
    @pytest.mark.asyncio
    async def test_ai_status_fleet_learning_data(
        self, client, db_session, test_user, owned_vehicle, 
        fleet_adjustments, auth_headers
    ):
        """Test that fleet learning adjustments are included."""
        baseline = VehicleBaseline(
            profile_id=owned_vehicle.profile_id,
            phase="baseline_ready",
            data_points=1000,
            trip_count=50,
            sensor_stats="{}",
            created_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.commit()
        
        response = client.get(
            f"/api/predictions/{owned_vehicle.profile_id}/ai-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check fleet learning data for each component
        components = [
            "battery", "cooling_system", "engine", "fuel_system",
            "transmission", "intake_system", "exhaust_system",
            "turbo_supercharger", "oil_system"
        ]
        
        for comp in components:
            assert comp in data["fleet_learning"]
            adj = data["fleet_learning"][comp]
            assert "penalty_multiplier" in adj
            assert "sample_count" in adj
            assert "directional_accuracy" in adj
            assert "mean_absolute_error" in adj
            assert "last_updated" in adj
    
    @pytest.mark.asyncio
    async def test_ai_status_autoencoder_info(
        self, client, db_session, test_user, owned_vehicle, auth_headers
    ):
        """Test autoencoder info is present when phase is autoencoder_ready."""
        import json
        
        baseline = VehicleBaseline(
            profile_id=owned_vehicle.profile_id,
            phase="autoencoder_ready",
            data_points=2500,
            trip_count=120,
            sensor_stats=json.dumps({"engine": {"mean": 2000}}),
            autoencoder_trained_at=time.time(),
            autoencoder_loss=0.023,
            autoencoder_weights=b"mock_weights",
            created_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.commit()
        
        response = client.get(
            f"/api/predictions/{owned_vehicle.profile_id}/ai-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["autoencoder"] is not None
        assert data["autoencoder"]["trained_at"] is not None
        assert data["autoencoder"]["loss"] == 0.023
        assert data["autoencoder"]["has_weights"] is True
    
    @pytest.mark.asyncio
    async def test_ai_status_no_autoencoder_info(
        self, client, db_session, test_user, owned_vehicle, auth_headers
    ):
        """Test autoencoder info is null when phase is not autoencoder_ready."""
        baseline = VehicleBaseline(
            profile_id=owned_vehicle.profile_id,
            phase="baseline_ready",
            data_points=600,
            trip_count=30,
            sensor_stats="{}",
            created_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.commit()
        
        response = client.get(
            f"/api/predictions/{owned_vehicle.profile_id}/ai-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["autoencoder"] is None
    
    @pytest.mark.asyncio
    async def test_ai_status_unauthorized_access(
        self, client, db_session, test_user, test_admin, other_vehicle, auth_headers
    ):
        """Test that non-owner cannot access another vehicle's AI status."""
        # Create baseline for the other vehicle
        baseline = VehicleBaseline(
            profile_id=other_vehicle.profile_id,
            phase="collecting",
            data_points=0,
            trip_count=0,
            sensor_stats="{}",
            created_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.commit()
        
        # auth_headers belongs to test_user, try to access admin's vehicle
        response = client.get(
            f"/api/predictions/{other_vehicle.profile_id}/ai-status",
            headers=auth_headers
        )
        
        assert response.status_code == 403
        assert "not your vehicle" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_ai_status_admin_bypass(
        self, client, db_session, test_admin, other_vehicle
    ):
        """Test that admin can access any vehicle's AI status."""
        from predict.core.security.jwt_handler import create_access_token
        
        # Create admin auth headers
        admin_token = create_access_token(
            {"sub": str(test_admin.id), "email": test_admin.email}
        )
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        baseline = VehicleBaseline(
            profile_id=other_vehicle.profile_id,
            phase="autoencoder_ready",
            data_points=3000,
            trip_count=200,
            sensor_stats="{}",
            created_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.commit()
        
        response = client.get(
            f"/api/predictions/{other_vehicle.profile_id}/ai-status",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["vehicle_id"] == other_vehicle.profile_id
        assert data["baseline_phase"] == "autoencoder_ready"


class TestAIStatusEdgeCases:
    """Edge case tests for AI status endpoint."""
    
    @pytest.mark.asyncio
    async def test_ai_status_no_baseline(
        self, client, db_session, test_user, owned_vehicle, auth_headers
    ):
        """Test behavior when vehicle has no baseline record."""
        response = client.get(
            f"/api/predictions/{owned_vehicle.profile_id}/ai-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["baseline_phase"] == "collecting"
        assert data["data_points"] == 0
        assert data["trip_count"] == 0
        assert data["intelligence_level"] == "minimal"
    
    @pytest.mark.asyncio
    async def test_ai_status_corrupted_sensor_stats(
        self, client, db_session, test_user, owned_vehicle, auth_headers
    ):
        """Test handling of corrupted sensor_stats JSON."""
        baseline = VehicleBaseline(
            profile_id=owned_vehicle.profile_id,
            phase="baseline_ready",
            data_points=1000,
            trip_count=50,
            sensor_stats="not valid json",
            created_at=time.time(),
        )
        db_session.add(baseline)
        await db_session.commit()
        
        response = client.get(
            f"/api/predictions/{owned_vehicle.profile_id}/ai-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still return valid response with empty sensor_stats
        assert data["baseline_phase"] == "baseline_ready"
        assert len(data["model_statuses"]) == 9
