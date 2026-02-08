"""
Unified AI module - orchestrates all prediction models.

Provides a single interface for:
- Failure prediction (LSTM + ensemble)
- Health scoring
- Maintenance recommendations
- Anomaly detection
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from predict.core.ai.lstm_predictor import LSTMPredictor
from predict.core.ai.ensemble_voter import EnsembleVoter
from predict.core.ai.explainability import ExplainabilityEngine

logger = logging.getLogger(__name__)


class UnifiedAI:
    """
    Unified AI interface for vehicle intelligence.
    
    Coordinates multiple models for comprehensive analysis.
    """
    
    def __init__(self):
        self.lstm = LSTMPredictor()
        self.ensemble = EnsembleVoter()
        self.explainer = ExplainabilityEngine()
        
        # Register models with ensemble
        self._setup_ensemble()
    
    def _setup_ensemble(self) -> None:
        """Register prediction models with ensemble voter."""
        # Register LSTM with higher weight (more accurate for time series)
        self.ensemble.register_model("lstm", self.lstm, weight=1.5)
        
        # TODO: Register XGBoost, Random Forest when available
        # self.ensemble.register_model("xgboost", xgb_model, weight=1.2)
    
    async def analyze_vehicle_health(
        self,
        vehicle_id: int,
        obd_data: List[Dict[str, Any]],
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        """
        Comprehensive vehicle health analysis.
        
        Args:
            vehicle_id: Vehicle identifier
            obd_data: Recent OBD readings
            include_explanation: Whether to include human-readable explanations
        
        Returns:
            Analysis result with predictions, scores, and recommendations
        """
        logger.info(f"Analyzing vehicle {vehicle_id} with {len(obd_data)} readings")
        
        # Get ensemble prediction
        ensemble_result = self.ensemble.predict(obd_data)
        
        # Get LSTM specific prediction (time-to-failure)
        lstm_result = self.lstm.predict(obd_data)
        
        # Calculate health score
        health_score = self._calculate_health_score(ensemble_result, lstm_result)
        
        # Build result
        result = {
            "vehicle_id": vehicle_id,
            "timestamp": datetime.utcnow().isoformat(),
            "health_score": health_score,
            "risk_level": ensemble_result.get("risk_level", "UNKNOWN"),
            "failure_probability": ensemble_result.get("failure_probability", 0),
            "predictions": {
                "ensemble": ensemble_result,
                "lstm": lstm_result,
            },
        }
        
        # Add time-to-failure if available
        if lstm_result and lstm_result.get("time_to_failure_km"):
            result["estimated_remaining_km"] = lstm_result["time_to_failure_km"]
        
        # Add explanation
        if include_explanation:
            # Get latest feature values
            feature_values = obd_data[-1] if obd_data else {}
            
            explanation = self.explainer.explain_prediction(
                prediction=ensemble_result,
                feature_values=feature_values,
            )
            result["explanation"] = explanation
        
        return result
    
    def quick_health_check(
        self,
        obd_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Quick health check for real-time monitoring.
        
        Args:
            obd_data: Recent OBD readings
        
        Returns:
            Simplified health status
        """
        if not obd_data:
            return {
                "status": "UNKNOWN",
                "health_score": 0,
                "message": "No data available",
            }
        
        # Use only LSTM for speed
        lstm_result = self.lstm.predict(obd_data)
        
        if lstm_result is None:
            return {
                "status": "UNKNOWN",
                "health_score": 0,
                "message": "Prediction failed",
            }
        
        prob = lstm_result.get("failure_probability", 0)
        
        # Quick status determination
        if prob < 0.2:
            status = "HEALTHY"
            message = "Vehicle operating normally"
        elif prob < 0.5:
            status = "ATTENTION"
            message = "Minor issues detected, monitor closely"
        elif prob < 0.7:
            status = "WARNING"
            message = "Issues detected, schedule maintenance"
        else:
            status = "CRITICAL"
            message = "Critical issues - seek immediate inspection"
        
        return {
            "status": status,
            "health_score": round((1 - prob) * 100),
            "failure_probability": prob,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def predict_maintenance_needs(
        self,
        vehicle_profile: Dict[str, Any],
        recent_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Predict upcoming maintenance needs.
        
        Args:
            vehicle_profile: Vehicle information
            recent_data: Recent OBD readings
        
        Returns:
            Maintenance predictions
        """
        # Analyze current health
        health = self.quick_health_check(recent_data)
        
        # TODO: Integrate with maintenance schedule from vehicle profile
        current_mileage = vehicle_profile.get("current_mileage", 0)
        
        recommendations = []
        
        if health["status"] == "CRITICAL":
            recommendations.append({
                "urgency": "immediate",
                "service": "Emergency inspection",
                "estimated_cost": None,
            })
        elif health["status"] == "WARNING":
            recommendations.append({
                "urgency": "soon",
                "service": "Maintenance check",
                "estimated_cost": {"min": 100, "max": 300, "currency": "SAR"},
            })
        
        return {
            "vehicle_id": vehicle_profile.get("id"),
            "current_health": health,
            "current_mileage": current_mileage,
            "recommended_services": recommendations,
            "next_service_due": None,  # TODO: Calculate from maintenance schedule
        }
    
    def _calculate_health_score(
        self,
        ensemble_result: Dict[str, Any],
        lstm_result: Optional[Dict[str, Any]]
    ) -> int:
        """
        Calculate overall health score (0-100).
        
        Higher score = healthier vehicle.
        """
        # Base score on failure probability
        failure_prob = ensemble_result.get("failure_probability", 0)
        base_score = int((1 - failure_prob) * 100)
        
        # Adjust based on LSTM time-to-failure if available
        if lstm_result:
            ttf_km = lstm_result.get("time_to_failure_km")
            if ttf_km is not None:
                if ttf_km < 500:
                    base_score = min(base_score, 30)
                elif ttf_km < 1000:
                    base_score = min(base_score, 50)
                elif ttf_km < 2000:
                    base_score = min(base_score, 70)
        
        return max(0, min(100, base_score))
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all AI models."""
        return {
            "lstm": {
                "available": self.lstm.model is not None,
                "name": self.lstm.model_name,
            },
            "ensemble": {
                "registered_models": len(self.ensemble.models),
                "model_info": self.ensemble.get_model_info(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }


# Singleton instance
_unified_ai: Optional[UnifiedAI] = None


def get_unified_ai() -> UnifiedAI:
    """Get singleton UnifiedAI instance."""
    global _unified_ai
    if _unified_ai is None:
        _unified_ai = UnifiedAI()
    return _unified_ai
