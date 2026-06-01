"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Attention-LSTM Model

Attention-LSTM Model for Predictive Maintenance
===============================================

LSTM network enhanced with multiple attention mechanisms for improved
temporal pattern recognition and feature importance understanding.

Architecture Overview:
```
Input Sequence (T, F) -> Feature Attention -> Temporal Attention -> LSTM Processing
       |                        |                        |                    |
   Time Steps              Feature Weights         Time Step Weights    Multi-head Output
   Features                (What matters)          (When matters)     Classification +
   (e.g., RPM, Temp)       Self-Attention          Self-Attention     Regression
```

Key Features:
- Multi-head attention for feature and temporal importance
- Hierarchical attention mechanism (feature-level + temporal-level)
- Self-attention for capturing long-range dependencies
- Attention-based confidence scoring
- Physics-informed feature weighting
- Interpretability through attention visualization
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
    Input, Dense, Dropout, BatchNormalization, LSTM,
    Bidirectional, Attention, MultiHeadAttention, LayerNormalization,
    GlobalAveragePooling1D, Concatenate, Add, Activation,
    TimeDistributed, Masking, Flatten, Reshape, Permute,
    Multiply, Softmax, Lambda
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
    logger.info(f"TensorFlow {tf.__version__} loaded for Attention-LSTM models")
except ImportError as e:
    logger.warning(f"TensorFlow not available - Attention-LSTM models disabled: {e}")
except Exception as e:
    logger.warning(f"TensorFlow import failed - Attention-LSTM models disabled: {e}")


@dataclass
class AttentionLSTMConfig:
    """Configuration for Attention-LSTM model."""

    # Sequence parameters
    sequence_length: int = 60  # Days of history
    prediction_horizon: int = 30  # Days ahead to predict

    # LSTM Architecture
    lstm_units_1: int = 128
    lstm_units_2: int = 64
    lstm_units_3: int = 32
    lstm_dropout_rate: float = 0.3
    use_bidirectional: bool = True

    # Attention Configuration
    num_attention_heads: int = 8
    attention_key_dim: int = 64
    attention_dropout: float = 0.1
    use_multihead_attention: bool = True
    use_temporal_attention: bool = True
    use_feature_attention: bool = True
    use_hierarchical_attention: bool = True

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
    use_layer_norm: bool = True

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

    # Physics-informed feature weights (higher = more important)
    physics_feature_weights: Dict[str, float] = field(default_factory=lambda: {
        'voltage': 1.0,      # Battery/alternator health
        'coolant_temp': 0.9, # Engine thermal management
        'rpm': 0.8,          # Engine performance
        'engine_load': 0.8,  # Engine stress
        'maf': 0.7,          # Air intake system
        'fuel_pressure': 0.7,# Fuel system
        'timing_advance': 0.6,# Ignition timing
        'short_fuel_trim': 0.6,# Fuel mixture
        'long_fuel_trim': 0.5,# Long-term fuel adaptation
        'throttle_pos': 0.5, # Driver input
        'speed': 0.4,        # Vehicle speed
        'intake_temp': 0.4,  # Intake air temperature
        'rpm_stability': 0.6,# Engine stability
        'load_stability': 0.6,# Load stability
        'temp_rate_of_change': 0.7,# Thermal dynamics
        'voltage_trend': 0.8 # Electrical system trends
    })


@dataclass
class AttentionWeights:
    """Attention weights for interpretability."""
    temporal_attention: np.ndarray  # (sequence_length,)
    feature_attention: np.ndarray   # (num_features,)
    hierarchical_attention: Optional[np.ndarray] = None  # (sequence_length, num_features)


@dataclass
class AttentionLSTMPrediction:
    """Attention-LSTM prediction result."""
    failure_probability: float
    failure_type: str
    days_to_failure: int
    confidence: float
    attention_weights: AttentionWeights
    feature_importance: Dict[str, float]
    physics_confidence: float
    model_version: str
    timestamp: str
    architecture_type: str = "attention_lstm"


