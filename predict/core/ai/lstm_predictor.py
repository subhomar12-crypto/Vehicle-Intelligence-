"""
LSTM-based failure prediction.

Time series forecasting for vehicle health prediction using LSTM networks.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import numpy as np

from predict.core.ai.model_loader import get_model_loader

logger = logging.getLogger(__name__)


class LSTMPredictor:
    """
    LSTM predictor for vehicle failure forecasting.
    
    Predicts time-to-failure based on sequential OBD data.
    """
    
    def __init__(self, model_name: str = "lstm_failure_predictor"):
        self.model_name = model_name
        self.model = None
        self.sequence_length = 50  # Number of time steps to look back
        self.features = [
            "engine_temp_c",
            "oil_temp_c",
            "rpm",
            "speed_kmh",
            "throttle_position",
            "coolant_temp_c",
            "intake_temp_c",
            "maf_rate",
            "fuel_level",
            "battery_voltage",
        ]
        self._load_model()
    
    def _load_model(self) -> None:
        """Load the LSTM model from disk."""
        loader = get_model_loader()
        
        # Try pickle format first (Keras/TensorFlow models)
        self.model = loader.load_pickle_model(self.model_name)
        
        if self.model is None:
            # Try joblib format
            self.model = loader.load_sklearn_model(self.model_name)
        
        if self.model is None:
            logger.warning(f"LSTM model '{self.model_name}' not found, using fallback")
    
    def preprocess_sequence(
        self,
        obd_data: List[Dict[str, Any]]
    ) -> Optional[np.ndarray]:
        """
        Preprocess OBD data into LSTM input sequence.
        
        Args:
            obd_data: List of OBD readings (chronological order)
        
        Returns:
            Preprocessed array of shape (1, sequence_length, num_features)
            or None if insufficient data
        """
        if len(obd_data) < self.sequence_length:
            logger.warning(f"Insufficient data: {len(obd_data)} < {self.sequence_length}")
            return None
        
        # Take last sequence_length readings
        sequence = obd_data[-self.sequence_length:]
        
        # Extract features
        features_array = np.zeros((self.sequence_length, len(self.features)))
        
        for i, reading in enumerate(sequence):
            for j, feature in enumerate(self.features):
                value = reading.get(feature)
                if value is None:
                    # Use mean imputation or forward fill
                    value = self._get_default_value(feature)
                features_array[i, j] = float(value)
        
        # Normalize (z-score)
        features_array = self._normalize(features_array)
        
        # Add batch dimension
        return np.expand_dims(features_array, axis=0)
    
    def _get_default_value(self, feature: str) -> float:
        """Get default value for missing features."""
        defaults = {
            "engine_temp_c": 90.0,
            "oil_temp_c": 95.0,
            "rpm": 1500,
            "speed_kmh": 50.0,
            "throttle_position": 15.0,
            "coolant_temp_c": 90.0,
            "intake_temp_c": 35.0,
            "maf_rate": 15.0,
            "fuel_level": 50.0,
            "battery_voltage": 12.5,
        }
        return defaults.get(feature, 0.0)
    
    def _normalize(self, data: np.ndarray) -> np.ndarray:
        """
        Normalize data using z-score normalization.
        
        In production, use fitted scaler from training.
        """
        # Simple z-score (should use training scaler in production)
        mean = np.mean(data, axis=0)
        std = np.std(data, axis=0)
        std[std == 0] = 1  # Prevent division by zero
        return (data - mean) / std
    
    def predict(
        self,
        obd_data: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Predict failure probability and time-to-failure.
        
        Args:
            obd_data: List of OBD readings
        
        Returns:
            Prediction dict with:
                - failure_probability: 0-1 probability
                - time_to_failure_km: Estimated km until failure
                - time_to_failure_days: Estimated days until failure
                - confidence: Prediction confidence
        """
        if self.model is None:
            return self._fallback_prediction()
        
        # Preprocess
        X = self.preprocess_sequence(obd_data)
        if X is None:
            return None
        
        try:
            # Make prediction
            prediction = self.model.predict(X)
            
            # Parse prediction (depends on model output structure)
            if isinstance(prediction, np.ndarray):
                if prediction.ndim == 2 and prediction.shape[1] == 1:
                    failure_prob = float(prediction[0, 0])
                else:
                    failure_prob = float(prediction[0])
            else:
                failure_prob = float(prediction)
            
            # Calculate derived metrics
            time_to_failure_km = self._estimate_km_to_failure(failure_prob, obd_data)
            time_to_failure_days = self._estimate_days_to_failure(failure_prob)
            confidence = self._calculate_confidence(obd_data)
            
            return {
                "failure_probability": round(failure_prob, 4),
                "time_to_failure_km": round(time_to_failure_km, 1),
                "time_to_failure_days": round(time_to_failure_days, 1),
                "confidence": round(confidence, 4),
                "model": self.model_name,
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"LSTM prediction failed: {e}")
            return self._fallback_prediction()
    
    def _fallback_prediction(self) -> Dict[str, Any]:
        """Return conservative fallback prediction when model unavailable."""
        return {
            "failure_probability": 0.0,
            "time_to_failure_km": None,
            "time_to_failure_days": None,
            "confidence": 0.0,
            "model": "fallback",
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Model unavailable - using conservative estimates",
        }
    
    def _estimate_km_to_failure(
        self,
        failure_prob: float,
        obd_data: List[Dict[str, Any]]
    ) -> float:
        """Estimate kilometers until failure based on probability."""
        # Simple heuristic: higher probability = fewer km remaining
        if failure_prob < 0.1:
            return 5000.0
        elif failure_prob < 0.3:
            return 2000.0
        elif failure_prob < 0.5:
            return 1000.0
        elif failure_prob < 0.7:
            return 500.0
        else:
            return 100.0
    
    def _estimate_days_to_failure(self, failure_prob: float) -> float:
        """Estimate days until failure based on probability."""
        if failure_prob < 0.1:
            return 90.0
        elif failure_prob < 0.3:
            return 60.0
        elif failure_prob < 0.5:
            return 30.0
        elif failure_prob < 0.7:
            return 14.0
        else:
            return 7.0
    
    def _calculate_confidence(self, obd_data: List[Dict[str, Any]]) -> float:
        """Calculate prediction confidence based on data quality."""
        # More data = higher confidence
        data_ratio = min(len(obd_data) / self.sequence_length, 1.0)
        
        # Check for missing values
        completeness = self._check_completeness(obd_data)
        
        return data_ratio * completeness
    
    def _check_completeness(self, obd_data: List[Dict[str, Any]]) -> float:
        """Check data completeness (1.0 = no missing values)."""
        if not obd_data:
            return 0.0
        
        total_fields = len(obd_data) * len(self.features)
        missing_fields = 0
        
        for reading in obd_data:
            for feature in self.features:
                if reading.get(feature) is None:
                    missing_fields += 1
        
        return 1.0 - (missing_fields / total_fields)
