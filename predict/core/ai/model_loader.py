"""
AI/ML Model loader and registry.

Handles loading LSTM, XGBoost, and LLM models with versioning.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import pickle

import joblib

from predict.core.config import get_config

logger = logging.getLogger(__name__)

# Registry of loaded models
_model_cache: Dict[str, Any] = {}
_model_metadata: Dict[str, Dict[str, Any]] = {}


class ModelLoader:
    """Load and cache ML models."""
    
    def __init__(self):
        self.config = get_config()
        self.models_dir = self.config.MODELS_DIR
        self.gguf_dir = self.config.GGUF_DIR
    
    def load_sklearn_model(self, model_name: str) -> Optional[Any]:
        """
        Load scikit-learn/XGBoost model from joblib.
        
        Args:
            model_name: Name of the model file (without .joblib extension)
        
        Returns:
            Loaded model or None if not found
        """
        cache_key = f"sklearn:{model_name}"
        
        if cache_key in _model_cache:
            return _model_cache[cache_key]
        
        model_path = self.models_dir / f"{model_name}.joblib"
        
        if not model_path.exists():
            logger.warning(f"Model not found: {model_path}")
            return None
        
        try:
            model = joblib.load(model_path)
            _model_cache[cache_key] = model
            
            # Load metadata if available
            metadata_path = model_path.with_suffix('.json')
            if metadata_path.exists():
                with open(metadata_path) as f:
                    _model_metadata[cache_key] = json.load(f)
            
            logger.info(f"Loaded model: {model_name}")
            return model
        
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return None
    
    def load_pickle_model(self, model_name: str) -> Optional[Any]:
        """
        Load model from pickle file.
        
        Args:
            model_name: Name of the model file (without .pkl extension)
        
        Returns:
            Loaded model or None if not found
        """
        cache_key = f"pickle:{model_name}"
        
        if cache_key in _model_cache:
            return _model_cache[cache_key]
        
        model_path = self.models_dir / f"{model_name}.pkl"
        
        if not model_path.exists():
            logger.warning(f"Model not found: {model_path}")
            return None
        
        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            _model_cache[cache_key] = model
            logger.info(f"Loaded pickle model: {model_name}")
            return model
        
        except Exception as e:
            logger.error(f"Failed to load pickle model {model_name}: {e}")
            return None
    
    def get_llm_model_path(self, model_filename: str) -> Optional[Path]:
        """
        Get path to GGUF model file.
        
        Args:
            model_filename: Name of the .gguf file
        
        Returns:
            Path to model file or None if not found
        """
        model_path = self.gguf_dir / model_filename
        
        if model_path.exists():
            return model_path
        
        # Try to find any .gguf file if specific one not found
        if not model_filename.endswith('.gguf'):
            model_path = self.gguf_dir / f"{model_filename}.gguf"
            if model_path.exists():
                return model_path
        
        # List available models
        available = list(self.gguf_dir.glob("*.gguf"))
        if available:
            logger.warning(f"Model {model_filename} not found, available: {[m.name for m in available]}")
        else:
            logger.warning(f"No GGUF models found in {self.gguf_dir}")
        
        return None
    
    def list_available_models(self) -> Dict[str, list]:
        """
        List all available models in the models directory.
        
        Returns:
            Dict with model types and their files
        """
        models = {
            "sklearn": [],
            "pickle": [],
            "gguf": [],
        }
        
        if self.models_dir.exists():
            models["sklearn"] = [f.stem for f in self.models_dir.glob("*.joblib")]
            models["pickle"] = [f.stem for f in self.models_dir.glob("*.pkl")]
        
        if self.gguf_dir.exists():
            models["gguf"] = [f.name for f in self.gguf_dir.glob("*.gguf")]
        
        return models
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a loaded model.
        
        Args:
            model_name: Model identifier
        
        Returns:
            Model metadata dict or None
        """
        for key, metadata in _model_metadata.items():
            if model_name in key:
                return metadata
        return None
    
    def clear_cache(self) -> None:
        """Clear all cached models from memory."""
        global _model_cache
        _model_cache.clear()
        _model_metadata.clear()
        logger.info("Model cache cleared")
    
    def reload_model(self, model_name: str, loader_func: Callable) -> Optional[Any]:
        """
        Reload a model from disk, bypassing cache.
        
        Args:
            model_name: Name of the model
            loader_func: Function to load the model
        
        Returns:
            Reloaded model or None
        """
        # Remove from cache
        for key in list(_model_cache.keys()):
            if model_name in key:
                del _model_cache[key]
        
        # Reload
        return loader_func()


def get_model_loader() -> ModelLoader:
    """Get singleton ModelLoader instance."""
    return ModelLoader()


def get_cached_model(model_type: str, model_name: str) -> Optional[Any]:
    """
    Get a model from cache if available.
    
    Args:
        model_type: Type of model (sklearn, pickle, llm)
        model_name: Name of the model
    
    Returns:
        Cached model or None
    """
    cache_key = f"{model_type}:{model_name}"
    return _model_cache.get(cache_key)
