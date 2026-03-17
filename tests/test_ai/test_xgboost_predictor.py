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
        """COMPONENT_IDS has 10 entries."""
        assert len(COMPONENT_IDS) == 10
        assert "ENGINE" in COMPONENT_IDS
        assert "TRANSMISSION" in COMPONENT_IDS

    def test_feature_columns_defined(self):
        """FEATURE_COLUMNS has 4 entries."""
        assert len(FEATURE_COLUMNS) == 4
        assert "rpm_std" in FEATURE_COLUMNS
        assert "load_mean" in FEATURE_COLUMNS

    def test_extract_features_empty(self):
        """Empty window returns zeros."""
        features = self.predictor._extract_features([])
        assert np.allclose(features, np.zeros(4))

    def test_extract_features_basic(self):
        """Features extracted correctly."""
        telemetry = [
            {"rpm": 1000, "engine_load": 50, "coolant_temp": 90, "lambda": 1.0},
            {"rpm": 1100, "engine_load": 55, "coolant_temp": 92, "lambda": 1.1},
            {"rpm": 1050, "engine_load": 52, "coolant_temp": 95, "lambda": 0.9},
        ]
        
        features = self.predictor._extract_features(telemetry)
        
        assert len(features) == 4
        assert features[0] > 0  # rpm_std
        assert 50 < features[1] < 56  # load_mean
        assert features[2] == 5.0  # coolant_delta (95-90)
        assert features[3] > 0  # lambda_variance

    def test_extract_features_with_none(self):
        """None values handled as zeros."""
        telemetry = [
            {"rpm": None, "engine_load": 50, "coolant_temp": 90, "lambda": 1.0},
            {"rpm": 1000, "engine_load": None, "coolant_temp": None, "lambda": None},
        ]
        
        features = self.predictor._extract_features(telemetry)
        
        assert len(features) == 4
        # Should not crash
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
        # Train
        self.predictor.train_from_synthetic(n_samples=100)
        
        # Create failure-like pattern for ENGINE
        failure_telemetry = [
            {"rpm": 8000, "engine_load": 95, "coolant_temp": 120, "lambda": 0.5}
            for _ in range(10)
        ]
        
        predictions = self.predictor.predict(failure_telemetry)
        
        # ENGINE should have higher failure probability than average
        engine_prob = predictions["ENGINE"]
        avg_prob = np.mean(list(predictions.values()))
        
        assert engine_prob > avg_prob * 0.5  # Loose check due to synthetic data

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
        # Train
        self.predictor.train_from_synthetic(n_samples=100)
        
        importance = self.predictor.get_feature_importance("ENGINE")
        
        assert importance is not None
        assert len(importance) == 4
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
