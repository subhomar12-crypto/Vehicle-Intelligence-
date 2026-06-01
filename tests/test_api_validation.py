"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Api Validation

Test suite for API input validation.
"""

import pytest
from pydantic import ValidationError
from api_endpoints_extended import (
    FillupRequest,
    CustomAlertRule,
    CreateProfileRequest,
    GeofenceCreate,
    AlertSeverity,
    AlertCondition
)

class TestFillupRequestValidation:
    """Test FillupRequest validation."""

    def test_valid_fillup(self):
        """Valid fillup request passes."""
        req = FillupRequest(
            profile_id=1,
            profile_name="Test Car",
            liters=45.5,
            cost=150.00,
            odometer_km=50000
        )
        assert req.profile_id == 1

    def test_negative_profile_id_rejected(self):
        """Negative profile ID must be rejected."""
        with pytest.raises(ValidationError):
            FillupRequest(
                profile_id=-1,
                profile_name="Test",
                liters=45,
                cost=100,
                odometer_km=50000
            )

    def test_excessive_liters_rejected(self):
        """Unrealistic fuel amounts must be rejected."""
        with pytest.raises(ValidationError):
            FillupRequest(
                profile_id=1,
                profile_name="Test",
                liters=1000,  # No car holds 1000L
                cost=100,
                odometer_km=50000
            )

    def test_sql_injection_sanitized(self):
        """SQL injection attempts must be sanitized."""
        req = FillupRequest(
            profile_id=1,
            profile_name="Test'; DROP TABLE users;--",
            liters=45,
            cost=100,
            odometer_km=50000
        )
        assert "DROP" not in req.profile_name
        assert ";" not in req.profile_name

    def test_xss_attack_sanitized(self):
        """XSS attempts must be sanitized."""
        req = FillupRequest(
            profile_id=1,
            profile_name="<script>alert('xss')</script>",
            liters=45,
            cost=100,
            odometer_km=50000
        )
        assert "<" not in req.profile_name
        assert ">" not in req.profile_name

class TestGeofenceValidation:
    """Test GeofenceCreate validation."""

    def test_valid_geofence(self):
        """Valid geofence passes."""
        geo = GeofenceCreate(
            geofence_id="home_zone_1",
            name="Home",
            center_lat=25.286,
            center_lon=51.534,
            radius_km=0.5
        )
        assert geo.radius_km == 0.5

    def test_invalid_latitude_rejected(self):
        """Latitude outside -90 to 90 must be rejected."""
        with pytest.raises(ValidationError):
            GeofenceCreate(
                geofence_id="test",
                name="Test",
                center_lat=91,  # Invalid
                center_lon=51,
                radius_km=1
            )

    def test_invalid_longitude_rejected(self):
        """Longitude outside -180 to 180 must be rejected."""
        with pytest.raises(ValidationError):
            GeofenceCreate(
                geofence_id="test",
                name="Test",
                center_lat=25,
                center_lon=181,  # Invalid
                radius_km=1
            )

    def test_geofence_id_alphanumeric_only(self):
        """Geofence ID must be alphanumeric with underscores/dashes."""
        with pytest.raises(ValidationError):
            GeofenceCreate(
                geofence_id="test zone!@#",  # Invalid characters
                name="Test",
                center_lat=25,
                center_lon=51,
                radius_km=1
            )

class TestVINValidation:
    """Test VIN validation in CreateProfileRequest."""

    def test_valid_vin_accepted(self):
        """Valid VIN passes."""
        req = CreateProfileRequest(
            name="My Car",
            vin="1HGBH41JXMN109186"
        )
        assert req.vin == "1HGBH41JXMN109186"

    def test_vin_with_invalid_chars_rejected(self):
        """VINs with I, O, Q are invalid per standard."""
        with pytest.raises(ValidationError):
            CreateProfileRequest(
                name="My Car",
                vin="1HGBH41JXIN109186"  # 'I' is invalid in VIN
            )

    def test_empty_vin_allowed(self):
        """Empty VIN is allowed (optional field)."""
        req = CreateProfileRequest(
            name="My Car",
            vin=""
        )
        assert req.vin == ""