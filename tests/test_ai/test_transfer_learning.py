"""Tests for transfer learning."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import hashlib

import numpy as np

from predict.core.ai.transfer_learning import (
    TransferLearning,
    transfer_learn_vehicle,
)


class TestTransferLearning:
    """Test TransferLearning class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.transfer = TransferLearning(
            freeze_layers=2,
            learning_rate=0.0001,
            epochs=10,
        )

    def test_init_params(self):
        """Initialization stores parameters."""
        assert self.transfer.freeze_layers == 2
        assert self.transfer.learning_rate == 0.0001
        assert self.transfer.epochs == 10
        assert self.transfer.base_model is None

    @pytest.mark.asyncio
    async def test_load_base_model_not_found(self):
        """Load returns None when no base model exists."""
        mock_session = AsyncMock()
        
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        path = await self.transfer.load_base_model(
            mock_session, "Toyota", "Camry", "health"
        )
        
        assert path is None

    @pytest.mark.asyncio
    async def test_load_base_model_file_not_exists(self):
        """Load returns None when file doesn't exist."""
        mock_session = AsyncMock()
        
        # Create mock entry
        entry = MagicMock()
        entry.file_path = "/nonexistent/model.keras"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        mock_session.execute.return_value = mock_result
        
        path = await self.transfer.load_base_model(
            mock_session, "Toyota", None, "health"
        )
        
        assert path is None

    def test_prepare_for_fine_tuning_no_model(self):
        """Prepare raises error if no base model loaded."""
        with pytest.raises(ValueError, match="No base model loaded"):
            self.transfer.prepare_for_fine_tuning()

    def test_prepare_for_fine_tuning_success(self):
        """Prepare freezes layers and compiles model."""
        pytest.importorskip("tensorflow", reason="tensorflow not installed")
        
        import tensorflow as tf
        
        # Create simple test model
        model = tf.keras.Sequential([
            tf.keras.layers.LSTM(32, return_sequences=True, input_shape=(10, 5)),
            tf.keras.layers.LSTM(16, return_sequences=True),
            tf.keras.layers.Dense(5),
        ])
        
        self.transfer.base_model = model
        
        prepared = self.transfer.prepare_for_fine_tuning()
        
        # Check first 2 layers are frozen
        assert not prepared.layers[0].trainable
        assert not prepared.layers[1].trainable
        # Last layer should be trainable
        assert prepared.layers[2].trainable

    @pytest.mark.asyncio
    async def test_save_model_version(self):
        """Save creates ModelVersion entry."""
        mock_session = AsyncMock()
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.keras') as f:
            f.write(b"fake model data")
            temp_path = f.name
        
        try:
            # Mock existing versions query
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_result
            
            metrics = {"train_sequences": 100, "final_val_loss": 0.1}
            
            pytest.importorskip("tensorflow", reason="tensorflow not installed")
            import tensorflow as tf
            
            # Create dummy model
            model = tf.keras.Sequential([tf.keras.layers.Dense(1)])
            
            version_id = await self.transfer.save_model_version(
                mock_session, 1, "health", model, metrics, temp_path
            )
            
            # Verify session.add was called
            assert mock_session.add.called
            assert mock_session.flush.called
            
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestARQJobs:
    """Test ARQ job functions."""

    @pytest.mark.asyncio
    async def test_transfer_learn_vehicle_runs(self):
        """Transfer learn job runs without error."""
        with patch('predict.core.db.session.get_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = MagicMock(return_value=mock_context)
            
            # Mock TransferLearning
            with patch('predict.core.ai.transfer_learning.TransferLearning') as mock_transfer_class:
                mock_transfer = MagicMock()
                mock_transfer.fine_tune = AsyncMock(return_value={
                    "final_loss": 0.1,
                    "epochs_trained": 5,
                    "base_model_used": "/path/to/base.keras",
                })
                mock_transfer.base_model = MagicMock()
                mock_transfer.save_model_version = AsyncMock(return_value=123)
                mock_transfer_class.return_value = mock_transfer
                
                result = await transfer_learn_vehicle(1, "Toyota", "Camry")
                
                assert result["profile_id"] == 1
                assert result["status"] == "success"
                assert "model_version_id" in result
                assert "metrics" in result

    @pytest.mark.asyncio
    async def test_transfer_learn_vehicle_failure(self):
        """Transfer learn job handles errors gracefully."""
        with patch('predict.core.db.session.get_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = MagicMock(return_value=mock_context)
            
            # Mock TransferLearning to raise error
            with patch('predict.core.ai.transfer_learning.TransferLearning') as mock_transfer_class:
                mock_transfer = MagicMock()
                mock_transfer.fine_tune = AsyncMock(side_effect=Exception("Training failed"))
                mock_transfer_class.return_value = mock_transfer
                
                result = await transfer_learn_vehicle(1, "Toyota", "Camry")
                
                assert result["profile_id"] == 1
                assert result["status"] == "failed"
                assert "error" in result
