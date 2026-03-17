"""
Ensemble voter that combines predictions from multiple models with uncertainty estimation.
"""

import logging
import time
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class _SimpleUncertaintyEstimator:
    """Inline replacement for deleted UncertaintyEstimator module."""

    def estimate(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        risks = [p["risk"] for p in predictions]
        if len(risks) < 2:
            return {
                "confidence": 0.7,
                "epistemic_uncertainty": 0.3,
                "confidence_level": "low",
                "models_agree": True,
                "should_suppress_alert": False,
                "should_abstain": False,
            }
        std = float(np.std(risks))
        confidence = max(0.5, min(1.0, 1.0 - (std / 0.5)))
        models_agree = std < 0.15
        return {
            "confidence": confidence,
            "epistemic_uncertainty": std,
            "confidence_level": "high" if confidence > 0.8 else ("medium" if confidence > 0.6 else "low"),
            "models_agree": models_agree,
            "should_suppress_alert": confidence < 0.5,
            "should_abstain": confidence < 0.3,
        }


class EnsembleVoter:
    """
    Combines predictions from multiple models using weighted voting.

    Includes uncertainty estimation for production safety.
    """

    def __init__(self):
        self.models: Dict[str, Dict[str, Any]] = {}
        self.uncertainty_estimator = _SimpleUncertaintyEstimator()
        logger.debug("EnsembleVoter initialized")
    
    def register_model(
        self,
        name: str,
        model: Any,
        weight: float = 1.0,
    ) -> None:
        """Register a model with the ensemble."""
        self.models[name] = {
            "model": model,
            "weight": weight,
        }
        logger.info(f"Registered model '{name}' with weight {weight}")
    
    async def predict(
        self,
        data: Dict[str, Any],
        component: str = "general",
    ) -> Dict[str, Any]:
        """
        Get ensemble prediction with uncertainty estimate.
        
        Args:
            data: Input sensor data
            component: Component being assessed
        
        Returns:
            Dict with ensemble prediction and uncertainty metrics
        """
        predictions = []
        
        # Collect predictions from all models
        for name, model_info in self.models.items():
            try:
                model = model_info["model"]
                
                # Get prediction from model
                if hasattr(model, 'predict'):
                    pred = await model.predict(data) if hasattr(model.predict, '__code__') and model.predict.__code__.co_flags & 0x80 else model.predict(data)
                else:
                    continue
                
                predictions.append({
                    "model": name,
                    "risk": float(pred) if isinstance(pred, (int, float)) else pred.get("risk", 0.5),
                    "weight": model_info["weight"],
                    "component": component,
                })
            
            except Exception as e:
                logger.warning(f"Model '{name}' failed to predict: {e}")
                continue
        
        if not predictions:
            logger.error("No models produced predictions")
            return {
                "risk": 0.5,
                "confidence": 0.0,
                "uncertainty": 1.0,
                "predictions": [],
                "timestamp": time.time(),
            }
        
        # Calculate weighted ensemble prediction
        total_weight = sum(p["weight"] for p in predictions)
        weighted_risk = sum(p["risk"] * p["weight"] for p in predictions) / total_weight
        
        # Estimate uncertainty
        uncertainty = self.uncertainty_estimator.estimate(predictions)
        
        result = {
            "risk": weighted_risk,
            "raw_risk": weighted_risk,
            "confidence": uncertainty["confidence"],
            "uncertainty": uncertainty["epistemic_uncertainty"],
            "confidence_level": uncertainty["confidence_level"],
            "models_agree": uncertainty["models_agree"],
            "should_suppress_alert": uncertainty["should_suppress_alert"],
            "should_abstain": uncertainty["should_abstain"],
            "predictions": predictions,
            "uncertainty_details": uncertainty,
            "timestamp": time.time(),
        }
        
        logger.debug(
            f"Ensemble prediction: risk={weighted_risk:.3f}, "
            f"confidence={uncertainty['confidence']:.3f}"
        )
        
        return result
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all registered models."""
        return {
            name: {
                "weight": info["weight"],
                "type": type(info["model"]).__name__,
            }
            for name, info in self.models.items()
        }
