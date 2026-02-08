"""
Ensemble voting system for combining multiple ML models.

Combines predictions from LSTM, XGBoost, and other models for robust results.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ModelPrediction:
    """Single model prediction result."""
    model_name: str
    failure_probability: float
    weight: float
    confidence: float


class EnsembleVoter:
    """
    Ensemble voter combining multiple model predictions.
    
    Uses weighted voting based on model performance and confidence.
    """
    
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.weights: Dict[str, float] = {}
        self.min_confidence_threshold = 0.3
    
    def register_model(
        self,
        name: str,
        model: Any,
        weight: float = 1.0,
    ) -> None:
        """
        Register a model with the ensemble.
        
        Args:
            name: Model identifier
            model: Model instance with predict() method
            weight: Voting weight (higher = more influence)
        """
        self.models[name] = model
        self.weights[name] = weight
        logger.info(f"Registered model '{name}' with weight {weight}")
    
    def predict(
        self,
        data: Any,
        require_consensus: bool = False,
    ) -> Dict[str, Any]:
        """
        Make ensemble prediction using all registered models.
        
        Args:
            data: Input data for prediction
            require_consensus: If True, all models must agree on risk level
        
        Returns:
            Ensemble prediction with:
                - failure_probability: Weighted average
                - risk_level: LOW, MEDIUM, HIGH, CRITICAL
                - model_predictions: Individual model results
                - confidence: Overall confidence
                - consensus: Whether models agree
        """
        if not self.models:
            logger.warning("No models registered in ensemble")
            return self._fallback_prediction()
        
        # Get predictions from all models
        model_predictions = self._get_model_predictions(data)
        
        if not model_predictions:
            return self._fallback_prediction()
        
        # Calculate weighted average
        weighted_prob = self._calculate_weighted_average(model_predictions)
        
        # Determine risk level
        risk_level = self._determine_risk_level(weighted_prob)
        
        # Check consensus
        consensus = self._check_consensus(model_predictions)
        
        # Calculate overall confidence
        confidence = self._calculate_overall_confidence(model_predictions)
        
        result = {
            "failure_probability": round(weighted_prob, 4),
            "risk_level": risk_level,
            "confidence": round(confidence, 4),
            "consensus": consensus,
            "model_count": len(model_predictions),
            "model_predictions": [
                {
                    "model": p.model_name,
                    "probability": round(p.failure_probability, 4),
                    "weight": p.weight,
                    "confidence": round(p.confidence, 4),
                }
                for p in model_predictions
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Add warning if consensus required but not achieved
        if require_consensus and not consensus:
            result["warning"] = "Low consensus - models disagree on risk level"
        
        return result
    
    def _get_model_predictions(
        self,
        data: Any
    ) -> List[ModelPrediction]:
        """Get predictions from all registered models."""
        predictions = []
        
        for name, model in self.models.items():
            try:
                # Call model predict method
                if hasattr(model, 'predict'):
                    raw_pred = model.predict(data)
                else:
                    logger.warning(f"Model {name} has no predict method")
                    continue
                
                # Parse prediction
                prob, conf = self._parse_prediction(raw_pred, name)
                
                pred = ModelPrediction(
                    model_name=name,
                    failure_probability=prob,
                    weight=self.weights.get(name, 1.0),
                    confidence=conf,
                )
                predictions.append(pred)
            
            except Exception as e:
                logger.error(f"Model {name} prediction failed: {e}")
                continue
        
        return predictions
    
    def _parse_prediction(
        self,
        raw_pred: Any,
        model_name: str
    ) -> Tuple[float, float]:
        """Parse prediction result into probability and confidence."""
        if isinstance(raw_pred, dict):
            prob = raw_pred.get('failure_probability', 0.0)
            conf = raw_pred.get('confidence', 0.5)
        elif isinstance(raw_pred, (list, np.ndarray)):
            prob = float(raw_pred[0]) if len(raw_pred) > 0 else 0.0
            conf = 0.5
        else:
            prob = float(raw_pred)
            conf = 0.5
        
        # Clamp values
        prob = max(0.0, min(1.0, prob))
        conf = max(0.0, min(1.0, conf))
        
        return prob, conf
    
    def _calculate_weighted_average(
        self,
        predictions: List[ModelPrediction]
    ) -> float:
        """Calculate weighted average of predictions."""
        total_weight = sum(p.weight * p.confidence for p in predictions)
        
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(
            p.failure_probability * p.weight * p.confidence
            for p in predictions
        )
        
        return weighted_sum / total_weight
    
    def _determine_risk_level(self, probability: float) -> str:
        """Determine risk level from probability."""
        if probability < 0.2:
            return "LOW"
        elif probability < 0.4:
            return "MEDIUM"
        elif probability < 0.7:
            return "HIGH"
        else:
            return "CRITICAL"
    
    def _check_consensus(self, predictions: List[ModelPrediction]) -> bool:
        """Check if models agree on risk level."""
        if len(predictions) < 2:
            return True
        
        risk_levels = [
            self._determine_risk_level(p.failure_probability)
            for p in predictions
        ]
        
        # Check if all agree
        return len(set(risk_levels)) == 1
    
    def _calculate_overall_confidence(
        self,
        predictions: List[ModelPrediction]
    ) -> float:
        """Calculate overall confidence based on model confidences and agreement."""
        if not predictions:
            return 0.0
        
        # Average confidence weighted by model weights
        total_weight = sum(p.weight for p in predictions)
        avg_confidence = sum(p.confidence * p.weight for p in predictions) / total_weight
        
        # Penalize if models disagree significantly
        probs = [p.failure_probability for p in predictions]
        prob_std = np.std(probs)
        agreement_factor = max(0, 1 - prob_std)
        
        return avg_confidence * agreement_factor
    
    def _fallback_prediction(self) -> Dict[str, Any]:
        """Return fallback when no models available."""
        return {
            "failure_probability": 0.0,
            "risk_level": "UNKNOWN",
            "confidence": 0.0,
            "consensus": False,
            "model_count": 0,
            "model_predictions": [],
            "timestamp": datetime.utcnow().isoformat(),
            "note": "No models available for prediction",
        }
    
    def update_weight(self, model_name: str, weight: float) -> bool:
        """Update voting weight for a model."""
        if model_name not in self.models:
            return False
        
        self.weights[model_name] = weight
        logger.info(f"Updated weight for '{model_name}' to {weight}")
        return True
    
    def get_model_info(self) -> List[Dict[str, Any]]:
        """Get information about registered models."""
        return [
            {
                "name": name,
                "weight": self.weights.get(name, 1.0),
                "type": type(model).__name__,
            }
            for name, model in self.models.items()
        ]
