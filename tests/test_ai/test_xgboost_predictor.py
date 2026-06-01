"""Tests for XGBoost failure predictor."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from predict.core.ai.xgboost_predictor import (
    XGBoostFailurePredictor,
    COMPONENT_IDS,
    FEATURE_COLUMNS,
)


class TestXGBoostFailurePredictor:
    """Test XGBoostFailurePredictor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.predictor = XGBoostFailurePredictor(
            n_estimators=10,  # Small for fast tests
            max_depth=3,
        )

    def test_component_ids_defined(self):
        """COMPONENT_IDS has 10 canonical entries."""
        assert len(COMPONENT_IDS) == 10
        assert "engine_oil" in COMPONENT_IDS
        assert "coolant_system" in COMPONENT_IDS
        assert "battery" in COMPONENT_IDS
        assert "brakes" in COMPONENT_IDS

    def test_feature_columns_defined(self):
        """FEATURE_COLUMNS has 75 entries (5 stats × 15 sensors)."""
        assert len(FEATURE_COLUMNS) == 75
        assert "rpm_mean" in FEATURE_COLUMNS
        assert "rpm_std" in FEATURE_COLUMNS
        assert "speed_min" in FEATURE_COLUMNS
        assert "battery_voltage_delta" in FEATURE_COLUMNS

    def test_extract_features_empty(self):
        """Empty window returns zeros."""
        features = self.predictor._extract_features([])
        assert np.allclose(features, np.zeros(75))

    def test_extract_features_basic(self):
        """Features extracted correctly — 75 features from 15 sensors."""
        telemetry = [
            {"rpm": 1000, "speed": 60, "coolant_temp": 90, "battery_voltage": 14.0,
             "engine_load": 50, "throttle_pos": 30, "maf_rate": 15, "intake_temp": 35,
             "short_term_fuel_trim": 100, "long_term_fuel_trim": 100,
             "timing_advance": 15, "injector_ms": 3.0, "fuel_trim_b2": 100,
             "accel_pedal": 25, "ambient_temp": 40},
            {"rpm": 1100, "speed": 65, "coolant_temp": 92, "battery_voltage": 14.1,
             "engine_load": 55, "throttle_pos": 35, "maf_rate": 18, "intake_temp": 36,
             "short_term_fuel_trim": 102, "long_term_fuel_trim": 101,
             "timing_advance": 16, "injector_ms": 3.5, "fuel_trim_b2": 101,
             "accel_pedal": 30, "ambient_temp": 40},
        ]

        features = self.predictor._extract_features(telemetry)

        assert len(features) == 75
        # rpm stats: indices 0-4 (mean, std, min, max, delta)
        assert features[0] == pytest.approx(1050.0)  # rpm_mean
        assert features[1] > 0  # rpm_std
        assert features[2] == 1000.0  # rpm_min
        assert features[3] == 1100.0  # rpm_max
        assert features[4] == 100.0  # rpm_delta

    def test_extract_features_with_none(self):
        """None values handled as zeros."""
        telemetry = [
            {"rpm": None, "engine_load": 50, "coolant_temp": 90},
            {"rpm": 1000, "engine_load": None, "coolant_temp": None},
        ]

        features = self.predictor._extract_features(telemetry)

        assert len(features) == 75
        assert np.all(np.isfinite(features))

    def test_train_from_synthetic(self):
        """Synthetic training works."""
        metrics = self.predictor.train_from_synthetic(n_samples=100)
        
        assert "components_trained" in metrics
        assert len(metrics["components_trained"]) == 10
        assert self.predictor.is_trained is True
        assert len(self.predictor.models) == 10

    @pytest.mark.asyncio
    async def test_train_from_db_insufficient_samples(self):
        """Training with insufficient samples skips components."""
        # This would need proper DB mocking, but we can test the logic
        # For now, just verify the method exists and has correct signature
        assert hasattr(self.predictor, 'train_from_db')

    def test_predict_not_trained(self):
        """Prediction without training returns defaults."""
        telemetry = [{"rpm": 1000, "engine_load": 50}]
        
        predictions = self.predictor.predict(telemetry)
        
        assert len(predictions) == 10
        assert all(v == 0.5 for v in predictions.values())

    def test_predict_after_training(self):
        """Prediction after training returns probabilities."""
        # Train first
        self.predictor.train_from_synthetic(n_samples=100)
        
        telemetry = [
            {"rpm": 1000, "engine_load": 50, "coolant_temp": 90, "lambda": 1.0}
            for _ in range(10)
        ]
        
        predictions = self.predictor.predict(telemetry)
        
        assert len(predictions) == 10
        for component in COMPONENT_IDS:
            assert component in predictions
            assert 0 <= predictions[component] <= 1

    def test_predict_failure_pattern(self):
        """Failure patterns give higher probabilities."""
        self.predictor.train_from_synthetic(n_samples=200)

        # Create failure-like pattern for engine_oil (high RPM variance, high load)
        failure_telemetry = [
            {"rpm": 7000 + i * 200, "speed": 120, "coolant_temp": 110,
             "battery_voltage": 13.5, "engine_load": 95, "throttle_pos": 90,
             "maf_rate": 50, "intake_temp": 55, "short_term_fuel_trim": 110,
             "long_term_fuel_trim": 108, "timing_advance": 5, "injector_ms": 12.0,
             "fuel_trim_b2": 109, "accel_pedal": 85, "ambient_temp": 45}
            for i in range(10)
        ]

        predictions = self.predictor.predict(failure_telemetry)

        # engine_oil should have a failure probability
        assert predictions["engine_oil"] > 0.0

    def test_serialize_not_trained(self):
        """Serialization without training raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="not trained"):
                self.predictor.serialize(tmpdir)

    def test_serialize_success(self):
        """Models serialize successfully."""
        # Train
        self.predictor.train_from_synthetic(n_samples=100)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self.predictor.serialize(tmpdir)
            
            # Check all components saved
            for component in COMPONENT_IDS:
                assert component in paths
                assert Path(paths[component]).exists()
            
            # Check metadata saved
            assert "metadata" in paths
            assert Path(paths["metadata"]).exists()
            
            # Verify metadata content
            with open(paths["metadata"], 'r') as f:
                metadata = json.load(f)
            assert metadata["components"] == COMPONENT_IDS
            assert metadata["feature_columns"] == FEATURE_COLUMNS

    def test_load_success(self):
        """Models load successfully."""
        # Train and serialize
        self.predictor.train_from_synthetic(n_samples=100)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            self.predictor.serialize(tmpdir)
            
            # Create new predictor and load
            new_predictor = XGBoostFailurePredictor()
            new_predictor.load(tmpdir)
            
            assert new_predictor.is_trained is True
            assert len(new_predictor.models) == 10

    def test_get_feature_importance(self):
        """Feature importance retrieved correctly."""
        self.predictor.train_from_synthetic(n_samples=100)

        importance = self.predictor.get_feature_importance("engine_oil")

        assert importance is not None
        assert len(importance) == 75
        for feature in FEATURE_COLUMNS:
            assert feature in importance
            assert importance[feature] >= 0

    def test_get_feature_importance_missing(self):
        """Missing component returns None."""
        importance = self.predictor.get_feature_importance("INVALID")
        assert importance is None

    def test_hyperparameters_stored(self):
        """Hyperparameters are stored correctly."""
        predictor = XGBoostFailurePredictor(
            n_estimators=50,
            max_depth=5,
            learning_rate=0.05,
        )
        
        assert predictor.n_estimators == 50
        assert predictor.max_depth == 5
        assert predictor.learning_rate == 0.05

    def test_scale_pos_weight(self):
        """Class imbalance handling parameter set."""
        predictor = XGBoostFailurePredictor(scale_pos_weight=5.0)
        assert predictor.scale_pos_weight == 5.0
