"""LSTM trainer — train autoencoder on healthy sequences, export to TFLite.

Uses predict.core.ai.data_loader for data preparation.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
import tensorflow as tf
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.ai.data_loader import LSTMDataLoader, FEATURE_COLUMNS

logger = logging.getLogger(__name__)


class LSTMTrainer:
    """Train LSTM autoencoder for anomaly detection and export to TFLite."""
    
    def __init__(
        self,
        window_size: int = 60,
        lstm_units: int = 64,
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
    ):
        """Initialize trainer.
        
        Args:
            window_size: Sequence length (default 60 = 1 minute at 1Hz)
            lstm_units: LSTM hidden units
            epochs: Training epochs
            batch_size: Batch size
            learning_rate: Adam learning rate
        """
        self.window_size = window_size
        self.lstm_units = lstm_units
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.model = None
        self.threshold = None
        
    def build_model(self) -> tf.keras.Model:
        """Build LSTM autoencoder model.
        
        Returns:
            Compiled Keras model
        """
        model = tf.keras.Sequential([
            # Encoder
            tf.keras.layers.LSTM(
                self.lstm_units,
                activation='tanh',
                return_sequences=False,
                input_shape=(self.window_size, 15),
            ),
            tf.keras.layers.RepeatVector(self.window_size),
            
            # Decoder
            tf.keras.layers.LSTM(
                self.lstm_units,
                activation='tanh',
                return_sequences=True,
            ),
            tf.keras.layers.TimeDistributed(
                tf.keras.layers.Dense(15, activation='linear')
            ),
        ])
        
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss='mse',
            metrics=['mae'],
        )
        
        self.model = model
        logger.info(f"Built LSTM autoencoder: {model.summary()}")
        return model
    
    async def train_from_profile(
        self,
        session: AsyncSession,
        profile_id: int,
        limit: int = 50000,
    ) -> Dict[str, Any]:
        """Train model from vehicle profile data.
        
        Args:
            session: Database session
            profile_id: Vehicle profile ID
            limit: Max rows to load
            
        Returns:
            Training metrics dict
        """
        # Load data
        loader = LSTMDataLoader()
        data = await loader.load_from_db(session, profile_id, limit=limit)
        
        if len(data) < self.window_size * 2:
            raise ValueError(
                f"Insufficient data: need {self.window_size * 2} rows, got {len(data)}"
            )
        
        # Normalize
        normalized, mins, maxs = loader.normalize(data)
        
        # Create sequences
        sequences = loader.create_sequences(normalized, self.window_size)
        
        if len(sequences) < 10:
            raise ValueError(f"Insufficient sequences: got {len(sequences)}")
        
        # Split train/val (80/20)
        split_idx = int(len(sequences) * 0.8)
        train_seq = sequences[:split_idx]
        val_seq = sequences[split_idx:]
        
        # Build model if not exists
        if self.model is None:
            self.build_model()
        
        # Train
        logger.info(f"Training on {len(train_seq)} sequences, validating on {len(val_seq)}")
        
        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-6,
            ),
        ]
        
        history = self.model.fit(
            train_seq, train_seq,  # Autoencoder: input == target
            epochs=self.epochs,
            batch_size=self.batch_size,
            validation_data=(val_seq, val_seq),
            callbacks=callbacks,
            verbose=1,
        )
        
        # Compute reconstruction error threshold (95th percentile)
        val_pred = self.model.predict(val_seq, verbose=0)
        reconstruction_errors = np.mean(np.abs(val_seq - val_pred), axis=(1, 2))
        self.threshold = float(np.percentile(reconstruction_errors, 95))
        
        metrics = {
            "final_loss": float(history.history['loss'][-1]),
            "final_val_loss": float(history.history['val_loss'][-1]),
            "epochs_trained": len(history.history['loss']),
            "threshold": self.threshold,
            "train_sequences": len(train_seq),
            "val_sequences": len(val_seq),
        }
        
        logger.info(f"Training complete: {metrics}")
        return metrics
    
    def export_tflite(
        self,
        output_path: str,
        quantization: str = "float16",
    ) -> str:
        """Export model to TFLite format for Pi5.
        
        Args:
            output_path: Path to save .tflite file
            quantization: "float16" or "int8"
            
        Returns:
            Path to exported file
        """
        if self.model is None:
            raise ValueError("No model to export")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to TFLite
        converter = tf.lite.TFLiteConverter.from_keras_model(self.model)
        
        # Apply quantization
        if quantization == "float16":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_types = [tf.float16]
        elif quantization == "int8":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            # Note: Requires representative dataset for full INT8
            # For now, use dynamic range quantization
        else:
            raise ValueError(f"Unknown quantization: {quantization}")
        
        # Enable TensorFlow ops (for LSTM)
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS,
            tf.lite.OpsSet.SELECT_TF_OPS,
        ]
        
        # Convert
        logger.info(f"Converting to TFLite with {quantization} quantization...")
        tflite_model = converter.convert()
        
        # Save
        output_path.write_bytes(tflite_model)
        
        # Also save normalization params
        norm_path = output_path.with_suffix('.norm.json')
        # Note: Normalization params should be saved separately
        
        logger.info(f"Exported TFLite model to {output_path} ({len(tflite_model)} bytes)")
        return str(output_path)
    
    def save_normalization_params(
        self,
        output_path: str,
        mins: np.ndarray,
        maxs: np.ndarray,
    ) -> str:
        """Save normalization parameters alongside model.
        
        Args:
            output_path: Path to save .json file
            mins: Minimum values per feature
            maxs: Maximum values per feature
            
        Returns:
            Path to saved file
        """
        import json
        
        params = {
            "feature_columns": FEATURE_COLUMNS,
            "mins": mins.tolist(),
            "maxs": maxs.tolist(),
        }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(params, f, indent=2)
        
        logger.info(f"Saved normalization params to {output_path}")
        return str(output_path)
    
    def predict_anomaly_score(
        self,
        sequence: np.ndarray,
    ) -> float:
        """Predict anomaly score for a single sequence.
        
        Args:
            sequence: (window_size, 15) normalized sequence
            
        Returns:
            Reconstruction error (higher = more anomalous)
        """
        if self.model is None:
            raise ValueError("No model loaded")
        
        if sequence.shape != (self.window_size, 15):
            raise ValueError(f"Expected shape ({self.window_size}, 15), got {sequence.shape}")
        
        # Add batch dimension
        sequence = np.expand_dims(sequence, axis=0)
        
        # Predict
        reconstructed = self.model.predict(sequence, verbose=0)
        
        # Compute reconstruction error
        error = np.mean(np.abs(sequence - reconstructed))
        
        return float(error)
    
    def is_anomaly(
        self,
        sequence: np.ndarray,
    ) -> Tuple[bool, float]:
        """Check if sequence is anomalous.
        
        Args:
            sequence: (window_size, 15) normalized sequence
            
        Returns:
            (is_anomaly, anomaly_score)
        """
        score = self.predict_anomaly_score(sequence)
        is_anom = score > self.threshold if self.threshold else False
        return is_anom, score