class AttentionLSTMModel:
    """
    Attention-Enhanced LSTM Model for Predictive Maintenance.

    Architecture:
    1. Feature-Level Attention: Learns which features are important
    2. Temporal Attention: Learns which time steps are important
    3. Hierarchical Attention: Combines feature and temporal attention
    4. LSTM Processing: Bidirectional LSTM with attention context
    5. Multi-head Output: Failure prediction with attention-based confidence
    """

    def __init__(self, config: AttentionLSTMConfig = None, model_path: str = None):
        """Initialize Attention-LSTM model."""
        self.config = config or AttentionLSTMConfig()
        self.model_path = Path(model_path or str(CONFIG.AI_MODELS_DIR / "attention_lstm_models"))
        self.model_path.mkdir(parents=True, exist_ok=True)

        self.model = None  # TensorFlow Model
        self.scaler_params: Dict[str, Dict] = {}  # Feature normalization
        self.model_version = "0.0.0"
        self.training_history: List[Dict] = []
        self.is_trained = False

        self.num_classes = len(self.config.failure_types)
        self.num_features = len(self.config.feature_columns)

        # Physics-informed feature weights tensor
        self.physics_weights = self._build_physics_weights()

        # Load existing model if available
        self._load_model()

        logger.info(f"AttentionLSTMModel initialized (TensorFlow: {TENSORFLOW_AVAILABLE})")

    def _build_physics_weights(self) -> np.ndarray:
        """Build physics-informed feature weights tensor."""
        weights = []
        for feature in self.config.feature_columns:
            weight = self.config.physics_feature_weights.get(feature, 0.5)
            weights.append(weight)
        return np.array(weights, dtype=np.float32)

    def _feature_attention_layer(self, inputs, name_prefix="feature"):
        """Apply feature-level attention."""
        # inputs shape: (batch, seq_len, num_features)

        # Compute feature importance scores
        feature_scores = Dense(
            self.num_features,
            activation='tanh',
            kernel_regularizer=l2(self.config.l2_regularization),
            name=f'{name_prefix}_attention_scores'
        )(inputs)  # (batch, seq_len, num_features)

        # Apply softmax across feature dimension
        feature_attention = Softmax(axis=-1, name=f'{name_prefix}_attention_weights')(feature_scores)

        # Apply attention weights
        attended_features = Multiply(name=f'{name_prefix}_attended_features')([inputs, feature_attention])

        return attended_features, feature_attention

    def _temporal_attention_layer(self, inputs, name_prefix="temporal"):
        """Apply temporal attention across time steps."""
        # inputs shape: (batch, seq_len, features)

        # Use multi-head attention for temporal relationships
        if self.config.use_multihead_attention:
            attention_output = MultiHeadAttention(
                num_heads=self.config.num_attention_heads,
                key_dim=self.config.attention_key_dim,
                dropout=self.config.attention_dropout,
                name=f'{name_prefix}_multihead_attention'
            )(inputs, inputs)

            # Add & norm
            attention_output = Add(name=f'{name_prefix}_attention_add')([inputs, attention_output])
            if self.config.use_layer_norm:
                attention_output = LayerNormalization(name=f'{name_prefix}_layer_norm')(attention_output)
        else:
            # Simple attention
            attention_output = Attention(name=f'{name_prefix}_attention')([inputs, inputs])

        return attention_output

    def _hierarchical_attention_layer(self, inputs, name_prefix="hierarchical"):
        """Apply hierarchical attention combining feature and temporal attention."""
        # inputs shape: (batch, seq_len, features)

        # Feature attention first
        feature_attended, feature_weights = self._feature_attention_layer(inputs, f"{name_prefix}_feature")

        # Temporal attention on feature-attended sequences
        temporal_attended = self._temporal_attention_layer(feature_attended, f"{name_prefix}_temporal")

        # Global pooling across time dimension
        temporal_pooled = GlobalAveragePooling1D(name=f'{name_prefix}_global_pool')(temporal_attended)

        # Compute temporal attention weights (importance of each time step)
        temporal_scores = Dense(
            self.config.sequence_length,
            activation='tanh',
            kernel_regularizer=l2(self.config.l2_regularization),
            name=f'{name_prefix}_temporal_scores'
        )(temporal_attended)  # (batch, seq_len, seq_len)

        temporal_weights = Softmax(axis=1, name=f'{name_prefix}_temporal_weights')(temporal_scores)

        return temporal_pooled, feature_weights, temporal_weights

    def _build_model(self, input_shape: Tuple[int, int]) -> Model:
        """
        Build complete Attention-LSTM model.

        Args:
            input_shape: (sequence_length, num_features)

        Returns:
            Complete Attention-LSTM model
        """
        if not TENSORFLOW_AVAILABLE:
            raise RuntimeError("TensorFlow not available")

        inputs = Input(shape=input_shape, name='attention_lstm_input')

        # Masking for variable-length sequences
        x = Masking(mask_value=0.0, name='input_masking')(inputs)

        # Apply physics-informed feature weighting
        physics_weights = K.constant(self.physics_weights, name='physics_weights')
        physics_weights = K.expand_dims(physics_weights, axis=0)  # (1, num_features)
        physics_weights = K.expand_dims(physics_weights, axis=0)  # (1, 1, num_features)
        physics_weights = K.tile(physics_weights, [K.shape(x)[0], K.shape(x)[1], 1])  # (batch, seq_len, num_features)

        x = Multiply(name='physics_weighted_input')([x, physics_weights])

        # Hierarchical attention
        if self.config.use_hierarchical_attention:
            attended_features, feature_attention, temporal_attention = self._hierarchical_attention_layer(
                x, "hierarchical"
            )
        else:
            # Separate feature and temporal attention
            if self.config.use_feature_attention:
                x, feature_attention = self._feature_attention_layer(x, "feature")
            else:
                feature_attention = None

            if self.config.use_temporal_attention:
                x = self._temporal_attention_layer(x, "temporal")
                temporal_attention = GlobalAveragePooling1D(name='temporal_pool')(x)
            else:
                temporal_attention = GlobalAveragePooling1D(name='temporal_pool')(x)

            attended_features = GlobalAveragePooling1D(name='feature_pool')(x)

        # Bidirectional LSTM processing
        if self.config.use_bidirectional:
            lstm_out = Bidirectional(
                LSTM(
                    self.config.lstm_units_1,
                    return_sequences=True,
                    kernel_regularizer=l2(self.config.l2_regularization),
                    recurrent_regularizer=l2(self.config.l2_regularization),
                    dropout=self.config.lstm_dropout_rate,
                    recurrent_dropout=self.config.lstm_dropout_rate
                ),
                name='bilstm_1'
            )(x)
        else:
            lstm_out = LSTM(
                self.config.lstm_units_1,
                return_sequences=True,
                kernel_regularizer=l2(self.config.l2_regularization),
                recurrent_regularizer=l2(self.config.l2_regularization),
                dropout=self.config.lstm_dropout_rate,
                recurrent_dropout=self.config.lstm_dropout_rate,
                name='lstm_1'
            )(x)

        if self.config.use_batch_norm:
            lstm_out = BatchNormalization(name='batch_norm_lstm_1')(lstm_out)

        # Second LSTM layer
        if self.config.use_bidirectional:
            lstm_out = Bidirectional(
                LSTM(
                    self.config.lstm_units_2,
                    return_sequences=True,
                    kernel_regularizer=l2(self.config.l2_regularization),
                    recurrent_regularizer=l2(self.config.l2_regularization),
                    dropout=self.config.lstm_dropout_rate,
                    recurrent_dropout=self.config.lstm_dropout_rate
                ),
                name='bilstm_2'
            )(lstm_out)
        else:
            lstm_out = LSTM(
                self.config.lstm_units_2,
                return_sequences=True,
                kernel_regularizer=l2(self.config.l2_regularization),
                recurrent_regularizer=l2(self.config.l2_regularization),
                dropout=self.config.lstm_dropout_rate,
                recurrent_dropout=self.config.lstm_dropout_rate,
                name='lstm_2'
            )(lstm_out)

        if self.config.use_batch_norm:
            lstm_out = BatchNormalization(name='batch_norm_lstm_2')(lstm_out)

        # Third LSTM layer (optional)
        if self.config.lstm_units_3 > 0:
            if self.config.use_bidirectional:
                lstm_out = Bidirectional(
                    LSTM(
                        self.config.lstm_units_3,
                        return_sequences=False,
                        kernel_regularizer=l2(self.config.l2_regularization),
                        recurrent_regularizer=l2(self.config.l2_regularization),
                        dropout=self.config.lstm_dropout_rate,
                        recurrent_dropout=self.config.lstm_dropout_rate
                    ),
                    name='bilstm_3'
                )(lstm_out)
            else:
                lstm_out = LSTM(
                    self.config.lstm_units_3,
                    return_sequences=False,
                    kernel_regularizer=l2(self.config.l2_regularization),
                    recurrent_regularizer=l2(self.config.l2_regularization),
                    dropout=self.config.lstm_dropout_rate,
                    recurrent_dropout=self.config.lstm_dropout_rate,
                    name='lstm_3'
                )(lstm_out)

            if self.config.use_batch_norm:
                lstm_out = BatchNormalization(name='batch_norm_lstm_3')(lstm_out)
        else:
            # Global pooling if no third LSTM
            lstm_out = GlobalAveragePooling1D(name='global_pool_lstm')(lstm_out)

        # Dense layers
        x = Dense(self.config.dense_units, activation='relu',
                 kernel_regularizer=l2(self.config.l2_regularization),
                 name='dense_1')(lstm_out)
        x = Dropout(self.config.dense_dropout_rate, name='dropout_dense_1')(x)

        x = Dense(self.config.dense_units // 2, activation='relu',
                 kernel_regularizer=l2(self.config.l2_regularization),
                 name='dense_2')(x)
        x = Dropout(self.config.dense_dropout_rate, name='dropout_dense_2')(x)

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
            name='attention_lstm_predictor'
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
        Train the Attention-LSTM model.

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

        logger.info(f"Starting Attention-LSTM training with {len(training_data)} samples")

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
                str(self.model_path / 'best_attention_lstm_model.keras'),
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
            'architecture': 'attention_lstm'
        }
        self.training_history.append(training_record)

        logger.info(f"Attention-LSTM training complete. Version: {self.model_version}")

        return {
            'success': True,
            'version': self.model_version,
            'epochs': len(history.history['loss']),
            'final_loss': training_record['final_loss'],
            'accuracy': training_record['accuracy'],
            'architecture': 'attention_lstm'
        }

    def predict(self, obd_data: List[Dict]) -> Optional[AttentionLSTMPrediction]:
        """
        Make a prediction using the Attention-LSTM model.

        Args:
            obd_data: Recent OBD readings

        Returns:
            Prediction result or None
        """
        if not self.is_trained or self.model is None:
            logger.warning("Attention-LSTM model not trained")
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

            # Extract attention weights
            attention_weights = self._extract_attention_weights(X)

            # Calculate confidence and feature importance
            confidence = self._calculate_attention_confidence(prob, type_confidence, attention_weights)
            feature_importance = self._analyze_feature_importance_with_attention(obd_data, attention_weights)
            physics_confidence = self._calculate_physics_confidence(obd_data, attention_weights)

            return AttentionLSTMPrediction(
                failure_probability=round(prob, 3),
                failure_type=failure_type if prob > 0.3 else 'no_failure',
                days_to_failure=days if prob > 0.3 else self.config.prediction_horizon,
                confidence=round(confidence, 3),
                attention_weights=attention_weights,
                feature_importance=feature_importance,
                physics_confidence=round(physics_confidence, 3),
                model_version=self.model_version,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"Attention-LSTM prediction error: {e}")
            return None

    def _extract_attention_weights(self, X: np.ndarray) -> AttentionWeights:
        """Extract attention weights from the model for interpretability."""
        try:
            # Extract feature attention weights
            feature_attention_model = Model(
                inputs=self.model.input,
                outputs=self.model.get_layer('hierarchical_feature_attention_weights').output
            )
            feature_weights = feature_attention_model.predict(X, verbose=0)

            # Extract temporal attention weights
            temporal_attention_model = Model(
                inputs=self.model.input,
                outputs=self.model.get_layer('hierarchical_temporal_weights').output
            )
            temporal_weights = temporal_attention_model.predict(X, verbose=0)

            # Average across batch and heads for interpretability
            feature_attention = np.mean(feature_weights, axis=(0, 1))  # (num_features,)
            temporal_attention = np.mean(temporal_weights, axis=(0, 2))  # (sequence_length,)

            # Create hierarchical attention matrix
            hierarchical_attention = np.outer(temporal_attention, feature_attention)

            return AttentionWeights(
                temporal_attention=temporal_attention,
                feature_attention=feature_attention,
                hierarchical_attention=hierarchical_attention
            )

        except Exception as e:
            logger.warning(f"Could not extract attention weights: {e}")
            # Return default weights
            return AttentionWeights(
                temporal_attention=np.ones(self.config.sequence_length) / self.config.sequence_length,
                feature_attention=np.ones(self.num_features) / self.num_features,
                hierarchical_attention=None
            )

    def _calculate_attention_confidence(self, prob: float, type_confidence: float,
                                       attention_weights: AttentionWeights) -> float:
        """Calculate confidence based on attention consistency."""
        # Base confidence from prediction probabilities
        base_confidence = (prob * 0.6 + type_confidence * 0.4)

        # Attention consistency bonus
        temporal_entropy = -np.sum(attention_weights.temporal_attention * np.log(attention_weights.temporal_attention + 1e-10))
        feature_entropy = -np.sum(attention_weights.feature_attention * np.log(attention_weights.feature_attention + 1e-10))

        # Lower entropy (more focused attention) increases confidence
        max_entropy_temporal = np.log(self.config.sequence_length)
        max_entropy_feature = np.log(self.num_features)

        temporal_focus = 1 - (temporal_entropy / max_entropy_temporal)
        feature_focus = 1 - (feature_entropy / max_entropy_feature)

        attention_bonus = (temporal_focus + feature_focus) * 0.1  # Up to 20% bonus

        total_confidence = min(1.0, base_confidence + attention_bonus)

        # Reduce confidence if prediction is uncertain but attention is unfocused
        if prob < 0.5 and attention_bonus < 0.1:
            total_confidence *= 0.8

        return total_confidence

    def _analyze_feature_importance_with_attention(self, obd_data: List[Dict],
                                                  attention_weights: AttentionWeights) -> Dict[str, float]:
        """Analyze feature importance using attention weights."""
        if not obd_data:
            return {}

        # Combine attention weights with physics-informed weights
        physics_weighted_attention = attention_weights.feature_attention * self.physics_weights

        # Create importance dictionary
        importance = {}
        for i, feature in enumerate(self.config.feature_columns):
            attention_score = float(physics_weighted_attention[i])
            importance[feature] = attention_score

        # Sort by importance
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:8])

    def _calculate_physics_confidence(self, obd_data: List[Dict],
                                     attention_weights: AttentionWeights) -> float:
        """Calculate physics-based confidence in the prediction."""
        if not obd_data:
            return 0.5

        recent = obd_data[-10:] if len(obd_data) >= 10 else obd_data

        # Check physics constraints
        physics_score = 0.0
        checks = 0

        # Voltage should be reasonable
        voltages = [r.get('voltage', 14) for r in recent if r.get('voltage')]
        if voltages:
            avg_voltage = sum(voltages) / len(voltages)
            if 11 < avg_voltage < 16:  # Reasonable voltage range
                physics_score += 1
            checks += 1

        # Coolant temp should be reasonable
        temps = [r.get('coolant_temp', 90) for r in recent if r.get('coolant_temp')]
        if temps:
            avg_temp = sum(temps) / len(temps)
            if 60 < avg_temp < 110:  # Reasonable temp range
                physics_score += 1
            checks += 1

        # RPM should be reasonable when running
        rpms = [r.get('rpm', 800) for r in recent if r.get('rpm')]
        if rpms:
            avg_rpm = sum(rpms) / len(rpms)
            if avg_rpm < 100 or 500 < avg_rpm < 6000:  # Reasonable RPM range
                physics_score += 1
            checks += 1

        physics_confidence = physics_score / checks if checks > 0 else 0.5

        # Weight by attention focus on physics-critical features
        voltage_attention = attention_weights.feature_attention[self.config.feature_columns.index('voltage')]
        temp_attention = attention_weights.feature_attention[self.config.feature_columns.index('coolant_temp')]

        attention_weighted_physics = physics_confidence * (0.7 + 0.3 * (voltage_attention + temp_attention) / 2)

        return min(1.0, attention_weighted_physics)

    def _save_model(self):
        """Save model and configuration."""
        if self.model is None:
            return

        try:
            # Save Keras model
            self.model.save(str(self.model_path / 'attention_lstm_model.keras'))

            # Save configuration
            config_data = {
                'version': self.model_version,
                'config': {
                    'sequence_length': self.config.sequence_length,
                    'prediction_horizon': self.config.prediction_horizon,
                    'feature_columns': self.config.feature_columns,
                    'failure_types': self.config.failure_types,
                    'lstm_units_1': self.config.lstm_units_1,
                    'lstm_units_2': self.config.lstm_units_2,
                    'lstm_units_3': self.config.lstm_units_3,
                    'num_attention_heads': self.config.num_attention_heads,
                    'attention_key_dim': self.config.attention_key_dim,
                    'use_multihead_attention': self.config.use_multihead_attention,
                    'use_hierarchical_attention': self.config.use_hierarchical_attention,
                    'physics_feature_weights': self.config.physics_feature_weights
                },
                'scaler_params': self.scaler_params,
                'training_history': self.training_history,
                'saved_at': datetime.now().isoformat()
            }

            with open(self.model_path / 'attention_lstm_config.json', 'w') as f:
                json.dump(config_data, f, indent=2)

            logger.info(f"Attention-LSTM model saved: version {self.model_version}")

        except Exception as e:
            logger.error(f"Failed to save Attention-LSTM model: {e}")

    def _load_model(self):
        """Load saved model and configuration."""
        config_path = self.model_path / 'attention_lstm_config.json'
        model_path = self.model_path / 'attention_lstm_model.keras'

        if not config_path.exists():
            logger.info("No saved Attention-LSTM model found")
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
            if saved_config.get('physics_feature_weights'):
                self.config.physics_feature_weights = saved_config['physics_feature_weights']

            # Rebuild physics weights
            self.physics_weights = self._build_physics_weights()

            # Load Keras model
            if TENSORFLOW_AVAILABLE and model_path.exists():
                self.model = tf.keras.models.load_model(str(model_path))
                self.is_trained = True
                logger.info(f"Loaded Attention-LSTM model version {self.model_version}")
            else:
                logger.info("Attention-LSTM config loaded but model not loaded (TensorFlow unavailable)")

        except Exception as e:
            logger.warning(f"Failed to load Attention-LSTM model: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the Attention-LSTM model."""
        return {
            'is_trained': self.is_trained,
            'version': self.model_version,
            'architecture': 'attention_lstm',
            'tensorflow_available': TENSORFLOW_AVAILABLE,
            'sequence_length': self.config.sequence_length,
            'prediction_horizon': self.config.prediction_horizon,
            'num_features': len(self.config.feature_columns),
            'num_classes': self.num_classes,
            'failure_types': self.config.failure_types,
            'training_samples': sum(h.get('samples', 0) for h in self.training_history),
            'last_trained': self.training_history[-1]['timestamp'] if self.training_history else None,
            'attention_config': {
                'num_heads': self.config.num_attention_heads,
                'key_dim': self.config.attention_key_dim,
                'multihead': self.config.use_multihead_attention,
                'hierarchical': self.config.use_hierarchical_attention
            },
            'lstm_config': {
                'units_1': self.config.lstm_units_1,
                'units_2': self.config.lstm_units_2,
                'units_3': self.config.lstm_units_3,
                'bidirectional': self.config.use_bidirectional
            },
            'physics_weights': self.config.physics_feature_weights
        }


# Singleton instance
_attention_lstm_model = None

def get_attention_lstm_model() -> AttentionLSTMModel:
    """Get the singleton AttentionLSTMModel instance."""
    global _attention_lstm_model
    if _attention_lstm_model is None:
        _attention_lstm_model = AttentionLSTMModel()
    return _attention_lstm_model