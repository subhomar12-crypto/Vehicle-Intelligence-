"""SHAP explainability — feature attribution for XGBoost predictions.

Uses shap library to explain why each component failure probability was predicted.
Outputs per-component explanations with top feature contributions.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Sensor columns for feature names
SENSOR_COLUMNS = [
    "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
    "throttle_pos", "maf_rate", "intake_temp", "short_term_fuel_trim",
    "long_term_fuel_trim", "timing_advance", "injector_ms",
    "fuel_trim_b2", "accel_pedal", "ambient_temp",
]

# Generate 75 feature names (5 stats × 15 sensors)
FEATURE_NAMES = []
for sensor in SENSOR_COLUMNS:
    for stat in ["mean", "std", "min", "max", "delta"]:
        FEATURE_NAMES.append(f"{sensor}_{stat}")

# Canonical component IDs
COMPONENT_IDS = [
    "engine_oil",
    "coolant_system", 
    "battery",
    "brakes",
    "transmission_fluid",
    "spark_plugs",
    "catalytic_converter",
    "o2_sensors",
    "air_filter",
    "fuel_system",
]


class SHAPExplainer:
    """SHAP-based explainability for XGBoost predictions."""
    
    def __init__(self):
        """Initialize SHAP explainer."""
        self.explainers: Dict[str, Any] = {}  # Component -> TreeExplainer
        self.background_data: Optional[np.ndarray] = None
        self.is_fitted = False
        
    def fit(self, xgboost_models: Dict[str, Any], background_data: np.ndarray) -> None:
        """Fit SHAP explainers for each component model.
        
        Args:
            xgboost_models: Dict mapping component -> XGBoost model
            background_data: Background dataset for SHAP (N, 75)
        """
        try:
            import shap
        except ImportError:
            logger.error("shap library not installed. Install with: pip install shap")
            return
        
        if len(background_data) < 10:
            logger.warning("Insufficient background data for SHAP")
            return
        
        self.background_data = background_data
        
        for component, model in xgboost_models.items():
            try:
                # TreeExplainer for XGBoost
                explainer = shap.TreeExplainer(model)
                self.explainers[component] = explainer
                logger.info(f"Fitted SHAP explainer for {component}")
            except Exception as e:
                logger.error(f"Failed to fit SHAP for {component}: {e}")
        
        self.is_fitted = len(self.explainers) > 0
    
    def explain_prediction(
        self,
        component: str,
        features: np.ndarray,
        top_k: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Explain a single prediction.
        
        Args:
            component: Component ID
            features: Feature vector (75,)
            top_k: Number of top features to return
            
        Returns:
            Explanation dict or None
        """
        if not self.is_fitted or component not in self.explainers:
            return None
        
        try:
            explainer = self.explainers[component]
            
            # Compute SHAP values
            shap_values = explainer.shap_values(features.reshape(1, -1))
            
            # Handle binary classification (shap_values might be list)
            if isinstance(shap_values, list):
                # For binary XGBoost, shap returns [class0_shap, class1_shap]
                # We want class1 (failure) explanations
                shap_values = shap_values[1]
            
            shap_values = shap_values.flatten()
            
            # Get top features by absolute SHAP value
            abs_shap = np.abs(shap_values)
            top_indices = np.argsort(abs_shap)[::-1][:top_k]
            
            # Build explanation
            contributions = []
            for idx in top_indices:
                feature_name = FEATURE_NAMES[idx]
                contribution = float(shap_values[idx])
                
                contributions.append({
                    "feature": feature_name,
                    "contribution": round(contribution, 4),
                    "direction": "increases_failure" if contribution > 0 else "decreases_failure",
                    "magnitude": round(abs(contribution), 4),
                })
            
            # Calculate base value (expected prediction)
            base_value = float(explainer.expected_value)
            if isinstance(base_value, (list, np.ndarray)):
                base_value = float(base_value[1])  # Class 1 (failure)
            
            # Actual prediction value
            prediction_value = base_value + np.sum(shap_values)
            
            return {
                "component": component,
                "base_value": round(base_value, 4),
                "prediction_value": round(prediction_value, 4),
                "top_contributions": contributions,
                "n_features_considered": len(FEATURE_NAMES),
            }
            
        except Exception as e:
            logger.error(f"SHAP explanation failed for {component}: {e}")
            return None
    
    def explain_all_components(
        self,
        features: np.ndarray,
        top_k: int = 5,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Explain predictions for all components.
        
        Args:
            features: Feature vector (75,)
            top_k: Number of top features per component
            
        Returns:
            Dict mapping component -> explanation
        """
        explanations = {}
        
        for component in COMPONENT_IDS:
            explanations[component] = self.explain_prediction(component, features, top_k)
        
        return explanations
    
    def get_global_importance(
        self,
        component: str,
        X: np.ndarray,
    ) -> Optional[Dict[str, float]]:
        """Get global feature importance for a component.
        
        Args:
            component: Component ID
            X: Dataset to compute importance on (N, 75)
            
        Returns:
            Dict mapping feature -> mean absolute SHAP value
        """
        if not self.is_fitted or component not in self.explainers:
            return None
        
        try:
            explainer = self.explainers[component]
            shap_values = explainer.shap_values(X)
            
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            
            # Mean absolute SHAP value per feature
            mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
            
            importance = {
                FEATURE_NAMES[i]: float(mean_abs_shap[i])
                for i in range(len(FEATURE_NAMES))
            }
            
            # Sort by importance
            importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
            
            return importance
            
        except Exception as e:
            logger.error(f"Global importance failed for {component}: {e}")
            return None
    
    def serialize(self, output_dir: str) -> Dict[str, str]:
        """Serialize SHAP configuration (not the explainers themselves).
        
        Note: SHAP explainers contain model references and can't be serialized directly.
        The XGBoost models should be serialized separately and SHAP refitted on load.
        
        Args:
            output_dir: Directory to save metadata
            
        Returns:
            Paths dict
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        metadata = {
            "feature_names": FEATURE_NAMES,
            "n_features": len(FEATURE_NAMES),
            "components": COMPONENT_IDS,
            "n_explainers": len(self.explainers),
            "fitted": self.is_fitted,
        }
        
        metadata_path = output_dir / "shap_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save background data sample (first 100 rows)
        if self.background_data is not None:
            background_path = output_dir / "shap_background.json"
            sample_size = min(100, len(self.background_data))
            background_sample = self.background_data[:sample_size].tolist()
            with open(background_path, 'w') as f:
                json.dump(background_sample, f)
        
        return {"metadata": str(metadata_path)}
    
    def generate_summary_plot(
        self,
        component: str,
        X: np.ndarray,
        output_path: str,
        max_display: int = 10,
    ) -> bool:
        """Generate SHAP summary plot for a component.
        
        Args:
            component: Component ID
            X: Dataset (N, 75)
            output_path: Path to save plot
            max_display: Maximum features to show
            
        Returns:
            True if successful
        """
        if not self.is_fitted or component not in self.explainers:
            return False
        
        try:
            import shap
            import matplotlib.pyplot as plt
            
            explainer = self.explainers[component]
            shap_values = explainer.shap_values(X)
            
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            
            plt.figure(figsize=(10, max_display))
            shap.summary_plot(
                shap_values,
                X,
                feature_names=FEATURE_NAMES,
                max_display=max_display,
                show=False,
            )
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Saved SHAP summary plot to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate summary plot: {e}")
            return False
    
    def generate_force_plot(
        self,
        component: str,
        features: np.ndarray,
        output_path: str,
    ) -> bool:
        """Generate SHAP force plot for a single prediction.
        
        Args:
            component: Component ID
            features: Feature vector (75,)
            output_path: Path to save plot (HTML)
            
        Returns:
            True if successful
        """
        if not self.is_fitted or component not in self.explainers:
            return False
        
        try:
            import shap
            
            explainer = self.explainers[component]
            shap_values = explainer.shap_values(features.reshape(1, -1))
            
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            
            shap_values = shap_values.flatten()
            
            # Generate HTML force plot
            base_value = explainer.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = base_value[1]
            
            force_plot = shap.force_plot(
                base_value,
                shap_values,
                features,
                feature_names=FEATURE_NAMES,
                show=False,
            )
            
            # Save as HTML
            shap.save_html(output_path, force_plot)
            
            logger.info(f"Saved SHAP force plot to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate force plot: {e}")
            return False
    
    def explain_to_text(
        self,
        explanation: Dict[str, Any],
        max_sentences: int = 3,
    ) -> str:
        """Convert explanation to human-readable text.
        
        Args:
            explanation: Explanation dict from explain_prediction()
            max_sentences: Maximum sentences to generate
            
        Returns:
            Human-readable explanation
        """
        if explanation is None:
            return "No explanation available."
        
        component = explanation["component"]
        contributions = explanation["top_contributions"]
        
        if not contributions:
            return f"No significant factors identified for {component}."
        
        # Build explanation text
        sentences = []
        
        # Top contributor
        top = contributions[0]
        feature = top["feature"].replace("_", " ")
        direction = "increases" if top["direction"] == "increases_failure" else "decreases"
        sentences.append(
            f"The {feature} reading {direction} the failure risk for {component}."
        )
        
        # Second contributor if available
        if len(contributions) > 1 and max_sentences >= 2:
            second = contributions[1]
            feature2 = second["feature"].replace("_", " ")
            direction2 = "increases" if second["direction"] == "increases_failure" else "decreases"
            sentences.append(
                f"Additionally, {feature2} {direction2} risk."
            )
        
        # Third contributor if available
        if len(contributions) > 2 and max_sentences >= 3:
            third = contributions[2]
            feature3 = third["feature"].replace("_", " ")
            direction3 = "increases" if third["direction"] == "increases_failure" else "decreases"
            sentences.append(
                f"Finally, {feature3} {direction3} risk."
            )
        
        return " ".join(sentences)
