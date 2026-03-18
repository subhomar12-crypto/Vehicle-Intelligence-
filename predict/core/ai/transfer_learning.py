"""Transfer learning — fine-tune base fleet models on vehicle-specific data.

Loads pre-trained base models and fine-tunes on new vehicle data for faster
convergence and better initial accuracy.
"""

import hashlib
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import tensorflow as tf
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.ai.lstm_trainer import LSTMTrainer
from predict.core.ai.data_loader import LSTMDataLoader

logger = logging.getLogger(__name__)


class TransferLearning:
    """Fine-tune base models on vehicle-specific data."""
    
    def __init__(
        self,
        freeze_layers: int = 2,
        learning_rate: float = 0.0001,
        epochs: int = 50,
    ):
        """Initialize transfer learning.
        
        Args:
            freeze_layers: Number of layers to freeze in base model
            learning_rate: Learning rate for fine-tuning (lower than training)
            epochs: Training epochs for fine-tuning
        """
        self.freeze_layers = freeze_layers
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.base_model = None
        
    async def load_base_model(
        self,
        session: AsyncSession,
        make: str,
        model: Optional[str] = None,
        model_type: str = "health",
    ) -> Optional[str]:
        """Load base model for transfer learning.
        
        Args:
            session: Database session
            make: Vehicle make (e.g., 'Toyota')
            model: Vehicle model (optional)
            model_type: Type of model ('health', 'anomaly', 'context')
            
        Returns:
            Path to loaded model file, or None if not found
        """
        from predict.core.db.models.model_registry import BaseModelEntry
        
        # Query for base model
        if model:
            # Try specific make + model first
            result = await session.execute(
                select(BaseModelEntry).where(
                    and_(
                        BaseModelEntry.make == make,
                        BaseModelEntry.model == model,
                        BaseModelEntry.model_type == model_type,
                    )
                )
            )
            entry = result.scalar_one_or_none()
            
            if not entry:
                # Fall back to make-only model
                result = await session.execute(
                    select(BaseModelEntry).where(
                        and_(
                            BaseModelEntry.make == make,
                            BaseModelEntry.model.is_(None),
                            BaseModelEntry.model_type == model_type,
                        )
                    )
                )
                entry = result.scalar_one_or_none()
        else:
            # Query make-only model
            result = await session.execute(
                select(BaseModelEntry).where(
                    and_(
                        BaseModelEntry.make == make,
                        BaseModelEntry.model.is_(None),
                        BaseModelEntry.model_type == model_type,
                    )
                )
            )
            entry = result.scalar_one_or_none()
        
        if not entry:
            logger.warning(f"No base model found for {make} {model} {model_type}")
            return None
        
        # Verify file exists
        model_path = Path(entry.file_path)
        if not model_path.exists():
            logger.error(f"Base model file not found: {model_path}")
            return None
        
        # Load model
        try:
            self.base_model = tf.keras.models.load_model(model_path)
            logger.info(f"Loaded base model from {model_path}")
            return str(model_path)
        except Exception as e:
            logger.error(f"Failed to load base model: {e}")
            return None
    
    def prepare_for_fine_tuning(self) -> tf.keras.Model:
        """Prepare base model for fine-tuning.
        
        Freezes bottom layers and compiles with lower learning rate.
        
        Returns:
            Prepared model
        """
        if self.base_model is None:
            raise ValueError("No base model loaded. Call load_base_model first.")
        
        # Freeze bottom layers
        for i, layer in enumerate(self.base_model.layers):
            if i < self.freeze_layers:
                layer.trainable = False
                logger.debug(f"Frozen layer: {layer.name}")
            else:
                layer.trainable = True
        
        # Recompile with lower learning rate
        self.base_model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss='mse',
            metrics=['mae'],
        )
        
        logger.info(f"Prepared model for fine-tuning: {self.freeze_layers} layers frozen")
        return self.base_model
    
    async def fine_tune(
        self,
        session: AsyncSession,
        profile_id: int,
        make: str,
        model: Optional[str] = None,
        min_samples: int = 500,
    ) -> Dict[str, Any]:
        """Fine-tune base model on vehicle-specific data.
        
        Args:
            session: Database session
            profile_id: Vehicle profile ID
            make: Vehicle make
            model: Vehicle model (optional)
            min_samples: Minimum samples required
            
        Returns:
            Training results dict
        """
        # Load base model
        base_path = await self.load_base_model(session, make, model)
        if not base_path:
            logger.warning("No base model available, training from scratch")
            # Fall back to training from scratch
            trainer = LSTMTrainer(epochs=self.epochs)
            return await trainer.train_from_profile(session, profile_id)
        
        # Load vehicle data
        loader = LSTMDataLoader()
        data = await loader.load_from_db(session, profile_id, limit=50000)
        
        if len(data) < min_samples:
            raise ValueError(
                f"Insufficient data: need {min_samples}, got {len(data)}"
            )
        
        # Normalize
        normalized, mins, maxs = loader.normalize(data)
        
        # Create sequences
        sequences = loader.create_sequences(normalized, window_size=60)
        
        if len(sequences) < 10:
            raise ValueError(f"Insufficient sequences: got {len(sequences)}")
        
        # Split train/val
        split_idx = int(len(sequences) * 0.8)
        train_seq = sequences[:split_idx]
        val_seq = sequences[split_idx:]
        
        # Prepare model
        model = self.prepare_for_fine_tuning()
        
        # Fine-tune
        logger.info(f"Fine-tuning on {len(train_seq)} sequences")
        
        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=5,
                restore_best_weights=True,
            ),
        ]
        
        history = model.fit(
            train_seq, train_seq,
            epochs=self.epochs,
            batch_size=32,
            validation_data=(val_seq, val_seq),
            callbacks=callbacks,
            verbose=1,
        )
        
        # Calculate reconstruction error threshold
        val_pred = model.predict(val_seq, verbose=0)
        reconstruction_errors = tf.reduce_mean(
            tf.abs(val_seq - val_pred), axis=(1, 2)
        ).numpy()
        threshold = float(tf.reduce_percentile(reconstruction_errors, 95))
        
        return {
            "final_loss": float(history.history['loss'][-1]),
            "final_val_loss": float(history.history['val_loss'][-1]),
            "epochs_trained": len(history.history['loss']),
            "threshold": threshold,
            "base_model_used": base_path,
            "train_sequences": len(train_seq),
            "val_sequences": len(val_seq),
        }
    
    async def save_model_version(
        self,
        session: AsyncSession,
        profile_id: int,
        model_type: str,
        model: tf.keras.Model,
        training_metrics: Dict[str, Any],
        file_path: str,
    ) -> int:
        """Save model version to database.
        
        Args:
            session: Database session
            profile_id: Vehicle profile ID
            model_type: Type of model
            model: Trained Keras model
            training_metrics: Training metrics dict
            file_path: Path to saved model file
            
        Returns:
            Model version ID
        """
        from predict.core.db.models.model_registry import ModelVersion
        
        # Calculate file hash
        file_path_obj = Path(file_path)
        file_bytes = file_path_obj.read_bytes()
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        # Get next version number
        result = await session.execute(
            select(ModelVersion).where(
                and_(
                    ModelVersion.profile_id == profile_id,
                    ModelVersion.model_type == model_type,
                )
            )
        )
        existing = result.scalars().all()
        next_version = max([v.version for v in existing], default=0) + 1
        
        # Create model version entry
        version = ModelVersion(
            profile_id=profile_id,
            model_type=model_type,
            version=next_version,
            file_path=file_path,
            file_size_bytes=len(file_bytes),
            sha256=sha256,
            training_data_points=training_metrics.get("train_sequences", 0),
            validation_accuracy=training_metrics.get("final_val_loss", 0.0),
        )
        
        session.add(version)
        await session.flush()
        
        logger.info(f"Saved model version {next_version} for profile {profile_id}")
        
        return version.id


async def transfer_learn_vehicle(
    profile_id: int,
    make: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """ARQ job: Transfer learn for a specific vehicle.
    
    Args:
        profile_id: Vehicle profile ID
        make: Vehicle make
        model: Vehicle model (optional)
        
    Returns:
        Training results
    """
    from predict.core.db.session import get_session_maker
    
    transfer = TransferLearning()
    
    async with get_session_maker()() as session:
        try:
            metrics = await transfer.fine_tune(
                session, profile_id, make, model
            )
            
            # Save model
            model_path = f"/app/models/transfer_{profile_id}_{datetime.utcnow().strftime('%Y%m%d')}.keras"
            transfer.base_model.save(model_path)
            
            # Save version
            version_id = await transfer.save_model_version(
                session, profile_id, "health", transfer.base_model, metrics, model_path
            )
            
            await session.commit()
            
            return {
                "profile_id": profile_id,
                "status": "success",
                "model_version_id": version_id,
                "metrics": metrics,
            }
            
        except Exception as e:
            logger.exception(f"Transfer learning failed for {profile_id}: {e}")
            return {
                "profile_id": profile_id,
                "status": "failed",
                "error": str(e),
            }
