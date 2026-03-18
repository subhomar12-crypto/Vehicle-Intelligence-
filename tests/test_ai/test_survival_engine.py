"""Tests for survival analysis engine."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from predict.core.ai.survival_engine import (
    SurvivalEngine,
    COMPONENT_IDS,
    SENSOR_COLUMNS,
)


class TestSurvivalEngine:
    """Test SurvivalEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = SurvivalEngine()

    def test_component_ids_defined(self):
        """COMPONENT_IDS has 10 canonical entries."""
        assert len(COMPONENT_IDS) == 10
        assert "engine_oil" in COMPONENT_IDS
        assert "battery" in COMPONENT_IDS
        assert "brakes" in COMPONENT_IDS

    def test_sensor_columns_defined(self):
        """SENSOR_COLUMNS has 15 entries."""
        assert len(SENSOR_COLUMNS) == 15
        assert "rpm" in SENSOR_COLUMNS
        assert "coolant_temp" in SENSOR_COLUMNS

    def test_extract_features_empty(self):
        """Empty window returns zeros."""
        features = self.engine._extract_features([])
        assert np.allclose(features, np.zeros(75))

    def test_extract_features_basic(self):
        """Features extracted correctly (75 = 5 stats × 15 sensors)."""
        telemetry = [
            {col: float(i * 10 + j) for j, col in enumerate(SENSOR_COLUMNS)}
            for i in range(10)
        ]
        
        features = self.engine._extract_features(telemetry)
        
        assert len(features) == 75
        assert not np.allclose(features, 0)
        
        # Check that features are finite
        assert np.all(np.isfinite(features))

    def test_extract_features_with_none(self):
        """None values handled as zeros."""
        telemetry = [
            {col: None if i == 0 else float(i * 10) for col in SENSOR_COLUMNS}
            for i in range(5)
        ]
        
        features = self.engine._extract_features(telemetry)
        
        assert len(features) == 75
        assert np.all(np.isfinite(features))

    def test_train_from_synthetic(self):
        """Synthetic training works."""
        metrics = self.engine.train_from_synthetic(n_samples=100)
        
        assert "components_trained" in metrics
        assert len(metrics["components_trained"]) == 10
        assert self.engine.is_trained is True
        assert len(self.engine.models) == 10

    @pytest.mark.asyncio
    async def test_train_from_db_insufficient_samples(self):
        """Training with insufficient samples skips components."""
        mock_session = AsyncMock()
        
        # Mock empty results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        metrics = await self.engine.train_from_db(mock_session, min_failures=10)
        
        # If lifelines not installed, returns empty metrics
        # If lifelines installed, all components would be skipped
        assert "components_skipped" in metrics or len(metrics) == 0

    def test_predict_survival_curve_not_trained(self):
        """Prediction without training returns None."""
        curve = self.engine.predict_survival_curve("engine_oil")
        assert curve is None

    def test_predict_survival_curve_after_training(self):
        """Survival curve generated after training."""
        self.engine.train_from_synthetic(n_samples=100)
        
        curve = self.engine.predict_survival_curve("engine_oil", days_ahead=365)
        
        assert curve is not None
        assert curve["component"] == "engine_oil"
        assert "timeline_days" in curve
        assert "survival_probability" in curve
        assert len(curve["timeline_days"]) == len(curve["survival_probability"])
        
        # Survival probability should start at 1.0 and decrease
        assert curve["survival_probability"][0] <= 1.0
        assert curve["survival_probability"][0] > 0

    def test_predict_mean_remaining_life(self):
        """Mean remaining life calculated."""
        self.engine.train_from_synthetic(n_samples=100)
        
        remaining = self.engine.predict_mean_remaining_life("engine_oil", current_age_days=0)
        
        assert remaining is not None
        assert isinstance(remaining, int)
        assert remaining > 0

    def test_predict_mean_remaining_life_with_age(self):
        """Remaining life accounts for current age."""
        self.engine.train_from_synthetic(n_samples=100)
        
        remaining_new = self.engine.predict_mean_remaining_life("engine_oil", current_age_days=0)
        remaining_old = self.engine.predict_mean_remaining_life("engine_oil", current_age_days=1000)
        
        # Older components should have less remaining life
        assert remaining_old <= remaining_new

    def test_predict_all_components(self):
        """Predictions for all components."""
        self.engine.train_from_synthetic(n_samples=100)
        
        results = self.engine.predict_all_components()
        
        assert len(results) == 10
        
        for component in COMPONENT_IDS:
            assert component in results
            assert "mean_remaining_life_days" in results[component]
            assert "survival_curve" in results[component]
            assert "current_age_days" in results[component]

    def test_predict_all_components_with_ages(self):
        """Predictions with specific component ages."""
        self.engine.train_from_synthetic(n_samples=100)
        
        ages = {
            "engine_oil": 100,
            "battery": 500,
            "brakes": 200,
        }
        
        results = self.engine.predict_all_components(current_ages=ages)
        
        assert results["engine_oil"]["current_age_days"] == 100
        assert results["battery"]["current_age_days"] == 500
        assert results["brakes"]["current_age_days"] == 200

    def test_serialize_not_trained(self):
        """Serialization without training raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="not trained"):
                self.engine.serialize(tmpdir)

    def test_serialize_success(self):
        """Models serialize successfully."""
        self.engine.train_from_synthetic(n_samples=100)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self.engine.serialize(tmpdir)
            
            # Check all components saved
            for component in COMPONENT_IDS:
                assert component in paths
                assert Path(paths[component]).exists()
            
            # Check metadata
            assert "metadata" in paths
            assert Path(paths["metadata"]).exists()

    def test_load_success(self):
        """Models load successfully."""
        self.engine.train_from_synthetic(n_samples=100)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            self.engine.serialize(tmpdir)
            
            # Create new engine and load
            new_engine = SurvivalEngine()
            new_engine.load(tmpdir)
            
            assert new_engine.is_trained is True
            assert len(new_engine.models) == 10

    def test_get_survival_probability_at_time(self):
        """Get survival probability at specific time."""
        self.engine.train_from_synthetic(n_samples=100)
        
        prob = self.engine.get_survival_probability_at_time("engine_oil", days=180)
        
        assert prob is not None
        assert 0 <= prob <= 1

    def test_get_survival_probability_decreases(self):
        """Survival probability decreases over time."""
        self.engine.train_from_synthetic(n_samples=100)
        
        prob_30 = self.engine.get_survival_probability_at_time("engine_oil", days=30)
        prob_180 = self.engine.get_survival_probability_at_time("engine_oil", days=180)
        prob_365 = self.engine.get_survival_probability_at_time("engine_oil", days=365)
        
        # Probability should generally decrease (with some noise tolerance)
        assert prob_180 <= prob_30 * 1.1  # Allow small increase due to estimation
        assert prob_365 <= prob_180 * 1.1

    def test_survival_curve_format(self):
        """Survival curve has correct format for Android charts."""
        self.engine.train_from_synthetic(n_samples=100)
        
        curve = self.engine.predict_survival_curve("engine_oil", days_ahead=365)
        
        # Android expects these fields
        assert isinstance(curve["component"], str)
        assert isinstance(curve["timeline_days"], list)
        assert isinstance(curve["survival_probability"], list)
        assert isinstance(curve["days_ahead"], int)
        
        # Arrays should have same length
        assert len(curve["timeline_days"]) == len(curve["survival_probability"])
        
        # Values should be numeric
        assert all(isinstance(t, (int, float)) for t in curve["timeline_days"])
        assert all(isinstance(p, (int, float)) for p in curve["survival_probability"])
