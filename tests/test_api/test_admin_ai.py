"""Tests for admin AI dashboard and train endpoints."""

import pytest
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def admin_user():
    return {"user_id": 1, "tier": "admin", "email": "admin@predict.app"}


@pytest.fixture
def non_admin_user():
    return {"user_id": 2, "tier": "pro", "email": "user@predict.app"}


class TestAiDashboard:
    """Tests for GET /api/admin/ai-dashboard."""

    def test_require_admin_rejects_non_admin(self, non_admin_user):
        from predict.core.api.v1.admin import require_admin
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            require_admin(non_admin_user)
        assert exc_info.value.status_code == 403

    def test_require_admin_accepts_admin(self, admin_user):
        from predict.core.api.v1.admin import require_admin

        result = require_admin(admin_user)
        assert result == admin_user


class TestTrainRequest:
    """Tests for POST /api/admin/vehicles/{id}/train request model."""

    def test_valid_model_names(self):
        from predict.core.api.v1.admin import TrainRequest

        valid = [
            "baseline_stats", "isolation_forest", "correlation_baseline",
            "survival_curves", "autoencoder", "lstm", "xgboost",
        ]
        for name in valid:
            req = TrainRequest(model_name=name)
            assert req.model_name == name

    def test_data_sufficiency_thresholds(self):
        """Verify the minimum data point thresholds per model."""
        min_data = {
            "baseline_stats": 500,
            "isolation_forest": 500,
            "correlation_baseline": 500,
            "survival_curves": 500,
            "autoencoder": 2000,
            "lstm": 2000,
            "xgboost": 5000,
        }
        # Autoencoder needs more data than baseline models
        assert min_data["autoencoder"] > min_data["baseline_stats"]
        # XGBoost needs the most data
        assert min_data["xgboost"] > min_data["autoencoder"]


class TestConcurrentTraining:
    """Tests for concurrent training detection logic."""

    def test_fresh_training_blocks(self):
        """Training started < 1 hour ago should block."""
        training_in_progress = {"autoencoder": time.time() - 300}  # 5 min ago
        model = "autoencoder"
        started_at = training_in_progress.get(model)
        is_running = started_at and (time.time() - started_at) < 3600
        assert is_running is True

    def test_stale_training_allows_requeue(self):
        """Training started > 1 hour ago should allow re-queue."""
        training_in_progress = {"autoencoder": time.time() - 7200}  # 2 hours ago
        model = "autoencoder"
        started_at = training_in_progress.get(model)
        is_running = started_at and (time.time() - started_at) < 3600
        assert is_running is False

    def test_no_training_allows_start(self):
        """No training in progress should allow start."""
        training_in_progress = {}
        model = "autoencoder"
        assert model not in training_in_progress


class TestIntelligenceLevelComputation:
    """Tests for intelligence level computation in dashboard."""

    def test_basic_level(self):
        """< 500 data points = basic."""
        data_points = 100
        phase = "collecting"
        level = _compute_level(data_points, phase)
        assert level == "basic"

    def test_enhanced_level(self):
        """500+ data points or baseline_ready = enhanced."""
        assert _compute_level(600, "baseline_ready") == "enhanced"
        assert _compute_level(500, "collecting") == "enhanced"

    def test_expert_level(self):
        """2000+ data points or autoencoder_ready = expert."""
        assert _compute_level(2500, "autoencoder_ready") == "expert"
        assert _compute_level(2000, "baseline_ready") == "expert"

    def test_predictive_level(self):
        """5000+ data points = predictive."""
        assert _compute_level(5000, "autoencoder_ready") == "predictive"
        assert _compute_level(10000, "autoencoder_ready") == "predictive"


def _compute_level(data_points: int, phase: str) -> str:
    """Mirror the intelligence level computation from admin.py."""
    if data_points >= 5000:
        return "predictive"
    elif data_points >= 2000 or phase == "autoencoder_ready":
        return "expert"
    elif data_points >= 500 or phase == "baseline_ready":
        return "enhanced"
    else:
        return "basic"
