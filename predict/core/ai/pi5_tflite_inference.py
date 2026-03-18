"""Pi5 TFLite Inference — edge deployment for LSTM autoencoder models.

Pure Python inference using TensorFlow Lite runtime (no full TF).
Handles bundled normalization params for proper data preprocessing.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE = True
except ImportError:
    TFLITE_AVAILABLE = False
    # Fallback for testing without tflite_runtime
    import tensorflow as tf

logger = logging.getLogger(__name__)

# Feature columns matching data_loader
FEATURE_COLUMNS = [
    "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
    "throttle_pos", "maf_rate", "intake_temp", "short_term_fuel_trim",
    "long_term_fuel_trim", "timing_advance", "injector_ms",
    "fuel_trim_b2", "accel_pedal", "ambient_temp",
]


class Pi5TFLiteInference:
    """TFLite inference engine for Pi5 edge deployment."""
    
    def __init__(self, model_path: str):
        """Initialize TFLite interpreter.
        
        Args:
            model_path: Path to .tflite model file
        """
        self.model_path = Path(model_path)
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.norm_params = None
        self.threshold = None
        self.window_size = 60
        
    def load_model(self) -> bool:
        """Load TFLite model and normalization params.
        
        Returns:
            True if successful
        """
        if not self.model_path.exists():
            logger.error(f"Model file not found: {self.model_path}")
            return False
        
        try:
            # Load TFLite interpreter
            if TFLITE_AVAILABLE:
                self.interpreter = tflite.Interpreter(model_path=str(self.model_path))
            else:
                # Fallback for testing
                self.interpreter = tf.lite.Interpreter(model_path=str(self.model_path))
            
            self.interpreter.allocate_tensors()
            
            # Get input/output details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # Extract window size from input shape
            input_shape = self.input_details[0]['shape']
            if len(input_shape) >= 2:
                self.window_size = int(input_shape[1])
            
            logger.info(f"Loaded TFLite model: {self.model_path}")
            logger.info(f"Input shape: {input_shape}")
            
            # Load normalization params
            self._load_normalization_params()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load TFLite model: {e}")
            return False
    
    def _load_normalization_params(self) -> None:
        """Load normalization parameters from bundled .norm.json file."""
        norm_path = self.model_path.with_suffix('.norm.json')
        
        if not norm_path.exists():
            logger.warning(f"Normalization params not found: {norm_path}")
            return
        
        try:
            with open(norm_path, 'r') as f:
                self.norm_params = json.load(f)
            
            self.mins = np.array(self.norm_params['mins'], dtype=np.float32)
            self.maxs = np.array(self.norm_params['maxs'], dtype=np.float32)
            
            # Load threshold if present
            self.threshold = self.norm_params.get('threshold', 0.5)
            
            logger.info(f"Loaded normalization params from {norm_path}")
            
        except Exception as e:
            logger.error(f"Failed to load normalization params: {e}")
    
    def normalize(self, data: np.ndarray) -> np.ndarray:
        """Normalize data using loaded params.
        
        Args:
            data: Raw data (N, 15)
            
        Returns:
            Normalized data
        """
        if self.norm_params is None:
            logger.warning("No normalization params loaded, returning raw data")
            return data
        
        # Min-max normalization
        ranges = self.maxs - self.mins
        ranges[ranges == 0] = 1.0  # Avoid division by zero
        
        normalized = (data - self.mins) / ranges
        return normalized.astype(np.float32)
    
    def create_sequence(self, readings: List[Dict[str, Any]]) -> Optional[np.ndarray]:
        """Create input sequence from readings.
        
        Args:
            readings: List of telemetry readings
            
        Returns:
            Sequence array (1, window_size, 15) or None
        """
        if len(readings) < self.window_size:
            logger.warning(f"Insufficient readings: {len(readings)} < {self.window_size}")
            return None
        
        # Extract features
        data = []
        for reading in readings[-self.window_size:]:  # Take last window_size readings
            row = []
            for col in FEATURE_COLUMNS:
                val = reading.get(col)
                if val is None:
                    row.append(0.0)
                else:
                    try:
                        row.append(float(val))
                    except (TypeError, ValueError):
                        row.append(0.0)
            data.append(row)
        
        data = np.array(data, dtype=np.float32)
        
        # Normalize
        normalized = self.normalize(data)
        
        # Add batch dimension
        return np.expand_dims(normalized, axis=0)
    
    def predict(self, sequence: np.ndarray) -> Tuple[np.ndarray, float]:
        """Run inference on a sequence.
        
        Args:
            sequence: Input sequence (1, window_size, 15)
            
        Returns:
            (reconstructed_sequence, reconstruction_error)
        """
        if self.interpreter is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        # Set input tensor
        self.interpreter.set_tensor(self.input_details[0]['index'], sequence)
        
        # Run inference
        start_time = time.time()
        self.interpreter.invoke()
        inference_time = time.time() - start_time
        
        # Get output
        reconstructed = self.interpreter.get_tensor(self.output_details[0]['index'])
        
        # Calculate reconstruction error (MSE)
        error = np.mean((sequence - reconstructed) ** 2)
        
        logger.debug(f"Inference time: {inference_time*1000:.2f}ms, error: {error:.4f}")
        
        return reconstructed, float(error)
    
    def is_anomaly(self, error: float) -> Tuple[bool, float]:
        """Check if reconstruction error indicates anomaly.
        
        Args:
            error: Reconstruction error
            
        Returns:
            (is_anomaly, confidence)
        """
        if self.threshold is None:
            logger.warning("No threshold set, using default 0.5")
            self.threshold = 0.5
        
        is_anom = error > self.threshold
        
        # Confidence based on how far above threshold
        if is_anom:
            confidence = min(1.0, error / (self.threshold * 2))
        else:
            confidence = min(1.0, 1.0 - (error / self.threshold))
        
        return is_anom, confidence
    
    def process_window(self, readings: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Process a window of readings end-to-end.
        
        Args:
            readings: List of telemetry readings
            
        Returns:
            Result dict with prediction and anomaly info
        """
        sequence = self.create_sequence(readings)
        if sequence is None:
            return None
        
        reconstructed, error = self.predict(sequence)
        is_anom, confidence = self.is_anomaly(error)
        
        return {
            "reconstruction_error": error,
            "is_anomaly": is_anom,
            "confidence": confidence,
            "threshold": self.threshold,
            "window_size": self.window_size,
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information.
        
        Returns:
            Model info dict
        """
        info = {
            "model_path": str(self.model_path),
            "loaded": self.interpreter is not None,
            "window_size": self.window_size,
            "has_norm_params": self.norm_params is not None,
            "threshold": self.threshold,
        }
        
        if self.input_details:
            info["input_shape"] = self.input_details[0]['shape'].tolist()
            info["input_dtype"] = str(self.input_details[0]['dtype'])
        
        if self.output_details:
            info["output_shape"] = self.output_details[0]['shape'].tolist()
            info["output_dtype"] = str(self.output_details[0]['dtype'])
        
        return info


def load_pi5_model(model_dir: str, model_type: str = "health") -> Optional[Pi5TFLiteInference]:
    """Load model for Pi5 inference.
    
    Args:
        model_dir: Directory containing model files
        model_type: Type of model ('health', 'anomaly', 'context')
        
    Returns:
        Pi5TFLiteInference instance or None
    """
    model_dir = Path(model_dir)
    
    # Find latest model
    model_files = list(model_dir.glob(f"{model_type}_*.tflite"))
    if not model_files:
        logger.error(f"No {model_type} model found in {model_dir}")
        return None
    
    # Sort by modification time (newest first)
    latest_model = sorted(model_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    
    inference = Pi5TFLiteInference(str(latest_model))
    
    if not inference.load_model():
        return None
    
    return inference
