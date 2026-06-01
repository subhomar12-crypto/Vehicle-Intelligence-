"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: CNN-LSTM Hybrid Architecture

CNN-LSTM Hybrid Architecture for Predictive Maintenance
======================================================

Combines Convolutional Neural Networks (CNN) for spatial feature extraction
with Long Short-Term Memory (LSTM) networks for temporal pattern learning.

Architecture Overview:
```
Input Sequence (T, F) -> CNN Feature Extraction -> LSTM Temporal Learning -> Dense Output
       |                        |                        |                    |
   Time Steps              Conv1D Layers           BiLSTM Layers     Multi-head Output
   Features                Max Pooling             Dropout          Classification +
   (e.g., RPM, Temp)       Batch Norm              Attention         Regression
```

Key Features:
- CNN layers extract local patterns and reduce dimensionality
- LSTM layers learn temporal dependencies across sequences
- Bidirectional processing for context awareness
- Multi-head output for failure prediction, type classification, and time-to-failure
- Attention mechanism for feature importance
- Physics-informed constraints integration
"""

import numpy as np
import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from collections import deque
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import Model
from tensorflow.keras.layers import (
    Input, Conv1D, MaxPooling1D, BatchNormalization, Dropout,
    Bidirectional, LSTM, Dense, Attention, Concatenate,
    GlobalAveragePooling1D, Multiply, Add, Activation,
    TimeDistributed, Masking, Flatten
)
from tensorflow.keras.callbacks import (
    EarlyStopping, ModelCheckpoint, ReduceLROnPlateau, TensorBoard
)
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.regularizers import l2
from tensorflow.keras import backend as K

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)

# TensorFlow availability check
TENSORFLOW_AVAILABLE = False
try:
    import tensorflow as tf
    from tensorflow import keras
    TENSORFLOW_AVAILABLE = True
    logger.info(f"TensorFlow {tf.__version__} loaded for CNN-LSTM models")
except ImportError as e:
    logger.warning(f"TensorFlow not available - CNN-LSTM models disabled: {e}")
except Exception as e:
    logger.warning(f"TensorFlow import failed - CNN-LSTM models disabled: {e}")


@dataclass
class CNNLSTMConfig:
    """Configuration for CNN-LSTM hybrid model."""

    # Sequence parameters
    sequence_length: int = 60  # Days of history
    prediction_horizon: int = 30  # Days ahead to predict

    # CNN Architecture
    cnn_filters_1: int = 64
    cnn_filters_2: int = 128
    cnn_kernel_size: int = 3
    cnn_pool_size: int = 2
    cnn_dropout_rate: float = 0.2

    # LSTM Architecture
    lstm_units_1: int = 128
    lstm_units_2: int = 64
    lstm_dropout_rate: float = 0.3
    use_bidirectional: bool = True
    use_attention: bool = True

    # Dense layers
    dense_units: int = 64
    dense_dropout_rate: float = 0.3

    # Training parameters
    batch_size: int = 32
    epochs: int = 100
    learning_rate: float = 0.001
    early_stopping_patience: int = 15
    reduce_lr_patience: int = 5

    # Regularization
    l2_regularization: float = 0.01
    use_batch_norm: bool = True

    # Features
    feature_columns: List[str] = field(default_factory=lambda: [
        'rpm', 'speed', 'coolant_temp', 'engine_load',
        'intake_temp', 'maf', 'throttle_pos', 'fuel_pressure',
        'timing_advance', 'short_fuel_trim', 'long_fuel_trim',
        'voltage', 'rpm_stability', 'load_stability',
        'temp_rate_of_change', 'voltage_trend'
    ])

    # Failure types
    failure_types: List[str] = field(default_factory=lambda: [
        'battery', 'alternator', 'starter', 'fuel_pump',
        'spark_plug', 'oxygen_sensor', 'catalytic_converter',
        'maf_sensor', 'thermostat', 'coolant_system',
        'transmission', 'ignition', 'no_failure'
    ])


@dataclass
class CNNLSTMPrediction:
    """CNN-LSTM prediction result."""
    failure_probability: float
    failure_type: str
    days_to_failure: int
    confidence: float
    feature_importance: Dict[str, float]
    attention_weights: Optional[np.ndarray]
    model_version: str
    timestamp: str
    architecture_type: str = "cnn_lstm"


class CNNLSTMModel:
    """
    CNN-LSTM Hybrid Model for Predictive Maintenance.

    Architecture:
    1. CNN Feature Extraction: Conv1D layers extract spatial patterns
    2. LSTM Temporal Learning: Bidirectional LSTM learns temporal dependencies
    3. Attention Mechanism: Focuses on important time steps
    4. Multi-head Output: Failure probability, type, and time-to-failure
    """

    def __init__(self, config: CNNLSTMConfig = None, model_path: str = None):
        """Initialize CNN-LSTM model."""
        self.config = config or CNNLSTMConfig()
        self.model_path = Path(model_path or str(CONFIG.AI_MODELS_DIR / "cnn_lstm_models"))
        self.model_path.mkdir(parents=True, exist_ok=True)

        self.model = None  # TensorFlow Model
        self.scaler_params: Dict[str, Dict] = {}  # Feature normalization
        self.model_version = "0.0.0"
        self.training_history: List[Dict] = []
        self.is_trained = False

        self.num_classes = len(self.config.failure_types)

        # Load existing model if available
        self._load_model()

        logger.info(f"CNNLSTMModel initialized (TensorFlow: {TENSORFLOW_AVAILABLE})")

    def _build_cnn_feature_extractor(self, input_shape: Tuple[int, int]) -> Model:
        """
        Build CNN feature extraction component.

        Args:
            input_shape: (sequence_length, num_features)

        Returns:
            CNN feature extractor model
        """
        inputs = Input(shape=input_shape, name='cnn_input')

        # Masking for variable-length sequences
        x = Masking(mask_value=0.0)(inputs)

        # First CNN block
        x = Conv1D(
            filters=self.config.cnn_filters_1,
            kernel_size=self.config.cnn_kernel_size,
            padding='same',
            activation='relu',
            kernel_regularizer=l2(self.config.l2_regularization),
            name='conv1d_1'
        )(x)

        if self.config.use_batch_norm:
            x = BatchNormalization(name='batch_norm_1')(x)

        x = MaxPooling1D(pool_size=self.config.cnn_pool_size, name='pool_1')(x)
        x = Dropout(self.config.cnn_dropout_rate, name='dropout_cnn_1')(x)

        # Second CNN block
        x = Conv1D(
            filters=self.config.cnn_filters_2,
            kernel_size=self.config.cnn_kernel_size,
            padding='same',
            activation='relu',
            kernel_regularizer=l2(self.config.l2_regularization),
            name='conv1d_2'
        )(x)

        if self.config.use_batch_norm:
            x = BatchNormalization(name='batch_norm_2')(x)

        x = MaxPooling1D(pool_size=self.config.cnn_pool_size, name='pool_2')(x)
        x = Dropout(self.config.cnn_dropout_rate, name='dropout_cnn_2')(x)

        # Global pooling to reduce sequence dimension
        x = GlobalAveragePooling1D(name='global_avg_pool')(x)

        # Dense layer for feature refinement
        x = Dense(self.config.dense_units, activation='relu',
                 kernel_regularizer=l2(self.config.l2_regularization),
                 name='dense_features')(x)
        x = Dropout(self.config.dense_dropout_rate, name='dropout_dense')(x)

        model = Model(inputs=inputs, outputs=x, name='cnn_feature_extractor')
        return model

    def _build_lstm_temporal_processor(self, input_shape: Tuple[int, int]) -> Model:
        """
        Build LSTM temporal processing component.

        Args:
            input_shape: (sequence_length, num_features)

        Returns:
            LSTM temporal processor model
        """
        inputs = Input(shape=input_shape, name='lstm_input')

        # Masking for variable-length sequences
        x = Masking(mask_value=0.0)(inputs)

        # Bidirectional LSTM layers
        if self.config.use_bidirectional:
            x = Bidirectional(
                LSTM(
                    self.config.lstm_units_1,
                    return_sequences=True,
                    kernel_regularizer=l2(self.config.l2_regularization),
                    recurrent_regularizer=l2(self.config.l2_regularization)
                ),
                name='bilstm_1'
            )(x)
        else:
            x = LSTM(
                self.config.lstm_units_1,
                return_sequences=True,
                kernel_regularizer=l2(self.config.l2_regularization),
                recurrent_regularizer=l2(self.config.l2_regularization),
                name='lstm_1'
            )(x)

        if self.config.use_batch_norm:
            x = BatchNormalization(name='batch_norm_lstm_1')(x)

        x = Dropout(self.config.lstm_dropout_rate, name='dropout_lstm_1')(x)

        # Second LSTM layer
        if self.config.use_bidirectional:
            x = Bidirectional(
                LSTM(
                    self.config.lstm_units_2,
                    return_sequences=True,
                    kernel_regularizer=l2(self.config.l2_regularization),
                    recurrent_regularizer=l2(self.config.l2_regularization)
                ),
                name='bilstm_2'
            )(x)
        else:
            x = LSTM(
                self.config.lstm_units_2,
                return_sequences=True,
                kernel_regularizer=l2(self.config.l2_regularization),
                recurrent_regularizer=l2(self.config.l2_regularization),
                name='lstm_2'
            )(x)

        if self.config.use_batch_norm:
            x = BatchNormalization(name='batch_norm_lstm_2')(x)

        x = Dropout(self.config.lstm_dropout_rate, name='dropout_lstm_2')(x)

        # Attention mechanism
        if self.config.use_attention:
            # Self-attention for temporal importance
            attention_output = Attention(name='temporal_attention')([x, x])
            x = Add(name='attention_add')([x, attention_output])
            x = Activation('tanh', name='attention_activation')(x)

        # Global pooling for sequence aggregation
        x = GlobalAveragePooling1D(name='global_avg_pool_lstm')(x)

        model = Model(inputs=inputs, outputs=x, name='lstm_temporal_processor')
        return model

    def _build_model(self, input_shape: Tuple[int, int]) -> Model:
        """
        Build complete CNN-LSTM hybrid model.

        Args:
            input_shape: (sequence_length, num_features)

        Returns:
            Complete CNN-LSTM model
        """
        if not TENSORFLOW_AVAILABLE:
            raise RuntimeError("TensorFlow not available")

        inputs = Input(shape=input_shape, name='hybrid_input')

        # CNN Feature Extraction
        cnn_features = self._build_cnn_feature_extractor(input_shape)(inputs)

        # LSTM Temporal Processing
        lstm_features = self._build_lstm_temporal_processor(input_shape)(inputs)

        # Combine CNN and LSTM features
        combined = Concatenate(name='feature_fusion')([cnn_features, lstm_features])

        # Additional dense layers
        x = Dense(self.config.dense_units, activation='relu',
                 kernel_regularizer=l2(self.config.l2_regularization),
                 name='dense_combined_1')(combined)
        x = Dropout(self.config.dense_dropout_rate, name='dropout_combined_1')(x)

        x = Dense(self.config.dense_units // 2, activation='relu',
                 kernel_regularizer=l2(self.config.l2_regularization),
                 name='dense_combined_2')(x)
        x = Dropout(self.config.dense_dropout_rate, name='dropout_combined_2')(x)

        # Multi-head outputs
        # 1. Failure probability (binary)
        failure_prob = Dense(1, activation='sigmoid', name='failure_probability')(x)

        # 2. Failure type (multi-class)
        failure_type = Dense(self.num_classes, activation='softmax', name='failure_type')(x)

        # 3. Days to failure (regression)
        days_to_failure = Dense(1, activation='linear', name='days_to_failure')(x)

        model = Model(
            inputs=inputs,
            outputs=[failure_prob, failure_type, days_to_failure],
            name='cnn_lstm_predictor'
        )

        # Compile with appropriate losses
        model.compile(
            optimizer=Adam(learning_rate=self.config.learning_rate),
            loss={
                'failure_probability': 'binary_crossentropy',
                'failure_type': 'categorical_crossentropy',
                'days_to_failure': 'mse'
            },
            loss_weights={
                'failure_probability': 1.0,
                'failure_type': 0.5,
                'days_to_failure': 0.3
            },
            metrics={
                'failure_probability': ['accuracy', 'AUC'],
                'failure_type': ['accuracy'],
                'days_to_failure': ['mae', 'mse']
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

        normalized = np.zeros_like(data, dtype=np.float32)
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
            obd_data: List of OBD readings
            failure_info: Optional failure information

        Returns:
            X: Input sequences, y: Labels if provided
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

        X = np.array([sequence_data], dtype=np.float32)

        # Prepare labels
        y = None
        if failure_info:
            y = {
                'failure_probability': np.array([[1.0 if failure_info.get('failure_occurred', False) else 0.0]], dtype=np.float32),
                'failure_type': self._encode_failure_type(failure_info.get('failure_type', 'no_failure')),
                'days_to_failure': np.array([[min(failure_info.get('days_to_failure', self.config.prediction_horizon),
                                                  self.config.prediction_horizon)]], dtype=np.float32)
            }

        return X, y

    def _encode_failure_type(self, failure_type: str) -> np.ndarray:
        """One-hot encode failure type."""
        encoded = np.zeros((1, self.num_classes), dtype=np.float32)
        try:
            idx = self.config.failure_types.index(failure_type.lower())
        except ValueError:
            idx = self.config.failure_types.index('no_failure')
        encoded[0, idx] = 1.0
        return encoded

    def _decode_failure_type(self, prediction: np.ndarray) -> Tuple[str, float]:
        """Decode failure type prediction."""
        idx = np.argmax(prediction, axis=-1)[0]
        confidence = float(prediction[0, idx])
        return self.config.failure_types[idx], confidence

    def train(
        self,
        training_data: List[Dict],
        validation_split: float = 0.2,
        verbose: int = 1
    ) -> Dict[str, Any]:
        """
        Train the CNN-LSTM model.

        Args:
            training_data: List of training samples
            validation_split: Validation data fraction
            verbose: Training verbosity

        Returns:
            Training results
        """
        if not TENSORFLOW_AVAILABLE:
            return {'error': 'TensorFlow not available'}

        if len(training_data) < 50:
            return {'error': f'Insufficient training data: {len(training_data)} samples (need 50+)'}

        logger.info(f"Starting CNN-LSTM training with {len(training_data)} samples")

        # Prepare sequences
        X_list = []
        y_prob_list = []
        y_type_list = []
        y_days_list = []

        for item in training_data:
            X, y = self.prepare_sequences(item['sequence'], item.get('label'))
            if X.size > 0 and y:
                X_list.append(X[0])
                y_prob_list.append(y['failure_probability'][0])
                y_type_list.append(y['failure_type'][0])
                y_days_list.append(y['days_to_failure'][0])

        if not X_list:
            return {'error': 'No valid sequences prepared'}

        X = np.array(X_list, dtype=np.float32)
        y_prob = np.array(y_prob_list, dtype=np.float32)
        y_type = np.array(y_type_list, dtype=np.float32)
        y_days = np.array(y_days_list, dtype=np.float32)

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
                str(self.model_path / 'best_cnn_lstm_model.keras'),
                monitor='val_loss',
                save_best_only=True
            ),
            TensorBoard(
                log_dir=str(self.model_path / 'logs'),
                histogram_freq=1
            )
        ]

        # Train
        history = self.model.fit(
            X,
            {'failure_probability': y_prob, 'failure_type': y_type, 'days_to_failure': y_days},
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
            'accuracy': float(history.history.get('failure_probability_accuracy', [0])[-1]),
            'architecture': 'cnn_lstm_hybrid'
        }
        self.training_history.append(training_record)

        logger.info(f"CNN-LSTM training complete. Version: {self.model_version}")

        return {
            'success': True,
            'version': self.model_version,
            'epochs': len(history.history['loss']),
            'final_loss': training_record['final_loss'],
            'accuracy': training_record['accuracy'],
            'architecture': 'cnn_lstm_hybrid'
        }

    def predict(self, obd_data: List[Dict]) -> Optional[CNNLSTMPrediction]:
        """
        Make a prediction using the CNN-LSTM model.

        Args:
            obd_data: Recent OBD readings

        Returns:
            Prediction result or None
        """
        if not self.is_trained or self.model is None:
            logger.warning("CNN-LSTM model not trained")
            return None

        if not TENSORFLOW_AVAILABLE:
            return None

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

            # Calculate confidence and feature importance
            confidence = (prob * 0.6 + type_confidence * 0.4) if prob > 0.5 else (1 - prob) * 0.8
            feature_importance = self._analyze_feature_importance(obd_data)

            # Get attention weights if available
            attention_weights = None
            if self.config.use_attention:
                attention_weights = self._extract_attention_weights(X)

            return CNNLSTMPrediction(
                failure_probability=round(prob, 3),
                failure_type=failure_type if prob > 0.3 else 'no_failure',
                days_to_failure=days if prob > 0.3 else self.config.prediction_horizon,
                confidence=round(confidence, 3),
                feature_importance=feature_importance,
                attention_weights=attention_weights,
                model_version=self.model_version,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"CNN-LSTM prediction error: {e}")
            return None

    def _analyze_feature_importance(self, obd_data: List[Dict]) -> Dict[str, float]:
        """Analyze feature importance from recent data."""
        if not obd_data:
            return {}

        recent = obd_data[-20:] if len(obd_data) >= 20 else obd_data
        importance = {}

        for col in self.config.feature_columns[:10]:  # Top 10 features
            values = [r.get(col, 0) for r in recent if r.get(col) is not None]
            if values:
                std = np.std(values)
                mean = np.mean(values)
                cv = std / abs(mean) if mean != 0 else 0
                importance[col] = round(min(1.0, cv), 3)

        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5])

    def _extract_attention_weights(self, X: np.ndarray) -> Optional[np.ndarray]:
        """Extract attention weights from the model."""
        try:
            # Create a model that outputs attention weights
            attention_layer = self.model.get_layer('temporal_attention')
            attention_model = Model(
                inputs=self.model.input,
                outputs=attention_layer.output
            )
            weights = attention_model.predict(X, verbose=0)
            return weights
        except Exception:
            return None

    def _save_model(self):
        """Save model and configuration."""
        if self.model is None:
            return

        try:
            # Save Keras model
            self.model.save(str(self.model_path / 'cnn_lstm_model.keras'))

            # Save configuration
            config_data = {
                'version': self.model_version,
                'config': {
                    'sequence_length': self.config.sequence_length,
                    'prediction_horizon': self.config.prediction_horizon,
                    'feature_columns': self.config.feature_columns,
                    'failure_types': self.config.failure_types,
                    'cnn_filters_1': self.config.cnn_filters_1,
                    'cnn_filters_2': self.config.cnn_filters_2,
                    'lstm_units_1': self.config.lstm_units_1,
                    'lstm_units_2': self.config.lstm_units_2,
                    'use_attention': self.config.use_attention,
                    'use_bidirectional': self.config.use_bidirectional
                },
                'scaler_params': self.scaler_params,
                'training_history': self.training_history,
                'saved_at': datetime.now().isoformat()
            }

            with open(self.model_path / 'cnn_lstm_config.json', 'w') as f:
                json.dump(config_data, f, indent=2)

            logger.info(f"CNN-LSTM model saved: version {self.model_version}")

        except Exception as e:
            logger.error(f"Failed to save CNN-LSTM model: {e}")

    def _load_model(self):
        """Load saved model and configuration."""
        config_path = self.model_path / 'cnn_lstm_config.json'
        model_path = self.model_path / 'cnn_lstm_model.keras'

        if not config_path.exists():
            logger.info("No saved CNN-LSTM model found")
            return

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            self.model_version = config_data.get('version', '0.0.0')
            self.scaler_params = config_data.get('scaler_params', {})
            self.training_history = config_data.get('training_history', [])

            # Update config
            saved_config = config_data.get('config', {})
            if saved_config.get('feature_columns'):
                self.config.feature_columns = saved_config['feature_columns']
            if saved_config.get('failure_types'):
                self.config.failure_types = saved_config['failure_types']

            # Load Keras model
            if TENSORFLOW_AVAILABLE and model_path.exists():
                self.model = tf.keras.models.load_model(str(model_path))
                self.is_trained = True
                logger.info(f"Loaded CNN-LSTM model version {self.model_version}")
            else:
                logger.info("CNN-LSTM config loaded but model not loaded (TensorFlow unavailable)")

        except Exception as e:
            logger.warning(f"Failed to load CNN-LSTM model: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the CNN-LSTM model."""
        return {
            'is_trained': self.is_trained,
            'version': self.model_version,
            'architecture': 'cnn_lstm_hybrid',
            'tensorflow_available': TENSORFLOW_AVAILABLE,
            'sequence_length': self.config.sequence_length,
            'prediction_horizon': self.config.prediction_horizon,
            'num_features': len(self.config.feature_columns),
            'num_classes': self.num_classes,
            'failure_types': self.config.failure_types,
            'training_samples': sum(h.get('samples', 0) for h in self.training_history),
            'last_trained': self.training_history[-1]['timestamp'] if self.training_history else None,
            'cnn_config': {
                'filters_1': self.config.cnn_filters_1,
                'filters_2': self.config.cnn_filters_2,
                'kernel_size': self.config.cnn_kernel_size,
                'pool_size': self.config.cnn_pool_size
            },
            'lstm_config': {
                'units_1': self.config.lstm_units_1,
                'units_2': self.config.lstm_units_2,
                'bidirectional': self.config.use_bidirectional,
                'attention': self.config.use_attention
            }
        }


# Singleton instance
_cnn_lstm_model = None

def get_cnn_lstm_model() -> CNNLSTMModel:
    """Get the singleton CNNLSTMModel instance."""
    global _cnn_lstm_model
    if _cnn_lstm_model is None:
        _cnn_lstm_model = CNNLSTMModel()
    return _cnn_lstm_model