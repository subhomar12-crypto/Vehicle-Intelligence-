"""Tests for LSTM trainer."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
import tensorflow as tf

from predict.core.ai.lstm_trainer import LSTMTrainer, FEATURE_COLUMNS


class TestLSTMTrainer:
    """Test LSTMTrainer."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use smaller params for faster tests
        self.trainer = LSTMTrainer(
            window_size=10,
            lstm_units=16,
            epochs=2,
            batch_size=4,
        )

    def test_feature_columns_count(self):
        """FEATURE_COLUMNS has 15 entries."""
        assert len(FEATURE_COLUMNS) == 15

    def test_build_model(self):
        """Model builds correctly."""
        model = self.trainer.build_model()
        
        assert model is not None
        assert self.trainer.model is model
        
        # Check input shape
        assert model.input_shape == (None, 10, 15)
        
        # Check output shape
        assert model.output_shape == (None, 10, 15)

    @pytest.mark.asyncio
    async def test_train_from_profile_insufficient_data(self):
        """Training with insufficient data raises error."""
        # Mock session
        mock_session = AsyncMock()
        
        # Mock loader to return insufficient data
        from predict.core.ai import lstm_trainer as trainer_module
        original_loader = trainer_module.LSTMDataLoader
        
        mock_loader = MagicMock()
        mock_loader.load_from_db = AsyncMock(return_value=np.array([]))
        
        trainer_module.LSTMDataLoader = lambda: mock_loader
        
        try:
            with pytest.raises(ValueError, match="Insufficient data"):
                await self.trainer.train_from_profile(mock_session, profile_id=1)
        finally:
            trainer_module.LSTMDataLoader = original_loader

    def test_export_tflite_no_model(self):
        """Export without model raises error."""
        with pytest.raises(ValueError, match="No model to export"):
            self.trainer.export_tflite("/tmp/model.tflite")

    def test_export_tflite_success(self):
        """Model exports to TFLite successfully."""
        # Build minimal model
        self.trainer.build_model()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "model.tflite"
            
            result = self.trainer.export_tflite(str(output_path), quantization="float16")
            
            assert Path(result).exists()
            assert Path(result).stat().st_size > 0

    def test_save_normalization_params(self):
        """Normalization params save correctly."""
        mins = np.array([0.0] * 15)
        maxs = np.array([100.0] * 15)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "norm.json"
            
            result = self.trainer.save_normalization_params(str(output_path), mins, maxs)
            
            assert Path(result).exists()
            
            # Verify content
            with open(result, 'r') as f:
                data = json.load(f)
            
            assert data["feature_columns"] == FEATURE_COLUMNS
            assert data["mins"] == [0.0] * 15
            assert data["maxs"] == [100.0] * 15

    def test_predict_anomaly_score_no_model(self):
        """Prediction without model raises error."""
        sequence = np.random.randn(10, 15)
        
        with pytest.raises(ValueError, match="No model loaded"):
            self.trainer.predict_anomaly_score(sequence)

    def test_predict_anomaly_score_wrong_shape(self):
        """Prediction with wrong shape raises error."""
        # Build model
        self.trainer.build_model()
        
        # Wrong shape
        sequence = np.random.randn(5, 15)  # window_size should be 10
        
        with pytest.raises(ValueError, match="Expected shape"):
            self.trainer.predict_anomaly_score(sequence)

    def test_predict_anomaly_score_success(self):
        """Prediction returns anomaly score."""
        # Build and predict with minimal model
        self.trainer.build_model()
        
        sequence = np.random.randn(10, 15).astype(np.float32)
        
        score = self.trainer.predict_anomaly_score(sequence)
        
        assert isinstance(score, float)
        assert score >= 0  # Reconstruction error is always positive

    def test_is_anomaly_no_threshold(self):
        """Anomaly detection without threshold returns False."""
        self.trainer.build_model()
        
        sequence = np.random.randn(10, 15).astype(np.float32)
        
        is_anom, score = self.trainer.is_anomaly(sequence)
        
        assert is_anom is False  # No threshold set
        assert isinstance(score, float)

    def test_is_anomaly_with_threshold(self):
        """Anomaly detection with threshold works."""
        self.trainer.build_model()
        self.trainer.threshold = 0.5
        
        sequence = np.random.randn(10, 15).astype(np.float32)
        
        is_anom, score = self.trainer.is_anomaly(sequence)
        
        # Score should be returned, is_anom depends on score vs threshold
        assert isinstance(is_anom, bool)
        assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_train_from_profile_success(self):
        """Successful training from profile data."""
        # Create sufficient mock data
        np.random.seed(42)
        mock_data = np.random.randn(100, 15).astype(np.float32) * 50 + 50
        
        # Mock the loader
        from predict.core.ai import lstm_trainer as trainer_module
        original_loader_class = trainer_module.LSTMDataLoader
        
        mock_loader_instance = MagicMock()
        mock_loader_instance.load_from_db = AsyncMock(return_value=mock_data)
        mock_loader_instance.normalize = MagicMock(return_value=(mock_data, None, None))
        
        # Create sequences (90, 10, 15)
        sequences = np.array([
            mock_data[i:i+10] for i in range(90)
        ])
        mock_loader_instance.create_sequences = MagicMock(return_value=sequences)
        
        trainer_module.LSTMDataLoader = lambda: mock_loader_instance
        
        mock_session = AsyncMock()
        
        try:
            metrics = await self.trainer.train_from_profile(
                mock_session, profile_id=1
            )
            
            assert "final_loss" in metrics
            assert "final_val_loss" in metrics
            assert "epochs_trained" in metrics
            assert "threshold" in metrics
            assert "train_sequences" in metrics
            assert "val_sequences" in metrics
            
            assert metrics["train_sequences"] > 0
            assert metrics["val_sequences"] > 0
            assert self.trainer.model is not None
            assert self.trainer.threshold is not None
            
        finally:
            trainer_module.LSTMDataLoader = original_loader_class

    def test_model_autoencoder_behavior(self):
        """Model reconstructs input (autoencoder behavior)."""
        trainer = LSTMTrainer(window_size=10, lstm_units=8, epochs=1, batch_size=2)
        trainer.build_model()
        
        # Create simple training data
        train_data = np.random.randn(20, 10, 15).astype(np.float32)
        
        # Quick training
        trainer.model.fit(train_data, train_data, epochs=1, verbose=0)
        
        # Test reconstruction
        test_seq = train_data[0:1]  # Single sequence with batch dim
        reconstructed = trainer.model.predict(test_seq, verbose=0)
        
        assert reconstructed.shape == test_seq.shape
        
        # After training, reconstruction should be somewhat close
        mse = np.mean((test_seq - reconstructed) ** 2)
        assert mse < 100  # Loose bound - just checking it runs

    def test_export_quantization_options(self):
        """Both quantization options work."""
        self.trainer.build_model()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test float16
            path16 = Path(tmpdir) / "model_f16.tflite"
            result16 = self.trainer.export_tflite(str(path16), quantization="float16")
            assert Path(result16).exists()
            
            # Test int8 (dynamic range)
            path8 = Path(tmpdir) / "model_int8.tflite"
            result8 = self.trainer.export_tflite(str(path8), quantization="int8")
            assert Path(result8).exists()
