"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: LSTM Deep Learning Predictor

LSTM Deep Learning Predictor for Predictive Maintenance
========================================================
Time-series sequence learning for 30-60 day failure prediction.

Features:
- LSTM neural network for temporal pattern learning
- Sequence-to-prediction architecture
- Multi-component failure prediction
- Transfer learning support
- Model persistence and versioning
- Confidence calibration
"""

import numpy as np
import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from collections import deque
from config import get_config
from advanced_model_factory import get_model_factory, ModelArchitecture, PredictionTask, create_prediction_request

CONFIG = get_config()
logger = logging.getLogger(__name__)

# TensorFlow import with fallback
TENSORFLOW_AVAILABLE = False
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.models import Sequential, load_model, Model
    from tensorflow.keras.layers import (
        LSTM, Dense, Dropout, BatchNormalization,
        Input, Bidirectional, Attention, Concatenate,
        TimeDistributed, Masking, RepeatVector
    )
    from tensorflow.keras.callbacks import (
        EarlyStopping, ModelCheckpoint, ReduceLROnPlateau,
        TensorBoard
    )
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.regularizers import l2
    TENSORFLOW_AVAILABLE = True
    logger.info(f"TensorFlow {tf.__version__} loaded successfully for LSTM predictions")
except ImportError as e:
    # TensorFlow not installed
    Model = None  # type: ignore
    logger.warning(f"TensorFlow not installed - LSTM predictions disabled: {e}")
except Exception as e:
    # Other errors during TensorFlow import (GPU issues, version conflicts, etc.)
    Model = None  # type: ignore
    logger.warning(f"TensorFlow import failed - LSTM predictions disabled: {e}")


@dataclass
class LSTMConfig:
    """Configuration for LSTM model."""
    # Sequence parameters
    sequence_length: int = 60  # Days of history to use
    prediction_horizon: int = 30  # Days ahead to predict

    # Model architecture
    lstm_units_1: int = 128
    lstm_units_2: int = 64
    dense_units: int = 32
    dropout_rate: float = 0.3

    # Training parameters
    batch_size: int = 32
    epochs: int = 100
    learning_rate: float = 0.001
    early_stopping_patience: int = 15
    reduce_lr_patience: int = 5

    # Features
    feature_columns: List[str] = None

    def __post_init__(self):
        if self.feature_columns is None:
            self.feature_columns = [
                'rpm', 'speed', 'coolant_temp', 'engine_load',
                'intake_temp', 'maf', 'throttle_pos', 'fuel_pressure',
                'timing_advance', 'short_fuel_trim', 'long_fuel_trim',
                'voltage', 'rpm_stability', 'load_stability',
                'temp_rate_of_change', 'voltage_trend'
            ]


@dataclass
class PredictionResult:
    """Result of LSTM prediction."""
    failure_probability: float
    failure_type: str
    days_to_failure: int
    confidence: float
    contributing_features: Dict[str, float]
    model_version: str
    timestamp: str


class LSTMPredictor:
    """
    LSTM-based deep learning predictor for vehicle failures.
    Learns temporal patterns from OBD-II sensor sequences.
    """

    def __init__(self, config: LSTMConfig = None, model_path: str = None):
        """Initialize LSTM predictor."""
        self.config = config or LSTMConfig()
        self.model_path = Path(model_path or str(CONFIG.AI_MODELS_DIR / "lstm_models"))
        self.model_path.mkdir(parents=True, exist_ok=True)

        self.model = None  # TensorFlow Model when available
        self.scaler_params: Dict[str, Dict] = {}  # For feature normalization
        self.model_version = "0.0.0"
        self.training_history: List[Dict] = []
        self.is_trained = False

        # Component-specific models
        self.component_models: Dict[str, Any] = {}

        # Advanced model factory for architecture selection
        self.model_factory = get_model_factory()

        # Default architecture preference
        self.preferred_architecture = ModelArchitecture.LSTM_BASELINE

        # Failure type mapping
        self.failure_types = [
            'battery', 'alternator', 'starter', 'fuel_pump',
            'spark_plug', 'oxygen_sensor', 'catalytic_converter',
            'maf_sensor', 'thermostat', 'coolant_system',
            'transmission', 'ignition', 'no_failure'
        ]
        self.num_classes = len(self.failure_types)

        # Load existing model if available
        self._load_model()

        logger.info(f"LSTMPredictor initialized (TensorFlow available: {TENSORFLOW_AVAILABLE})")

    def _build_model(self, input_shape: Tuple[int, int]):
        """
        Build the LSTM model architecture.

        Args:
            input_shape: (sequence_length, num_features)

        Returns:
            TensorFlow Model
        """
        if not TENSORFLOW_AVAILABLE:
            raise RuntimeError("TensorFlow not available")

        inputs = Input(shape=input_shape, name='sequence_input')

        # Masking layer for variable-length sequences
        x = Masking(mask_value=0.0)(inputs)

        # First Bidirectional LSTM layer
        x = Bidirectional(
            LSTM(
                self.config.lstm_units_1,
                return_sequences=True,
                kernel_regularizer=l2(0.01),
                recurrent_regularizer=l2(0.01)
            ),
            name='bilstm_1'
        )(x)
        x = BatchNormalization()(x)
        x = Dropout(self.config.dropout_rate)(x)

        # Second LSTM layer
        x = LSTM(
            self.config.lstm_units_2,
            return_sequences=False,
            kernel_regularizer=l2(0.01)
        )(x)
        x = BatchNormalization()(x)
        x = Dropout(self.config.dropout_rate)(x)

        # Dense layers
        x = Dense(self.config.dense_units, activation='relu')(x)
        x = Dropout(self.config.dropout_rate / 2)(x)

        # Output heads
        # 1. Failure probability (binary)
        failure_prob = Dense(1, activation='sigmoid', name='failure_prob')(x)

        # 2. Failure type (multi-class)
        failure_type = Dense(self.num_classes, activation='softmax', name='failure_type')(x)

        # 3. Days to failure (regression, capped at prediction_horizon)
        days_to_failure = Dense(1, activation='linear', name='days_to_failure')(x)

        model = Model(
            inputs=inputs,
            outputs=[failure_prob, failure_type, days_to_failure],
            name='lstm_failure_predictor'
        )

        # Compile with appropriate losses
        model.compile(
            optimizer=Adam(learning_rate=self.config.learning_rate),
            loss={
                'failure_prob': 'binary_crossentropy',
                'failure_type': 'categorical_crossentropy',
                'days_to_failure': 'mse'
            },
            loss_weights={
                'failure_prob': 1.0,
                'failure_type': 0.5,
                'days_to_failure': 0.3
            },
            metrics={
                'failure_prob': ['accuracy', 'AUC'],
                'failure_type': ['accuracy'],
                'days_to_failure': ['mae']
            }
        )

        return model

    def _normalize_features(self, data: np.ndarray, fit: bool = False) -> np.ndarray:
        """Normalize features using min-max scaling."""
        if fit:
            self.scaler_params = {}
            for i in range(data.shape[-1]):
                col_data = data[:, :, i].flatten()
                col_data = col_data[~np.isnan(col_data)]
                if len(col_data) > 0:
                    self.scaler_params[i] = {
                        'min': float(np.min(col_data)),
                        'max': float(np.max(col_data))
                    }
                else:
                    self.scaler_params[i] = {'min': 0, 'max': 1}

        normalized = np.zeros_like(data)
        for i in range(data.shape[-1]):
            params = self.scaler_params.get(i, {'min': 0, 'max': 1})
            range_val = params['max'] - params['min']
            if range_val > 0:
                normalized[:, :, i] = (data[:, :, i] - params['min']) / range_val
            else:
                normalized[:, :, i] = 0

        return np.nan_to_num(normalized, nan=0.0)

    def prepare_sequences(
        self,
        obd_data: List[Dict],
        failure_info: Optional[Dict] = None
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """
        Prepare OBD data into sequences for training/prediction.

        Args:
            obd_data: List of OBD readings with timestamps
            failure_info: Optional dict with 'failure_occurred', 'failure_type', 'days_to_failure'

        Returns:
            X: Array of shape (num_sequences, sequence_length, num_features)
            y: Dict with labels if failure_info provided
        """
        if not obd_data:
            return np.array([]), None

        # Sort by timestamp
        sorted_data = sorted(obd_data, key=lambda x: x.get('timestamp', ''))

        # Extract features
        num_features = len(self.config.feature_columns)
        sequence_data = []

        for reading in sorted_data:
            features = []
            for col in self.config.feature_columns:
                val = reading.get(col, 0)
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    val = 0
                features.append(float(val))
            sequence_data.append(features)

        # Pad or truncate to sequence_length
        if len(sequence_data) < self.config.sequence_length:
            padding = [[0] * num_features] * (self.config.sequence_length - len(sequence_data))
            sequence_data = padding + sequence_data
        elif len(sequence_data) > self.config.sequence_length:
            sequence_data = sequence_data[-self.config.sequence_length:]

        X = np.array([sequence_data])  # Shape: (1, sequence_length, num_features)

        # Prepare labels if provided
        y = None
        if failure_info:
            y = {
                'failure_prob': np.array([[1.0 if failure_info.get('failure_occurred', False) else 0.0]]),
                'failure_type': self._encode_failure_type(failure_info.get('failure_type', 'no_failure')),
                'days_to_failure': np.array([[min(failure_info.get('days_to_failure', self.config.prediction_horizon),
                                                  self.config.prediction_horizon)]])
            }

        return X, y

    def _encode_failure_type(self, failure_type: str) -> np.ndarray:
        """One-hot encode failure type."""
        encoded = np.zeros((1, self.num_classes))
        try:
            idx = self.failure_types.index(failure_type.lower())
        except ValueError:
            idx = self.failure_types.index('no_failure')
        encoded[0, idx] = 1.0
        return encoded

    def _decode_failure_type(self, prediction: np.ndarray) -> Tuple[str, float]:
        """Decode failure type prediction."""
        idx = np.argmax(prediction)
        confidence = float(prediction[0, idx])
        return self.failure_types[idx], confidence

    def train(
        self,
        training_data: List[Dict],
        validation_split: float = 0.2,
        verbose: int = 1
    ) -> Dict[str, Any]:
        """
        Train the LSTM model.

        Args:
            training_data: List of dicts with 'sequence' (OBD data) and 'label' (failure info)
            validation_split: Fraction of data for validation
            verbose: Training verbosity

        Returns:
            Training history and metrics
        """
        if not TENSORFLOW_AVAILABLE:
            return {'error': 'TensorFlow not available'}

        if len(training_data) < 50:
            return {'error': f'Insufficient training data: {len(training_data)} samples (need 50+)'}

        logger.info(f"Starting LSTM training with {len(training_data)} samples")

        # Prepare all sequences
        X_list = []
        y_prob_list = []
        y_type_list = []
        y_days_list = []

        for item in training_data:
            X, y = self.prepare_sequences(item['sequence'], item.get('label'))
            if X.size > 0:
                X_list.append(X[0])
                if y:
                    y_prob_list.append(y['failure_prob'][0])
                    y_type_list.append(y['failure_type'][0])
                    y_days_list.append(y['days_to_failure'][0])

        if not X_list:
            return {'error': 'No valid sequences prepared'}

        X = np.array(X_list)
        y_prob = np.array(y_prob_list)
        y_type = np.array(y_type_list)
        y_days = np.array(y_days_list)

        # Normalize features
        X = self._normalize_features(X, fit=True)

        # Build model
        input_shape = (self.config.sequence_length, len(self.config.feature_columns))
        self.model = self._build_model(input_shape)

        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor='val_loss',
                patience=self.config.early_stopping_patience,
                restore_best_weights=True
            ),
            ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=self.config.reduce_lr_patience,
                min_lr=1e-6
            ),
            ModelCheckpoint(
                str(self.model_path / 'best_model.keras'),
                monitor='val_loss',
                save_best_only=True
            )
        ]

        # Train
        history = self.model.fit(
            X,
            {'failure_prob': y_prob, 'failure_type': y_type, 'days_to_failure': y_days},
            batch_size=self.config.batch_size,
            epochs=self.config.epochs,
            validation_split=validation_split,
            callbacks=callbacks,
            verbose=verbose
        )

        # Update state
        self.is_trained = True
        self.model_version = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save model
        self._save_model()

        # Record history
        training_record = {
            'version': self.model_version,
            'timestamp': datetime.now().isoformat(),
            'samples': len(training_data),
            'epochs_run': len(history.history['loss']),
            'final_loss': float(history.history['loss'][-1]),
            'final_val_loss': float(history.history.get('val_loss', [0])[-1]),
            'accuracy': float(history.history.get('failure_prob_accuracy', [0])[-1])
        }
        self.training_history.append(training_record)

        logger.info(f"Training complete. Version: {self.model_version}")

        return {
            'success': True,
            'version': self.model_version,
            'epochs': len(history.history['loss']),
            'final_loss': training_record['final_loss'],
            'accuracy': training_record['accuracy']
        }

    def set_architecture(self, architecture: ModelArchitecture):
        """
        Set the preferred model architecture for predictions.

        Args:
            architecture: Model architecture to use
        """
        self.preferred_architecture = architecture
        logger.info(f"Set preferred architecture to: {architecture.value}")

    def get_available_architectures(self) -> List[ModelArchitecture]:
        """Get list of available model architectures."""
        available = []
        for arch in ModelArchitecture:
            model = self.model_factory.get_model(arch)
            if model and model.is_available():
                available.append(arch)
        return available

    def predict(self, obd_data: List[Dict]) -> Optional[PredictionResult]:
        """
        Make a failure prediction from OBD sequence.

        Args:
            obd_data: Recent OBD readings (ideally sequence_length days)

        Returns:
            PredictionResult or None if prediction fails
        """
        # Try advanced architecture first
        if self.preferred_architecture != ModelArchitecture.LSTM_BASELINE:
            advanced_result = self._predict_with_advanced_architecture(obd_data)
            if advanced_result:
                return advanced_result

        # Fall back to original LSTM implementation
        return self._predict_with_baseline_lstm(obd_data)

    def _predict_with_advanced_architecture(self, obd_data: List[Dict]) -> Optional[PredictionResult]:
        """Make prediction using advanced model architectures."""
        try:
            # Create prediction request
            request = create_prediction_request(
                task=PredictionTask.FAILURE_PREDICTION,
                obd_data=obd_data,
                preferred_architectures=[self.preferred_architecture],
                allow_fallback=True
            )

            # Get prediction from factory
            result = self.model_factory.predict(request)

            if result.success and result.prediction:
                # Convert factory result to PredictionResult format
                prediction = result.prediction

                # Handle different prediction formats
                if hasattr(prediction, 'failure_probability'):
                    # Direct prediction object
                    return prediction
                elif isinstance(prediction, dict):
                    # Dictionary format (e.g., from ensemble)
                    failure_prob = prediction.get('ensemble_failure_probability',
                                                prediction.get('failure_probability', 0.0))

                    # Get failure type from component predictions if available
                    failure_type = 'no_failure'
                    component_preds = prediction.get('component_predictions', {})
                    for comp_pred in component_preds.values():
                        if isinstance(comp_pred, dict) and 'failure_type' in comp_pred:
                            if comp_pred.get('failure_probability', 0) > failure_prob:
                                failure_type = comp_pred['failure_type']
                                failure_prob = comp_pred['failure_probability']

                    return PredictionResult(
                        failure_probability=round(failure_prob, 3),
                        failure_type=failure_type,
                        days_to_failure=self.config.prediction_horizon,  # Default
                        confidence=round(result.confidence, 3),
                        contributing_features={},  # Would need to extract from components
                        model_version=result.model_version,
                        timestamp=result.timestamp
                    )

            logger.warning(f"Advanced architecture prediction failed: {result.error_message if not result.success else 'Unknown error'}")
            return None

        except Exception as e:
            logger.warning(f"Advanced architecture prediction error: {e}")
            return None

    def _predict_with_baseline_lstm(self, obd_data: List[Dict]) -> Optional[PredictionResult]:
        """Make prediction using baseline LSTM (original implementation)."""
        if not self.is_trained or self.model is None:
            logger.warning("Model not trained - using fallback prediction")
            return self._fallback_prediction(obd_data)

        if not TENSORFLOW_AVAILABLE:
            return self._fallback_prediction(obd_data)

        try:
            # Prepare sequence
            X, _ = self.prepare_sequences(obd_data)
            if X.size == 0:
                return None

            # Normalize
            X = self._normalize_features(X, fit=False)

            # Predict
            predictions = self.model.predict(X, verbose=0)
            failure_prob, failure_type_pred, days_pred = predictions

            # Decode results
            prob = float(failure_prob[0, 0])
            failure_type, type_confidence = self._decode_failure_type(failure_type_pred)
            days = max(1, min(int(days_pred[0, 0]), self.config.prediction_horizon))

            # Calculate contributing features
            contributing = self._analyze_feature_importance(obd_data)

            # Overall confidence
            confidence = (prob * 0.6 + type_confidence * 0.4) if prob > 0.5 else (1 - prob) * 0.8

            return PredictionResult(
                failure_probability=round(prob, 3),
                failure_type=failure_type if prob > 0.3 else 'no_failure',
                days_to_failure=days if prob > 0.3 else self.config.prediction_horizon,
                confidence=round(confidence, 3),
                contributing_features=contributing,
                model_version=self.model_version,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"LSTM prediction error: {e}")
            return self._fallback_prediction(obd_data)

    def _fallback_prediction(self, obd_data: List[Dict]) -> PredictionResult:
        """Fallback prediction when LSTM is not available."""
        # Simple heuristic-based prediction
        if not obd_data:
            return PredictionResult(
                failure_probability=0.1,
                failure_type='no_failure',
                days_to_failure=60,
                confidence=0.3,
                contributing_features={},
                model_version='fallback',
                timestamp=datetime.now().isoformat()
            )

        # Analyze recent data for anomalies
        recent = obd_data[-10:] if len(obd_data) >= 10 else obd_data

        anomaly_score = 0
        contributing = {}

        # Check voltage
        voltages = [r.get('voltage', 14) for r in recent if r.get('voltage')]
        if voltages:
            avg_voltage = sum(voltages) / len(voltages)
            if avg_voltage < 12.5:
                anomaly_score += 0.3
                contributing['voltage'] = avg_voltage

        # Check coolant temp
        temps = [r.get('coolant_temp', 90) for r in recent if r.get('coolant_temp')]
        if temps:
            avg_temp = sum(temps) / len(temps)
            if avg_temp > 105:
                anomaly_score += 0.25
                contributing['coolant_temp'] = avg_temp

        # Check RPM stability
        rpms = [r.get('rpm', 800) for r in recent if r.get('rpm')]
        if len(rpms) >= 3:
            rpm_std = np.std(rpms)
            if rpm_std > 200:
                anomaly_score += 0.2
                contributing['rpm_instability'] = rpm_std

        prob = min(0.9, anomaly_score)
        failure_type = 'battery' if contributing.get('voltage', 14) < 12.5 else 'no_failure'

        return PredictionResult(
            failure_probability=round(prob, 3),
            failure_type=failure_type,
            days_to_failure=30 if prob > 0.3 else 60,
            confidence=0.4,
            contributing_features=contributing,
            model_version='fallback_heuristic',
            timestamp=datetime.now().isoformat()
        )

    def _analyze_feature_importance(self, obd_data: List[Dict]) -> Dict[str, float]:
        """Analyze which features are contributing most to prediction."""
        if not obd_data:
            return {}

        recent = obd_data[-20:] if len(obd_data) >= 20 else obd_data
        importance = {}

        # Calculate variance for each feature
        for col in self.config.feature_columns[:8]:  # Top 8 features
            values = [r.get(col, 0) for r in recent if r.get(col) is not None]
            if values:
                std = np.std(values)
                mean = np.mean(values)
                cv = std / abs(mean) if mean != 0 else 0  # Coefficient of variation
                importance[col] = round(min(1.0, cv), 3)

        # Sort by importance
        sorted_imp = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5])
        return sorted_imp

    def _save_model(self):
        """Save model and configuration."""
        if self.model is None:
            return

        try:
            # Save Keras model
            self.model.save(str(self.model_path / 'lstm_model.keras'))

            # Save configuration and scaler
            config_data = {
                'version': self.model_version,
                'config': {
                    'sequence_length': self.config.sequence_length,
                    'prediction_horizon': self.config.prediction_horizon,
                    'feature_columns': self.config.feature_columns,
                    'lstm_units_1': self.config.lstm_units_1,
                    'lstm_units_2': self.config.lstm_units_2
                },
                'scaler_params': self.scaler_params,
                'failure_types': self.failure_types,
                'training_history': self.training_history,
                'saved_at': datetime.now().isoformat()
            }

            with open(self.model_path / 'lstm_config.json', 'w') as f:
                json.dump(config_data, f, indent=2)

            logger.info(f"Model saved: version {self.model_version}")

        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def _load_model(self):
        """Load saved model and configuration."""
        config_path = self.model_path / 'lstm_config.json'
        model_path = self.model_path / 'lstm_model.keras'

        if not config_path.exists():
            logger.info("No saved LSTM model found")
            return

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            self.model_version = config_data.get('version', '0.0.0')
            self.scaler_params = config_data.get('scaler_params', {})
            self.training_history = config_data.get('training_history', [])
            self.failure_types = config_data.get('failure_types', self.failure_types)

            # Update config
            saved_config = config_data.get('config', {})
            if saved_config.get('feature_columns'):
                self.config.feature_columns = saved_config['feature_columns']

            # Load Keras model if TensorFlow available
            if TENSORFLOW_AVAILABLE and model_path.exists():
                self.model = load_model(str(model_path))
                self.is_trained = True
                logger.info(f"Loaded LSTM model version {self.model_version}")
            else:
                logger.info("LSTM config loaded but model not loaded (TensorFlow unavailable)")

        except Exception as e:
            logger.warning(f"Failed to load model: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            'is_trained': self.is_trained,
            'version': self.model_version,
            'tensorflow_available': TENSORFLOW_AVAILABLE,
            'sequence_length': self.config.sequence_length,
            'prediction_horizon': self.config.prediction_horizon,
            'num_features': len(self.config.feature_columns),
            'failure_types': self.failure_types,
            'training_samples': sum(h.get('samples', 0) for h in self.training_history),
            'last_trained': self.training_history[-1]['timestamp'] if self.training_history else None,
            'architecture': {
                'preferred': self.preferred_architecture.value,
                'available': [arch.value for arch in self.get_available_architectures()],
                'factory_status': self.model_factory.get_model_performance_summary()
            }
        }

    # ==================== MODEL AVAILABILITY CHECKS ====================
    # REQUIRED BY: startup_enforcer.py

    def is_model_loaded(self) -> bool:
        """
        Check if a trained model is loaded and ready for predictions.

        Returns:
            True if model is loaded and can make predictions
        """
        if not TENSORFLOW_AVAILABLE:
            return False
        return self.model is not None and self.is_trained

    def has_fallback(self) -> bool:
        """
        Check if fallback prediction is available.

        The fallback heuristic predictor is ALWAYS available.

        Returns:
            True (fallback is always available)
        """
        return True  # Fallback heuristic predictor is always available

    def get_availability_status(self) -> Dict[str, Any]:
        """
        Get comprehensive model availability status.

        REQUIRED BY: startup_enforcer.py for validation

        Returns:
            Dict with availability status for startup validation
        """
        return {
            'tensorflow_available': TENSORFLOW_AVAILABLE,
            'model_loaded': self.is_model_loaded(),
            'fallback_available': self.has_fallback(),
            'can_make_predictions': self.is_model_loaded() or self.has_fallback(),
            'model_version': self.model_version if self.is_trained else None,
            'prediction_mode': 'lstm' if self.is_model_loaded() else 'fallback_heuristic',
            'status': 'ready' if (self.is_model_loaded() or self.has_fallback()) else 'unavailable'
        }

    def validate_for_production(self) -> Tuple[bool, str]:
        """
        Validate model is ready for production use.

        REQUIRED BY: startup_enforcer.py

        Returns:
            (is_ready, message)
        """
        if self.is_model_loaded():
            return True, f"LSTM model v{self.model_version} ready"

        if self.has_fallback():
            return True, "Fallback heuristic predictor ready (LSTM not available)"

        return False, "No prediction capability available"


# Singleton instance
_lstm_predictor = None

def get_lstm_predictor() -> LSTMPredictor:
    """Get the singleton LSTMPredictor instance."""
    global _lstm_predictor
    if _lstm_predictor is None:
        _lstm_predictor = LSTMPredictor()
    return _lstm_predictor
