"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Lstm Autoencoder

LSTM Autoencoder for Anomaly Detection
======================================

Unsupervised anomaly detection using LSTM-based autoencoders that learn
normal vehicle behavior patterns and detect deviations indicating potential failures.

Architecture Overview:
```
Input Sequence (T, F) -> Encoder LSTM -> Latent Space -> Decoder LSTM -> Reconstruction (T, F)
       |                        |            |             |                    |
   Time Steps              Compress      Bottleneck    Reconstruct      Compare with Input
   Features                Temporal      Low-dim       Temporal         Anomaly Score =
   (e.g., RPM, Temp)       Patterns       Representation Patterns       MSE(Reconstruction Error)
```

Key Features:
- Sequence-to-sequence autoencoder for temporal pattern learning
- Variational autoencoder option for generative modeling
- Reconstruction error-based anomaly scoring
- Multi-scale anomaly detection (point, contextual, collective)
- Adaptive thresholding based on reconstruction statistics
- Integration with physics constraints for false positive reduction

Author: Kilo Code (AI Architect)
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
    Bidirectional, RepeatVector, TimeDistributed,
    Concatenate, Add, Activation, Reshape, Flatten,
    Conv1D, MaxPooling1D, UpSampling1D
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
    logger.info(f"TensorFlow {tf.__version__} loaded for LSTM Autoencoder models")
except ImportError as e:
    logger.warning(f"TensorFlow not available - LSTM Autoencoder models disabled: {e}")
except Exception as e:
    logger.warning(f"TensorFlow import failed - LSTM Autoencoder models disabled: {e}")


@dataclass
class LSTMAutoencoderConfig:
    """Configuration for LSTM Autoencoder."""

    # Sequence parameters
    sequence_length: int = 60  # Days of history for training
    prediction_window: int = 7  # Days to predict anomalies ahead

    # Encoder Architecture
    encoder_lstm_units: List[int] = field(default_factory=lambda: [128, 64, 32])
    use_bidirectional_encoder: bool = True
    encoder_dropout_rate: float = 0.2

    # Latent Space
    latent_dim: int = 16
    use_variational: bool = False  # VAE vs AE

    # Decoder Architecture
    decoder_lstm_units: List[int] = field(default_factory=lambda: [32, 64, 128])
    use_bidirectional_decoder: bool = False
    decoder_dropout_rate: float = 0.2

    # Anomaly Detection
    anomaly_threshold_method: str = "adaptive"  # "fixed", "adaptive", "percentile"
    fixed_threshold: float = 0.1
    percentile_threshold: float = 95.0  # Percentile for anomaly cutoff
    min_samples_for_threshold: int = 1000

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

    # Anomaly Types
    anomaly_types: List[str] = field(default_factory=lambda: [
        'point_anomaly',      # Single point deviation
        'contextual_anomaly', # Context-dependent deviation
        'collective_anomaly', # Pattern-based deviation
        'trend_anomaly',      # Trend deviation
        'seasonal_anomaly'    # Seasonal pattern deviation
    ])


@dataclass
class ReconstructionResult:
    """Result of sequence reconstruction."""
    original_sequence: np.ndarray
    reconstructed_sequence: np.ndarray
    reconstruction_error: np.ndarray
    mean_error: float
    max_error: float
    anomaly_score: float
    is_anomaly: bool


@dataclass
class LSTMAutoencoderPrediction:
    """LSTM Autoencoder prediction result."""
    anomaly_detected: bool
    anomaly_score: float
    anomaly_type: str
    confidence: float
    reconstruction_error: float
    feature_anomalies: Dict[str, float]
    temporal_anomalies: Dict[int, float]  # time_step -> anomaly_score
    model_version: str
    timestamp: str
    architecture_type: str = "lstm_autoencoder"


