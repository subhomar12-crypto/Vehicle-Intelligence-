"""Tests for SHAP explainer."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from predict.core.ai.shap_explainer import (
    SHAPExplainer,
    COMPONENT_IDS,
    FEATURE_NAMES,
    SENSOR_COLUMNS,
)


class TestSHAPExplainer:
    """Test SHAPExplainer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.explainer = SHAPExplainer()

    def test_feature_names_count(self):
        """FEATURE_NAMES has 75 entries (5 stats × 15 sensors)."""
        assert len(FEATURE_NAMES) == 75
        assert "rpm_mean" in FEATURE_NAMES
        assert "rpm_std" in FEATURE_NAMES
        assert "coolant_temp_max" in FEATURE_NAMES

    def test_sensor_columns_defined(self):
        """SENSOR_COLUMNS has 15 entries."""
        assert len(SENSOR_COLUMNS) == 15

    def test_component_ids_match(self):
        """COMPONENT_IDS matches canonical IDs."""
        assert len(COMPONENT_IDS) == 10
        assert "engine_oil" in COMPONENT_IDS
        assert "battery" in COMPONENT_IDS

    def test_fit_without_shap(self):
        """Fit handles missing shap library gracefully."""
        # This will fail to import shap if not installed
        # but should not crash
        mock_models = {}
        background = np.random.randn(20, 75)
        
        # Should not raise
        self.explainer.fit(mock_models, background)
        
        # Won't be fitted if shap not installed
        # But code should run without error

    def test_explain_prediction_not_fitted(self):
        """Explanation before fit returns None."""
        features = np.random.randn(75)
        
        result = self.explainer.explain_prediction("engine_oil", features)
        
        assert result is None

    def test_explain_all_components_not_fitted(self):
        """All explanations before fit return None."""
        features = np.random.randn(75)
        
        results = self.explainer.explain_all_components(features)
        
        assert all(v is None for v in results.values())

    def test_get_global_importance_not_fitted(self):
        """Global importance before fit returns None."""
        X = np.random.randn(50, 75)
        
        result = self.explainer.get_global_importance("engine_oil", X)
        
        assert result is None

    def test_explain_to_text_none(self):
        """Text explanation for None returns default."""
        text = self.explainer.explain_to_text(None)
        
        assert "No explanation available" in text

    def test_explain_to_text_basic(self):
        """Text explanation generated from explanation dict."""
        explanation = {
            "component": "engine_oil",
            "base_value": 0.5,
            "prediction_value": 0.8,
            "top_contributions": [
                {
                    "feature": "rpm_max",
                    "contribution": 0.15,
                    "direction": "increases_failure",
                    "magnitude": 0.15,
                },
                {
                    "feature": "coolant_temp_mean",
                    "contribution": 0.10,
                    "direction": "increases_failure",
                    "magnitude": 0.10,
                },
            ],
            "n_features_considered": 75,
        }
        
        text = self.explainer.explain_to_text(explanation)
        
        assert "engine_oil" in text
        assert "rpm max" in text.lower()
        assert "increases" in text

    def test_explain_to_text_decreases(self):
        """Text explanation handles decreasing contributions."""
        explanation = {
            "component": "battery",
            "base_value": 0.5,
            "prediction_value": 0.3,
            "top_contributions": [
                {
                    "feature": "battery_voltage_mean",
                    "contribution": -0.20,
                    "direction": "decreases_failure",
                    "magnitude": 0.20,
                },
            ],
            "n_features_considered": 75,
        }
        
        text = self.explainer.explain_to_text(explanation)
        
        assert "battery voltage mean" in text.lower()
        assert "decreases" in text

    def test_serialize(self):
        """Serialization saves metadata."""
        self.explainer.is_fitted = True
        self.explainer.background_data = np.random.randn(50, 75)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self.explainer.serialize(tmpdir)
            
            assert "metadata" in paths
            assert Path(paths["metadata"]).exists()
            
            # Verify content
            with open(paths["metadata"], 'r') as f:
                metadata = json.load(f)
            
            assert metadata["n_features"] == 75
            assert metadata["fitted"] is True

    def test_generate_summary_plot_not_fitted(self):
        """Plot generation before fit returns False."""
        X = np.random.randn(10, 75)
        
        result = self.explainer.generate_summary_plot("engine_oil", X, "/tmp/test.png")
        
        assert result is False

    def test_generate_force_plot_not_fitted(self):
        """Force plot generation before fit returns False."""
        features = np.random.randn(75)
        
        result = self.explainer.generate_force_plot("engine_oil", features, "/tmp/test.html")
        
        assert result is False

    def test_fit_with_mock_models(self):
        """Fit with mock XGBoost models."""
        pytest.importorskip("shap", reason="shap not installed")
        
        # Create mock XGBoost-like models
        try:
            import xgboost as xgb
            
            # Train simple XGBoost models
            mock_models = {}
            X_train = np.random.randn(100, 75)
            y_train = np.random.randint(0, 2, 100)
            
            for component in ["engine_oil", "battery"]:
                model = xgb.XGBClassifier(n_estimators=5, max_depth=3)
                model.fit(X_train, y_train)
                mock_models[component] = model
            
            background = np.random.randn(20, 75)
            
            # Should fit without error
            self.explainer.fit(mock_models, background)
            
            assert self.explainer.is_fitted
            assert len(self.explainer.explainers) == 2
            
        except ImportError:
            pytest.skip("xgboost not installed")

    def test_explain_prediction_with_mock(self):
        """Explain prediction with fitted explainer."""
        pytest.importorskip("shap", reason="shap not installed")
        pytest.importorskip("xgboost", reason="xgboost not installed")
        
        import xgboost as xgb
        
        # Create and fit model
        X_train = np.random.randn(100, 75)
        y_train = np.random.randint(0, 2, 100)
        
        model = xgb.XGBClassifier(n_estimators=5, max_depth=3)
        model.fit(X_train, y_train)
        
        # Fit explainer
        self.explainer.fit({"engine_oil": model}, X_train[:20])
        
        # Explain
        features = np.random.randn(75)
        explanation = self.explainer.explain_prediction("engine_oil", features, top_k=5)
        
        assert explanation is not None
        assert explanation["component"] == "engine_oil"
        assert "top_contributions" in explanation
        assert len(explanation["top_contributions"]) <= 5
        
        # Check contribution format
        contrib = explanation["top_contributions"][0]
        assert "feature" in contrib
        assert "contribution" in contrib
        assert "direction" in contrib
        assert contrib["direction"] in ["increases_failure", "decreases_failure"]

    def test_global_importance_with_mock(self):
        """Global importance with fitted explainer."""
        pytest.importorskip("shap", reason="shap not installed")
        pytest.importorskip("xgboost", reason="xgboost not installed")
        
        import xgboost as xgb
        
        # Create and fit model
        X_train = np.random.randn(100, 75)
        y_train = np.random.randint(0, 2, 100)
        
        model = xgb.XGBClassifier(n_estimators=5, max_depth=3)
        model.fit(X_train, y_train)
        
        # Fit explainer
        self.explainer.fit({"engine_oil": model}, X_train[:20])
        
        # Get global importance
        X_test = np.random.randn(50, 75)
        importance = self.explainer.get_global_importance("engine_oil", X_test)
        
        assert importance is not None
        assert len(importance) == 75
        
        # Check sorted by importance
        values = list(importance.values())
        assert values == sorted(values, reverse=True)

    def test_explain_all_components_with_mock(self):
        """Explain all components with fitted explainer."""
        pytest.importorskip("shap", reason="shap not installed")
        pytest.importorskip("xgboost", reason="xgboost not installed")
        
        import xgboost as xgb
        
        # Create models for all components
        mock_models = {}
        X_train = np.random.randn(100, 75)
        y_train = np.random.randint(0, 2, 100)
        
        for component in ["engine_oil", "battery", "brakes"]:
            model = xgb.XGBClassifier(n_estimators=5, max_depth=3)
            model.fit(X_train, y_train)
            mock_models[component] = model
        
        # Fit explainer
        self.explainer.fit(mock_models, X_train[:20])
        
        # Explain all
        features = np.random.randn(75)
        explanations = self.explainer.explain_all_components(features, top_k=3)
        
        # Check fitted components have explanations
        assert explanations["engine_oil"] is not None
        assert explanations["battery"] is not None
        assert explanations["brakes"] is not None
        
        # Check unfitted components return None
        assert explanations["coolant_system"] is None

    def test_feature_names_format(self):
        """Feature names are in correct format (sensor_stat)."""
        for name in FEATURE_NAMES:
            parts = name.split("_")
            assert len(parts) >= 2
            stat = parts[-1]
            assert stat in ["mean", "std", "min", "max", "delta"]
