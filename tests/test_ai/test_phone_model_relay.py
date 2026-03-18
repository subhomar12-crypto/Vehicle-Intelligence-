"""Tests for phone model relay."""

import json
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from predict.core.ai.phone_model_relay import (
    PhoneModelRelay,
    BLEModelReceiver,
    ModelChunk,
    MODEL_TYPES,
    create_relay_from_config,
)


class TestPhoneModelRelay:
    """Test PhoneModelRelay."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.relay = PhoneModelRelay(
            server_url="https://api.predict.com",
            api_key="test_key_123",
            temp_dir=self.temp_dir,
        )

    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_model_types_defined(self):
        """MODEL_TYPES has expected values."""
        assert "health" in MODEL_TYPES
        assert "anomaly" in MODEL_TYPES
        assert "xgboost" in MODEL_TYPES

    def test_init(self):
        """Initialization stores parameters."""
        assert self.relay.server_url == "https://api.predict.com"
        assert self.relay.api_key == "test_key_123"
        assert Path(self.temp_dir).exists()

    def test_receive_chunk_success(self):
        """Successfully receive and store chunk."""
        data = b"test data"
        checksum = hashlib.md5(data).hexdigest()
        
        result = self.relay.receive_chunk(
            model_id="model_123",
            chunk_index=0,
            total_chunks=3,
            data=data,
            checksum=checksum,
        )
        
        assert result["status"] == "received"
        assert result["model_id"] == "model_123"
        assert result["received_chunks"] == 1
        assert result["total_chunks"] == 3
        assert result["complete"] is False

    def test_receive_chunk_checksum_mismatch(self):
        """Detect checksum mismatch."""
        data = b"test data"
        wrong_checksum = "wrong_checksum"
        
        result = self.relay.receive_chunk(
            model_id="model_123",
            chunk_index=0,
            total_chunks=3,
            data=data,
            checksum=wrong_checksum,
        )
        
        assert result["status"] == "error"
        assert "checksum" in result["message"].lower()

    def test_receive_all_chunks(self):
        """Receive all chunks completes transfer."""
        for i in range(3):
            data = f"chunk {i}".encode()
            checksum = hashlib.md5(data).hexdigest()
            
            result = self.relay.receive_chunk(
                model_id="model_123",
                chunk_index=i,
                total_chunks=3,
                data=data,
                checksum=checksum,
            )
            
            if i == 2:
                assert result["complete"] is True

    def test_is_transfer_complete(self):
        """Check transfer completion status."""
        # Initially not complete
        assert self.relay.is_transfer_complete("model_123") is False
        
        # Receive all chunks
        for i in range(2):
            data = f"chunk {i}".encode()
            checksum = hashlib.md5(data).hexdigest()
            self.relay.receive_chunk(
                model_id="model_123",
                chunk_index=i,
                total_chunks=2,
                data=data,
                checksum=checksum,
            )
        
        assert self.relay.is_transfer_complete("model_123") is True

    def test_assemble_model(self):
        """Assemble chunks into file."""
        # Receive chunks
        chunks_data = [b"Hello ", b"World", b"!"]
        for i, data in enumerate(chunks_data):
            checksum = hashlib.md5(data).hexdigest()
            self.relay.receive_chunk(
                model_id="model_123",
                chunk_index=i,
                total_chunks=3,
                data=data,
                checksum=checksum,
            )
        
        # Assemble
        model_path = self.relay.assemble_model("model_123")
        
        assert model_path is not None
        assert model_path.exists()
        assert model_path.read_bytes() == b"Hello World!"

    def test_assemble_model_incomplete(self):
        """Assemble returns None if incomplete."""
        result = self.relay.assemble_model("model_123")
        assert result is None

    @patch('requests.post')
    def test_upload_to_server_success(self, mock_post):
        """Successfully upload to server."""
        # Create test file
        test_file = Path(self.temp_dir) / "test_model.tflite"
        test_file.write_bytes(b"model data")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"model_id": "srv_123"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        result = self.relay.upload_to_server(
            model_path=test_file,
            vehicle_id=1,
            model_type="health",
        )
        
        assert result["status"] == "success"
        assert "server_response" in result

    @patch('requests.post')
    def test_upload_to_server_failure(self, mock_post):
        """Handle upload failure."""
        test_file = Path(self.temp_dir) / "test_model.tflite"
        test_file.write_bytes(b"model data")
        
        # Mock failed response
        mock_post.side_effect = Exception("Network error")
        
        result = self.relay.upload_to_server(
            model_path=test_file,
            vehicle_id=1,
            model_type="health",
        )
        
        assert result["status"] == "error"
        assert "message" in result

    def test_get_transfer_status_not_found(self):
        """Status for unknown model."""
        status = self.relay.get_transfer_status("unknown_model")
        
        assert status["status"] == "not_found"

    def test_get_transfer_status_in_progress(self):
        """Status during transfer."""
        # Receive first chunk
        data = b"chunk 0"
        checksum = hashlib.md5(data).hexdigest()
        self.relay.receive_chunk(
            model_id="model_123",
            chunk_index=0,
            total_chunks=3,
            data=data,
            checksum=checksum,
        )
        
        status = self.relay.get_transfer_status("model_123")
        
        assert status["status"] == "in_progress"
        assert status["received_chunks"] == 1
        assert status["total_chunks"] == 3
        assert status["progress_percent"] == pytest.approx(33.33, abs=0.01)
        assert 1 in status["missing_chunks"]  # Chunks 1 and 2 missing

    def test_cancel_transfer(self):
        """Cancel transfer cleans up."""
        # Receive chunk
        data = b"chunk 0"
        checksum = hashlib.md5(data).hexdigest()
        self.relay.receive_chunk(
            model_id="model_123",
            chunk_index=0,
            total_chunks=2,
            data=data,
            checksum=checksum,
        )
        
        # Cancel
        result = self.relay.cancel_transfer("model_123")
        
        assert result is True
        assert "model_123" not in self.relay._chunk_buffer

    def test_cancel_transfer_not_found(self):
        """Cancel unknown transfer returns False."""
        result = self.relay.cancel_transfer("unknown_model")
        assert result is False


class TestBLEModelReceiver:
    """Test BLEModelReceiver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.relay = PhoneModelRelay(
            server_url="https://api.predict.com",
            api_key="test_key",
            temp_dir=self.temp_dir,
        )
        self.receiver = BLEModelReceiver(self.relay)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Initialization stores relay."""
        assert self.receiver.relay == self.relay
        assert self.receiver._is_advertising is False

    def test_start_advertising(self):
        """Start advertising."""
        result = self.receiver.start_advertising("uuid-123")
        
        assert result is True
        assert self.receiver._is_advertising is True

    def test_stop_advertising(self):
        """Stop advertising."""
        self.receiver.start_advertising("uuid-123")
        self.receiver.stop_advertising()
        
        assert self.receiver._is_advertising is False

    def test_on_chunk_received(self):
        """BLE chunk received callback."""
        data = b"test chunk"
        checksum = hashlib.md5(data).hexdigest()
        
        result = self.receiver.on_chunk_received(
            model_id="model_123",
            chunk_index=0,
            total_chunks=2,
            data=data,
            checksum=checksum,
        )
        
        assert result["status"] == "received"

    @patch.object(PhoneModelRelay, 'relay_model')
    def test_on_transfer_complete(self, mock_relay):
        """BLE transfer complete callback."""
        mock_relay.return_value = {"status": "success"}
        
        result = self.receiver.on_transfer_complete(
            model_id="model_123",
            vehicle_id=1,
            model_type="health",
        )
        
        assert result["status"] == "success"
        mock_relay.assert_called_once_with("model_123", 1, "health")


class TestCreateRelayFromConfig:
    """Test create_relay_from_config."""

    def test_create_from_config(self):
        """Create relay from config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config = {
                "server_url": "https://test.api.com",
                "api_key": "secret_key",
                "temp_dir": tmpdir,
            }
            with open(config_path, 'w') as f:
                json.dump(config, f)
            
            relay = create_relay_from_config(str(config_path))
            
            assert relay.server_url == "https://test.api.com"
            assert relay.api_key == "secret_key"