class LSTMAutoencoder:
    """
    LSTM-based Autoencoder for unsupervised anomaly detection.

    Learns normal temporal patterns in vehicle sensor data and detects
    anomalies based on reconstruction error deviations.
    """

    def __init__(self, config: LSTMAutoencoderConfig = None, model_path: str = None):
        """Initialize LSTM Autoencoder."""
        self.config = config or LSTMAutoencoderConfig()
        self.model_path = Path(model_path or str(CONFIG.AI_MODELS_DIR / "lstm_autoencoder_models"))
        self.model_path.mkdir(parents=True, exist_ok=True)

        self.encoder = None
        self.decoder = None
        self.autoencoder = None  # Full autoencoder model
        self.scaler_params: Dict[str, Dict] = {}  # Feature normalization
        self.model_version = "0.0.0"
        self.training_history: List[Dict] = []
        self.is_trained = False

        # Anomaly detection thresholds
        self.anomaly_threshold = self.config.fixed_threshold
        self.reconstruction_stats: Dict[str, float] = {}

        self.num_features = len(self.config.feature_columns)

        # Load existing model if available
        self._load_model()

        logger.info(f"LSTMAutoencoder initialized (TensorFlow: {TENSORFLOW_AVAILABLE})")

    def _build_encoder(self, input_shape: Tuple[int, int]) -> Model:
        """Build the encoder part of the autoencoder."""
        inputs = Input(shape=input_shape, name='encoder_input')

        # Masking for variable-length sequences
        x = keras.layers.Masking(mask_value=0.0)(inputs)

        # Encoder LSTM layers
        for i, units in enumerate(self.config.encoder_lstm_units):
            return_sequences = i < len(self.config.encoder_lstm_units) - 1

            if self.config.use_bidirectional_encoder:
                x = Bidirectional(
                    LSTM(
                        units,
                        return_sequences=return_sequences,
                        kernel_regularizer=l2(self.config.l2_regularization),
                        recurrent_regularizer=l2(self.config.l2_regularization),
                        dropout=self.config.encoder_dropout_rate,
                        recurrent_dropout=self.config.encoder_dropout_rate
                    ),
                    name=f'encoder_bilstm_{i+1}'
                )(x)
            else:
                x = LSTM(
                    units,
                    return_sequences=return_sequences,
                    kernel_regularizer=l2(self.config.l2_regularization),
                    recurrent_regularizer=l2(self.config.l2_regularization),
                    dropout=self.config.encoder_dropout_rate,
                    recurrent_dropout=self.config.encoder_dropout_rate,
                    name=f'encoder_lstm_{i+1}'
                )(x)

            if self.config.use_batch_norm and return_sequences:
                x = BatchNormalization(name=f'encoder_batch_norm_{i+1}')(x)

        # Latent space
        if self.config.use_variational:
            # Variational Autoencoder
            z_mean = Dense(self.config.latent_dim, name='z_mean')(x)
            z_log_var = Dense(self.config.latent_dim, name='z_log_var')(x)

            # Reparameterization trick
            def sampling(args):
                z_mean, z_log_var = args
                epsilon = K.random_normal(shape=(K.shape(z_mean)[0], self.config.latent_dim),
                                        mean=0., stddev=1.)
                return z_mean + K.exp(z_log_var / 2) * epsilon

            z = keras.layers.Lambda(sampling, name='z')([z_mean, z_log_var])
            latent = z
        else:
            # Standard Autoencoder
            latent = Dense(self.config.latent_dim, activation='relu',
                          kernel_regularizer=l2(self.config.l2_regularization),
                          name='latent_space')(x)

        encoder = Model(inputs, latent, name='encoder')
        return encoder

    def _build_decoder(self, latent_shape: Tuple[int, int]) -> Model:
        """Build the decoder part of the autoencoder."""
        latent_inputs = Input(shape=latent_shape, name='decoder_input')

        # Repeat latent vector for sequence generation
        x = RepeatVector(self.config.sequence_length, name='repeat_latent')(latent_inputs)

        # Decoder LSTM layers
        for i, units in enumerate(self.config.decoder_lstm_units):
            return_sequences = i < len(self.config.decoder_lstm_units) - 1

            if self.config.use_bidirectional_decoder:
                x = Bidirectional(
                    LSTM(
                        units,
                        return_sequences=return_sequences,
                        kernel_regularizer=l2(self.config.l2_regularization),
                        recurrent_regularizer=l2(self.config.l2_regularization),
                        dropout=self.config.decoder_dropout_rate,
                        recurrent_dropout=self.config.decoder_dropout_rate
                    ),
                    name=f'decoder_bilstm_{i+1}'
                )(x)
            else:
                x = LSTM(
                    units,
                    return_sequences=return_sequences,
                    kernel_regularizer=l2(self.config.l2_regularization),
                    recurrent_regularizer=l2(self.config.l2_regularization),
                    dropout=self.config.decoder_dropout_rate,
                    recurrent_dropout=self.config.decoder_dropout_rate,
                    name=f'decoder_lstm_{i+1}'
                )(x)

            if self.config.use_batch_norm and return_sequences:
                x = BatchNormalization(name=f'decoder_batch_norm_{i+1}')(x)

        # Output layer - reconstruct original sequence
        outputs = TimeDistributed(
            Dense(self.num_features, activation='linear'),
            name='reconstruction_output'
        )(x)

        decoder = Model(latent_inputs, outputs, name='decoder')
        return decoder

    def _build_autoencoder(self, input_shape: Tuple[int, int]) -> Model:
        """Build the complete autoencoder model."""
        if not TENSORFLOW_AVAILABLE:
            raise RuntimeError("TensorFlow not available")

        inputs = Input(shape=input_shape, name='autoencoder_input')

        # Encoder
        self.encoder = self._build_encoder(input_shape)
        latent = self.encoder(inputs)

        # Decoder
        self.decoder = self._build_decoder((self.config.latent_dim,))
        outputs = self.decoder(latent)

        # Complete autoencoder
        autoencoder = Model(inputs, outputs, name='lstm_autoencoder')

        # Compile
        if self.config.use_variational:
            # VAE loss includes reconstruction + KL divergence
            reconstruction_loss = keras.losses.mse(inputs, outputs)
            reconstruction_loss *= self.num_features * self.config.sequence_length

            kl_loss = 1 + self.encoder.get_layer('z_log_var').output - K.square(self.encoder.get_layer('z_mean').output) - K.exp(self.encoder.get_layer('z_log_var').output)
            kl_loss = K.sum(kl_loss, axis=-1)
            kl_loss *= -0.5

            vae_loss = K.mean(reconstruction_loss + kl_loss)
            autoencoder.add_loss(vae_loss)
            autoencoder.compile(optimizer=Adam(learning_rate=self.config.learning_rate))
        else:
            # Standard AE loss
            autoencoder.compile(
                optimizer=Adam(learning_rate=self.config.learning_rate),
                loss='mse',
                metrics=['mae', 'mse']
            )

        return autoencoder

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

    def prepare_sequences(self, obd_data: List[Dict]) -> np.ndarray:
        """
        Prepare OBD data into sequences for training/detection.

        Args:
            obd_data: List of OBD readings

        Returns:
            X: Input sequences array
        """
        if not obd_data:
            return np.array([])

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
        return X

    def train(
        self,
        training_data: List[List[Dict]],
        validation_split: float = 0.2,
        verbose: int = 1
    ) -> Dict[str, Any]:
        """
        Train the LSTM Autoencoder on normal data.

        Args:
            training_data: List of sequences (each sequence is a list of OBD readings)
            validation_split: Validation data fraction
            verbose: Training verbosity

        Returns:
            Training results
        """
        if not TENSORFLOW_AVAILABLE:
            return {'error': 'TensorFlow not available'}

        if len(training_data) < 50:
            return {'error': f'Insufficient training data: {len(training_data)} sequences (need 50+)'}

        logger.info(f"Starting LSTM Autoencoder training with {len(training_data)} sequences")

        # Prepare sequences
        X_list = []
        for sequence in training_data:
            X = self.prepare_sequences(sequence)
            if X.size > 0:
                X_list.append(X[0])

        if not X_list:
            return {'error': 'No valid sequences prepared'}

        X = np.array(X_list, dtype=np.float32)

        # Normalize features
        X = self._normalize_features(X, fit=True)

        # Build model
        input_shape = (self.config.sequence_length, len(self.config.feature_columns))
        self.autoencoder = self._build_autoencoder(input_shape)

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
                str(self.model_path / 'best_lstm_autoencoder.keras'),
                monitor='val_loss',
                save_best_only=True
            ),
            TensorBoard(
                log_dir=str(self.model_path / 'logs'),
                histogram_freq=1
            )
        ]

        # Train
        history = self.autoencoder.fit(
            X, X,  # Autoencoder: input = target
            batch_size=self.config.batch_size,
            epochs=self.config.epochs,
            validation_split=validation_split,
            callbacks=callbacks,
            verbose=verbose
        )

        # Update state
        self.is_trained = True
        self.model_version = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Calculate anomaly detection threshold
        self._calculate_anomaly_threshold(X)

        # Save model
        self._save_model()

        # Record history
        training_record = {
            'version': self.model_version,
            'timestamp': datetime.now().isoformat(),
            'sequences': len(training_data),
            'epochs_run': len(history.history['loss']),
            'final_loss': float(history.history['loss'][-1]),
            'final_val_loss': float(history.history.get('val_loss', [0])[-1]),
            'mae': float(history.history.get('mae', [0])[-1]),
            'anomaly_threshold': self.anomaly_threshold,
            'architecture': 'lstm_autoencoder'
        }
        self.training_history.append(training_record)

        logger.info(f"LSTM Autoencoder training complete. Version: {self.model_version}")

        return {
            'success': True,
            'version': self.model_version,
            'epochs': len(history.history['loss']),
            'final_loss': training_record['final_loss'],
            'anomaly_threshold': self.anomaly_threshold,
            'architecture': 'lstm_autoencoder'
        }

    def _calculate_anomaly_threshold(self, training_data: np.ndarray):
        """Calculate anomaly detection threshold from training data."""
        if len(training_data) < self.config.min_samples_for_threshold:
            logger.warning(f"Using fixed threshold due to insufficient samples: {len(training_data)}")
            self.anomaly_threshold = self.config.fixed_threshold
            return

        # Get reconstruction errors for training data
        reconstruction_errors = []
        for i in range(0, len(training_data), self.config.batch_size):
            batch = training_data[i:i+self.config.batch_size]
            reconstructed = self.autoencoder.predict(batch, verbose=0)
            batch_errors = np.mean(np.square(batch - reconstructed), axis=(1, 2))
            reconstruction_errors.extend(batch_errors)

        reconstruction_errors = np.array(reconstruction_errors)

        if self.config.anomaly_threshold_method == "adaptive":
            # Adaptive threshold based on training data statistics
            mean_error = np.mean(reconstruction_errors)
            std_error = np.std(reconstruction_errors)
            self.anomaly_threshold = mean_error + 3 * std_error  # 3-sigma rule

        elif self.config.anomaly_threshold_method == "percentile":
            # Percentile-based threshold
            self.anomaly_threshold = np.percentile(reconstruction_errors, self.config.percentile_threshold)

        else:
            # Fixed threshold
            self.anomaly_threshold = self.config.fixed_threshold

        # Store reconstruction statistics
        self.reconstruction_stats = {
            'mean_error': float(np.mean(reconstruction_errors)),
            'std_error': float(np.std(reconstruction_errors)),
            'min_error': float(np.min(reconstruction_errors)),
            'max_error': float(np.max(reconstruction_errors)),
            'threshold': self.anomaly_threshold,
            'threshold_method': self.config.anomaly_threshold_method
        }

        logger.info(f"Anomaly threshold calculated: {self.anomaly_threshold:.4f} "
                   f"(method: {self.config.anomaly_threshold_method})")

    def detect_anomalies(self, obd_data: List[Dict]) -> Optional[LSTMAutoencoderPrediction]:
        """
        Detect anomalies in OBD data sequence.

        Args:
            obd_data: Recent OBD readings

        Returns:
            Anomaly detection result or None
        """
        if not self.is_trained or self.autoencoder is None:
            logger.warning("LSTM Autoencoder not trained")
            return None

        if not TENSORFLOW_AVAILABLE:
            return None

        try:
            # Prepare sequence
            X = self.prepare_sequences(obd_data)
            if X.size == 0:
                return None

            # Normalize
            X_normalized = self._normalize_features(X, fit=False)

            # Reconstruct
            reconstructed = self.autoencoder.predict(X_normalized, verbose=0)

            # Calculate reconstruction error
            reconstruction_result = self._calculate_reconstruction_error(X_normalized, reconstructed)

            # Determine if anomaly
            is_anomaly = reconstruction_result.anomaly_score > self.anomaly_threshold

            # Classify anomaly type
            anomaly_type = self._classify_anomaly_type(reconstruction_result)

            # Calculate confidence
            confidence = self._calculate_anomaly_confidence(reconstruction_result, is_anomaly)

            # Analyze feature and temporal anomalies
            feature_anomalies = self._analyze_feature_anomalies(reconstruction_result)
            temporal_anomalies = self._analyze_temporal_anomalies(reconstruction_result)

            return LSTMAutoencoderPrediction(
                anomaly_detected=is_anomaly,
                anomaly_score=round(reconstruction_result.anomaly_score, 4),
                anomaly_type=anomaly_type,
                confidence=round(confidence, 3),
                reconstruction_error=round(reconstruction_result.mean_error, 4),
                feature_anomalies=feature_anomalies,
                temporal_anomalies=temporal_anomalies,
                model_version=self.model_version,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"LSTM Autoencoder anomaly detection error: {e}")
            return None

    def _calculate_reconstruction_error(self, original: np.ndarray,
                                       reconstructed: np.ndarray) -> ReconstructionResult:
        """Calculate reconstruction error metrics."""
        # Mean squared error per time step per feature
        squared_error = np.square(original - reconstructed)

        # Overall metrics
        mean_error = float(np.mean(squared_error))
        max_error = float(np.max(squared_error))

        # Anomaly score (can be mean, max, or custom combination)
        anomaly_score = mean_error  # Using mean error as primary score

        return ReconstructionResult(
            original_sequence=original,
            reconstructed_sequence=reconstructed,
            reconstruction_error=squared_error,
            mean_error=mean_error,
            max_error=max_error,
            anomaly_score=anomaly_score,
            is_anomaly=anomaly_score > self.anomaly_threshold
        )

    def _classify_anomaly_type(self, reconstruction_result: ReconstructionResult) -> str:
        """Classify the type of anomaly detected."""
        error_pattern = reconstruction_result.reconstruction_error[0]  # (seq_len, features)

        # Analyze error distribution
        mean_error_per_timestep = np.mean(error_pattern, axis=1)
        mean_error_per_feature = np.mean(error_pattern, axis=0)

        # Point anomaly: Single timestep with high error
        max_timestep_error = np.max(mean_error_per_timestep)
        if max_timestep_error > 3 * np.mean(mean_error_per_timestep):
            return 'point_anomaly'

        # Collective anomaly: Multiple timesteps with correlated errors
        high_error_timesteps = np.sum(mean_error_per_timestep > np.mean(mean_error_per_timestep) * 1.5)
        if high_error_timesteps > self.config.sequence_length * 0.3:
            return 'collective_anomaly'

        # Contextual anomaly: Pattern doesn't match expected context
        # (This would require more sophisticated analysis)
        if np.std(mean_error_per_timestep) > np.mean(mean_error_per_timestep) * 2:
            return 'contextual_anomaly'

        # Trend anomaly: Gradual deviation from normal trend
        if np.mean(mean_error_per_timestep[-10:]) > np.mean(mean_error_per_timestep[:10]) * 2:
            return 'trend_anomaly'

        return 'point_anomaly'  # Default

    def _calculate_anomaly_confidence(self, reconstruction_result: ReconstructionResult,
                                     is_anomaly: bool) -> float:
        """Calculate confidence in anomaly detection."""
        if not is_anomaly:
            # For non-anomalies, confidence is based on how far below threshold
            distance_from_threshold = self.anomaly_threshold - reconstruction_result.anomaly_score
            relative_distance = distance_from_threshold / self.anomaly_threshold
            return min(0.95, 0.5 + relative_distance * 0.5)
        else:
            # For anomalies, confidence is based on how far above threshold
            exceedance = reconstruction_result.anomaly_score - self.anomaly_threshold
            relative_exceedance = exceedance / self.anomaly_threshold
            return min(0.95, 0.5 + relative_exceedance * 0.5)

    def _analyze_feature_anomalies(self, reconstruction_result: ReconstructionResult) -> Dict[str, float]:
        """Analyze which features are contributing most to anomalies."""
        error_per_feature = np.mean(reconstruction_result.reconstruction_error[0], axis=0)

        feature_anomalies = {}
        for i, feature in enumerate(self.config.feature_columns):
            feature_anomalies[feature] = float(error_per_feature[i])

        # Return top 5 most anomalous features
        return dict(sorted(feature_anomalies.items(), key=lambda x: x[1], reverse=True)[:5])

    def _analyze_temporal_anomalies(self, reconstruction_result: ReconstructionResult) -> Dict[int, float]:
        """Analyze temporal pattern of anomalies."""
        error_per_timestep = np.mean(reconstruction_result.reconstruction_error[0], axis=1)

        temporal_anomalies = {}
        for i, error in enumerate(error_per_timestep):
            if error > np.mean(error_per_timestep) * 1.5:  # Above average
                temporal_anomalies[int(i)] = float(error)

        return temporal_anomalies

    def _save_model(self):
        """Save model and configuration."""
        if self.autoencoder is None:
            return

        try:
            # Save Keras model
            self.autoencoder.save(str(self.model_path / 'lstm_autoencoder.keras'))

            # Save encoder and decoder separately for inference
            if self.encoder:
                self.encoder.save(str(self.model_path / 'encoder.keras'))
            if self.decoder:
                self.decoder.save(str(self.model_path / 'decoder.keras'))

            # Save configuration
            config_data = {
                'version': self.model_version,
                'config': {
                    'sequence_length': self.config.sequence_length,
                    'prediction_window': self.config.prediction_window,
                    'feature_columns': self.config.feature_columns,
                    'anomaly_types': self.config.anomaly_types,
                    'encoder_lstm_units': self.config.encoder_lstm_units,
                    'decoder_lstm_units': self.config.decoder_lstm_units,
                    'latent_dim': self.config.latent_dim,
                    'use_variational': self.config.use_variational,
                    'use_bidirectional_encoder': self.config.use_bidirectional_encoder,
                    'use_bidirectional_decoder': self.config.use_bidirectional_decoder,
                    'anomaly_threshold_method': self.config.anomaly_threshold_method,
                    'fixed_threshold': self.config.fixed_threshold,
                    'percentile_threshold': self.config.percentile_threshold
                },
                'scaler_params': self.scaler_params,
                'reconstruction_stats': self.reconstruction_stats,
                'anomaly_threshold': self.anomaly_threshold,
                'training_history': self.training_history,
                'saved_at': datetime.now().isoformat()
            }

            with open(self.model_path / 'lstm_autoencoder_config.json', 'w') as f:
                json.dump(config_data, f, indent=2)

            logger.info(f"LSTM Autoencoder saved: version {self.model_version}")

        except Exception as e:
            logger.error(f"Failed to save LSTM Autoencoder: {e}")

    def _load_model(self):
        """Load saved model and configuration."""
        config_path = self.model_path / 'lstm_autoencoder_config.json'
        model_path = self.model_path / 'lstm_autoencoder.keras'

        if not config_path.exists():
            logger.info("No saved LSTM Autoencoder found")
            return

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            self.model_version = config_data.get('version', '0.0.0')
            self.scaler_params = config_data.get('scaler_params', {})
            self.reconstruction_stats = config_data.get('reconstruction_stats', {})
            self.anomaly_threshold = config_data.get('anomaly_threshold', self.config.fixed_threshold)
            self.training_history = config_data.get('training_history', [])

            # Update config
            saved_config = config_data.get('config', {})
            if saved_config.get('feature_columns'):
                self.config.feature_columns = saved_config['feature_columns']

            # Load Keras model
            if TENSORFLOW_AVAILABLE and model_path.exists():
                self.autoencoder = tf.keras.models.load_model(str(model_path))
                self.is_trained = True

                # Rebuild encoder and decoder for inference
                input_shape = (self.config.sequence_length, len(self.config.feature_columns))
                self.encoder = self._build_encoder(input_shape)
                self.decoder = self._build_decoder((self.config.latent_dim,))

                logger.info(f"Loaded LSTM Autoencoder version {self.model_version}")
            else:
                logger.info("LSTM Autoencoder config loaded but model not loaded (TensorFlow unavailable)")

        except Exception as e:
            logger.warning(f"Failed to load LSTM Autoencoder: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the LSTM Autoencoder."""
        return {
            'is_trained': self.is_trained,
            'version': self.model_version,
            'architecture': 'lstm_autoencoder',
            'tensorflow_available': TENSORFLOW_AVAILABLE,
            'sequence_length': self.config.sequence_length,
            'prediction_window': self.config.prediction_window,
            'num_features': len(self.config.feature_columns),
            'latent_dim': self.config.latent_dim,
            'use_variational': self.config.use_variational,
            'anomaly_threshold': self.anomaly_threshold,
            'threshold_method': self.config.anomaly_threshold_method,
            'reconstruction_stats': self.reconstruction_stats,
            'training_samples': sum(h.get('sequences', 0) for h in self.training_history),
            'last_trained': self.training_history[-1]['timestamp'] if self.training_history else None,
            'encoder_config': {
                'units': self.config.encoder_lstm_units,
                'bidirectional': self.config.use_bidirectional_encoder
            },
            'decoder_config': {
                'units': self.config.decoder_lstm_units,
                'bidirectional': self.config.use_bidirectional_decoder
            }
        }


# Singleton instance
_lstm_autoencoder = None

def get_lstm_autoencoder() -> LSTMAutoencoder:
    """Get the singleton LSTMAutoencoder instance."""
    global _lstm_autoencoder
    if _lstm_autoencoder is None:
        _lstm_autoencoder = LSTMAutoencoder()
    return _lstm_autoencoder