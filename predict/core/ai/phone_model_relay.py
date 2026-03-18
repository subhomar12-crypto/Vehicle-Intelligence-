"""Phone Model Relay — BLE to HTTP bridge for model relay from Pi5 to server.

Receives models via BLE from Raspberry Pi 5 and relays them to the server via HTTP.
Handles chunked BLE transfers and reassembles model files.
"""

import hashlib
import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# Model types that can be relayed
MODEL_TYPES = ["health", "anomaly", "context", "xgboost", "survival"]


@dataclass
class ModelChunk:
    """A chunk of model data received via BLE."""
    chunk_index: int
    total_chunks: int
    data: bytes
    checksum: str


class PhoneModelRelay:
    """Relay models from Pi5 to server via HTTP."""
    
    def __init__(
        self,
        server_url: str,
        api_key: str,
        temp_dir: str = "/tmp/model_relay",
    ):
        """Initialize relay.
        
        Args:
            server_url: Server URL for model upload
            api_key: API key for authentication
            temp_dir: Temporary directory for assembling chunks
        """
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Storage for chunks during transfer
        self._chunk_buffer: Dict[str, List[Optional[bytes]]] = {}
        self._chunk_metadata: Dict[str, Dict[str, Any]] = {}
    
    def receive_chunk(
        self,
        model_id: str,
        chunk_index: int,
        total_chunks: int,
        data: bytes,
        checksum: str,
    ) -> Dict[str, Any]:
        """Receive a chunk of model data via BLE.
        
        Args:
            model_id: Unique model identifier
            chunk_index: Index of this chunk (0-based)
            total_chunks: Total number of chunks
            data: Chunk data bytes
            checksum: MD5 checksum of chunk
            
        Returns:
            Status dict
        """
        # Verify chunk checksum
        actual_checksum = hashlib.md5(data).hexdigest()
        if actual_checksum != checksum:
            return {
                "status": "error",
                "message": f"Checksum mismatch for chunk {chunk_index}",
                "received": checksum,
                "actual": actual_checksum,
            }
        
        # Initialize buffer for new model
        if model_id not in self._chunk_buffer:
            self._chunk_buffer[model_id] = [None] * total_chunks
            self._chunk_metadata[model_id] = {
                "total_chunks": total_chunks,
                "received_chunks": 0,
                "start_time": datetime.utcnow().isoformat(),
            }
        
        # Store chunk
        self._chunk_buffer[model_id][chunk_index] = data
        self._chunk_metadata[model_id]["received_chunks"] += 1
        
        received = self._chunk_metadata[model_id]["received_chunks"]
        total = total_chunks
        
        logger.info(f"Received chunk {chunk_index + 1}/{total} for model {model_id}")
        
        return {
            "status": "received",
            "model_id": model_id,
            "chunk_index": chunk_index,
            "received_chunks": received,
            "total_chunks": total,
            "complete": received == total,
        }
    
    def is_transfer_complete(self, model_id: str) -> bool:
        """Check if all chunks received for a model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if complete
        """
        if model_id not in self._chunk_buffer:
            return False
        
        chunks = self._chunk_buffer[model_id]
        return all(chunk is not None for chunk in chunks)
    
    def assemble_model(self, model_id: str) -> Optional[Path]:
        """Assemble chunks into complete model file.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Path to assembled file, or None if incomplete
        """
        if not self.is_transfer_complete(model_id):
            return None
        
        chunks = self._chunk_buffer[model_id]
        
        # Assemble file
        model_path = self.temp_dir / f"{model_id}.tflite"
        
        with open(model_path, 'wb') as f:
            for chunk in chunks:
                f.write(chunk)
        
        logger.info(f"Assembled model {model_id} at {model_path}")
        
        return model_path
    
    def upload_to_server(
        self,
        model_path: Path,
        vehicle_id: int,
        model_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upload assembled model to server.
        
        Args:
            model_path: Path to model file
            vehicle_id: Vehicle ID
            model_type: Type of model
            metadata: Optional metadata dict
            
        Returns:
            Server response
        """
        url = f"{self.server_url}/api/v1/models/upload"
        
        data = {
            'vehicle_id': str(vehicle_id),
            'model_type': model_type,
            'metadata': json.dumps(metadata or {}),
        }
        
        headers = {
            'X-API-Key': self.api_key,
        }
        
        try:
            with open(model_path, 'rb') as f:
                files = {
                    'model_file': (model_path.name, f, 'application/octet-stream'),
                }
                
                response = requests.post(
                    url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=60,
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Successfully uploaded model for vehicle {vehicle_id}")
                
                return {
                    "status": "success",
                    "server_response": result,
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to upload model: {e}")
            return {
                "status": "error",
                "message": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error uploading model: {e}")
            return {
                "status": "error",
                "message": str(e),
            }
    
    def relay_model(
        self,
        model_id: str,
        vehicle_id: int,
        model_type: str,
    ) -> Dict[str, Any]:
        """Complete relay: assemble and upload.
        
        Args:
            model_id: Model identifier
            vehicle_id: Vehicle ID
            model_type: Type of model
            
        Returns:
            Result dict
        """
        # Assemble model
        model_path = self.assemble_model(model_id)
        if not model_path:
            return {
                "status": "error",
                "message": f"Model {model_id} not complete",
            }
        
        # Get metadata
        metadata = self._chunk_metadata.get(model_id, {})
        
        # Upload
        result = self.upload_to_server(model_path, vehicle_id, model_type, metadata)
        
        # Cleanup
        self._cleanup(model_id)
        
        return result
    
    def _cleanup(self, model_id: str) -> None:
        """Clean up chunks and assembled file for a model.
        
        Args:
            model_id: Model identifier
        """
        # Remove from buffer
        if model_id in self._chunk_buffer:
            del self._chunk_buffer[model_id]
        
        if model_id in self._chunk_metadata:
            del self._chunk_metadata[model_id]
        
        # Remove assembled file
        model_path = self.temp_dir / f"{model_id}.tflite"
        if model_path.exists():
            model_path.unlink()
        
        logger.debug(f"Cleaned up model {model_id}")
    
    def get_transfer_status(self, model_id: str) -> Dict[str, Any]:
        """Get transfer status for a model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Status dict
        """
        if model_id not in self._chunk_buffer:
            return {
                "status": "not_found",
                "model_id": model_id,
            }
        
        metadata = self._chunk_metadata[model_id]
        chunks = self._chunk_buffer[model_id]
        
        received = metadata["received_chunks"]
        total = metadata["total_chunks"]
        missing = [i for i, chunk in enumerate(chunks) if chunk is None]
        
        return {
            "status": "complete" if self.is_transfer_complete(model_id) else "in_progress",
            "model_id": model_id,
            "received_chunks": received,
            "total_chunks": total,
            "progress_percent": (received / total) * 100,
            "missing_chunks": missing,
            "start_time": metadata.get("start_time"),
        }
    
    def cancel_transfer(self, model_id: str) -> bool:
        """Cancel and cleanup an in-progress transfer.
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if cancelled
        """
        if model_id not in self._chunk_buffer:
            return False
        
        self._cleanup(model_id)
        logger.info(f"Cancelled transfer for model {model_id}")
        
        return True


class BLEModelReceiver:
    """BLE receiver for model chunks from Pi5.
    
    This class handles the BLE peripheral role and receives
    model chunks from the Pi5 acting as BLE central.
    """
    
    def __init__(self, relay: PhoneModelRelay):
        """Initialize BLE receiver.
        
        Args:
            relay: PhoneModelRelay instance
        """
        self.relay = relay
        self._is_advertising = False
        
    def start_advertising(self, service_uuid: str) -> bool:
        """Start BLE advertising for Pi5 to connect.
        
        Args:
            service_uuid: BLE service UUID
            
        Returns:
            True if started
        """
        # This is a placeholder - actual implementation would use
        # a BLE library like bleak or native Android BLE APIs
        logger.info(f"Started BLE advertising with UUID {service_uuid}")
        self._is_advertising = True
        return True
    
    def stop_advertising(self) -> None:
        """Stop BLE advertising."""
        logger.info("Stopped BLE advertising")
        self._is_advertising = False
    
    def on_chunk_received(
        self,
        model_id: str,
        chunk_index: int,
        total_chunks: int,
        data: bytes,
        checksum: str,
    ) -> Dict[str, Any]:
        """Callback when BLE chunk received.
        
        Args:
            model_id: Model identifier
            chunk_index: Chunk index
            total_chunks: Total chunks
            data: Chunk data
            checksum: Chunk checksum
            
        Returns:
            Status dict
        """
        return self.relay.receive_chunk(
            model_id, chunk_index, total_chunks, data, checksum
        )
    
    def on_transfer_complete(
        self,
        model_id: str,
        vehicle_id: int,
        model_type: str,
    ) -> Dict[str, Any]:
        """Callback when BLE transfer complete.
        
        Args:
            model_id: Model identifier
            vehicle_id: Vehicle ID
            model_type: Model type
            
        Returns:
            Result dict
        """
        return self.relay.relay_model(model_id, vehicle_id, model_type)


def create_relay_from_config(config_path: str) -> PhoneModelRelay:
    """Create relay from config file.
    
    Args:
        config_path: Path to JSON config file
        
    Returns:
        PhoneModelRelay instance
    """
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return PhoneModelRelay(
        server_url=config["server_url"],
        api_key=config["api_key"],
        temp_dir=config.get("temp_dir", "/tmp/model_relay"),
    )
