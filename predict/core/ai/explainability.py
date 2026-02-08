"""
Explainability module for AI predictions.

Provides SHAP-based feature importance and human-readable explanations.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FeatureImportance:
    """Feature importance entry."""
    feature: str
    importance: float
    direction: str  # "positive" or "negative"
    description: str


class ExplainabilityEngine:
    """
    Generate explanations for AI predictions.
    
    Uses SHAP values and rule-based explanations to make
    predictions interpretable to users.
    """
    
    def __init__(self):
        self.feature_descriptions = {
            "engine_temp_c": "Engine temperature",
            "oil_temp_c": "Oil temperature",
            "rpm": "Engine RPM",
            "speed_kmh": "Vehicle speed",
            "throttle_position": "Throttle position",
            "coolant_temp_c": "Coolant temperature",
            "intake_temp_c": "Intake air temperature",
            "maf_rate": "Mass air flow rate",
            "fuel_level": "Fuel level",
            "battery_voltage": "Battery voltage",
        }
    
    def explain_prediction(
        self,
        prediction: Dict[str, Any],
        feature_values: Dict[str, Any],
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """
        Generate human-readable explanation for a prediction.
        
        Args:
            prediction: Prediction result dict
            feature_values: Current feature values
            top_n: Number of top factors to include
        
        Returns:
            Explanation dict with:
                - summary: Human-readable summary
                - key_factors: List of important factors
                - recommendations: Actionable recommendations
                - confidence_explanation: Why confidence is high/low
        """
        failure_prob = prediction.get("failure_probability", 0)
        risk_level = prediction.get("risk_level", "UNKNOWN")
        
        # Generate key factors (simplified - would use SHAP in production)
        key_factors = self._identify_key_factors(feature_values, top_n)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            risk_level, key_factors, feature_values
        )
        
        # Generate summary
        summary = self._generate_summary(
            failure_prob, risk_level, key_factors
        )
        
        return {
            "summary": summary,
            "risk_level": risk_level,
            "failure_probability": failure_prob,
            "key_factors": [
                {
                    "feature": f.feature,
                    "description": f.description,
                    "importance": round(f.importance, 4),
                    "direction": f.direction,
                    "current_value": feature_values.get(f.feature),
                }
                for f in key_factors
            ],
            "recommendations": recommendations,
            "confidence_explanation": self._explain_confidence(prediction),
        }
    
    def _identify_key_factors(
        self,
        feature_values: Dict[str, Any],
        top_n: int
    ) -> List[FeatureImportance]:
        """
        Identify key factors contributing to prediction.
        
        In production, this would use SHAP values from the model.
        For now, uses rule-based heuristics.
        """
        factors = []
        
        # Check critical thresholds
        thresholds = {
            "engine_temp_c": ("high", 110, 0.9),
            "coolant_temp_c": ("high", 105, 0.85),
            "oil_temp_c": ("high", 120, 0.8),
            "rpm": ("high", 5000, 0.7),
            "battery_voltage": ("low", 11.5, 0.75),
        }
        
        for feature, (direction, threshold, importance) in thresholds.items():
            value = feature_values.get(feature)
            if value is None:
                continue
            
            if direction == "high" and value > threshold:
                factors.append(FeatureImportance(
                    feature=feature,
                    importance=importance,
                    direction="positive",
                    description=f"{self.feature_descriptions.get(feature, feature)} is high ({value})",
                ))
            elif direction == "low" and value < threshold:
                factors.append(FeatureImportance(
                    feature=feature,
                    importance=importance,
                    direction="positive",
                    description=f"{self.feature_descriptions.get(feature, feature)} is low ({value})",
                ))
        
        # Sort by importance and take top N
        factors.sort(key=lambda x: x.importance, reverse=True)
        return factors[:top_n]
    
    def _generate_recommendations(
        self,
        risk_level: str,
        key_factors: List[FeatureImportance],
        feature_values: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations based on risk factors."""
        recommendations = []
        
        if risk_level == "LOW":
            recommendations.append("Continue regular maintenance schedule")
            return recommendations
        
        # Add specific recommendations based on factors
        for factor in key_factors:
            if factor.feature == "engine_temp_c":
                recommendations.append("Check cooling system immediately - engine overheating detected")
            elif factor.feature == "coolant_temp_c":
                recommendations.append("Inspect coolant level and radiator condition")
            elif factor.feature == "oil_temp_c":
                recommendations.append("Check oil level and quality - consider oil change")
            elif factor.feature == "battery_voltage":
                recommendations.append("Test battery and charging system")
            elif factor.feature == "rpm":
                recommendations.append("Avoid high RPM driving until inspection")
        
        # General recommendations by risk level
        if risk_level == "CRITICAL":
            recommendations.insert(0, "⚠️ STOP DRIVING - Seek immediate mechanical inspection")
        elif risk_level == "HIGH":
            recommendations.append("Schedule mechanic inspection within 24-48 hours")
        elif risk_level == "MEDIUM":
            recommendations.append("Schedule maintenance check within 1-2 weeks")
        
        return recommendations
    
    def _generate_summary(
        self,
        failure_prob: float,
        risk_level: str,
        key_factors: List[FeatureImportance]
    ) -> str:
        """Generate human-readable summary."""
        if risk_level == "LOW":
            return f"Vehicle health is good. Failure probability is low ({failure_prob:.1%})."
        
        factor_text = ""
        if key_factors:
            top_factor = key_factors[0]
            factor_text = f" Primary concern: {top_factor.description}."
        
        if risk_level == "CRITICAL":
            return f"CRITICAL RISK: Immediate attention required.{factor_text}"
        elif risk_level == "HIGH":
            return f"High risk detected ({failure_prob:.1%}).{factor_text}"
        else:
            return f"Moderate risk ({failure_prob:.1%}).{factor_text}"
    
    def _explain_confidence(self, prediction: Dict[str, Any]) -> str:
        """Explain why confidence is high or low."""
        confidence = prediction.get("confidence", 0)
        model_count = prediction.get("model_count", 0)
        consensus = prediction.get("consensus", False)
        
        if confidence > 0.8:
            return f"High confidence ({confidence:.1%}) based on {model_count} models agreeing."
        elif confidence > 0.5:
            if not consensus:
                return f"Moderate confidence ({confidence:.1%}) - models show some disagreement."
            return f"Moderate confidence ({confidence:.1%}) - limited data available."
        else:
            return f"Low confidence ({confidence:.1%}) - insufficient data or model disagreement."
    
    def calculate_shap_values(
        self,
        model: Any,
        features: np.ndarray,
        feature_names: List[str]
    ) -> Optional[np.ndarray]:
        """
        Calculate SHAP values for feature importance.
        
        Args:
            model: Trained model with predict method
            features: Feature array
            feature_names: List of feature names
        
        Returns:
            SHAP values array or None if calculation fails
        """
        try:
            import shap
            
            # Create explainer
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(features)
            
            return shap_values
        
        except ImportError:
            logger.warning("SHAP not installed, skipping SHAP calculation")
            return None
        
        except Exception as e:
            logger.error(f"SHAP calculation failed: {e}")
            return None
