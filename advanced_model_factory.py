"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Advanced AI Model Factory & Pipeline Manager

Advanced AI Model Factory & Pipeline Manager
===========================================

Factory pattern implementation for managing multiple AI architectures
with unified interfaces, automatic model selection, and ensemble methods.

Architecture Overview:
```
Model Requests -> Factory -> Model Selection -> Ensemble Pipeline -> Prediction
       |              |            |                |                |
   User Needs    Architecture    Performance     Model Fusion    Final Output
   Constraints   Instantiation   Optimization   Confidence       Unified API
   Performance   Configuration  Auto-tuning    Weighting        Results
```

Key Features:
- Factory pattern for model instantiation
- Automatic model selection based on use case
- Ensemble methods for improved accuracy
- Performance monitoring and optimization
- Unified prediction API across all architectures
- Model versioning and rollback capabilities
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Union, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path
from abc import ABC, abstractmethod

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class ModelArchitecture(Enum):
    """Available AI model architectures."""
    LSTM_BASELINE = "lstm_baseline"
    CNN_LSTM_HYBRID = "cnn_lstm_hybrid"
    ATTENTION_LSTM = "attention_lstm"
    LSTM_AUTOENCODER = "lstm_autoencoder"
    ENSEMBLE = "ensemble"


class PredictionTask(Enum):
    """Types of prediction tasks."""
    FAILURE_PREDICTION = "failure_prediction"
    ANOMALY_DETECTION = "anomaly_detection"
    RUL_ESTIMATION = "rul_estimation"
    HEALTH_ASSESSMENT = "health_assessment"


@dataclass
class ModelCapabilities:
    """Capabilities and characteristics of a model."""
    architecture: ModelArchitecture
    supported_tasks: List[PredictionTask]
    requires_training: bool
    supports_incremental: bool
    typical_accuracy: float
    training_time_minutes: int
    memory_mb: int
    latency_ms: int
    physics_aware: bool
    attention_mechanism: bool


@dataclass
class ModelPerformance:
    """Performance metrics for a model."""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    latency_ms: float
    memory_usage_mb: float
    last_updated: str
    sample_count: int


@dataclass
class EnsembleWeights:
    """Weights for ensemble model combination."""
    lstm_baseline: float = 0.2
    cnn_lstm_hybrid: float = 0.3
    attention_lstm: float = 0.4
    lstm_autoencoder: float = 0.1

    def normalize(self):
        """Normalize weights to sum to 1.0."""
        total = sum([self.lstm_baseline, self.cnn_lstm_hybrid,
                    self.attention_lstm, self.lstm_autoencoder])
        if total > 0:
            self.lstm_baseline /= total
            self.cnn_lstm_hybrid /= total
            self.attention_lstm /= total
            self.lstm_autoencoder /= total


@dataclass
class PredictionRequest:
    """Request for model prediction."""
    task: PredictionTask
    obd_data: List[Dict[str, Any]]
    vehicle_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    preferred_architectures: Optional[List[ModelArchitecture]] = None
    require_confidence: bool = True
    allow_fallback: bool = True


@dataclass
class PredictionResult:
    """Unified prediction result from any model."""
    success: bool
    prediction: Any  # Model-specific prediction object
    architecture_used: ModelArchitecture
    confidence: float
    processing_time_ms: float
    model_version: str
    timestamp: str
    error_message: Optional[str] = None


class BaseModelWrapper(ABC):
    """Abstract base class for model wrappers."""

    def __init__(self, architecture: ModelArchitecture, config: Any = None):
        self.architecture = architecture
        self.config = config
        self.is_trained = False
        self.model_version = "0.0.0"
        self.performance = ModelPerformance(0, 0, 0, 0, 0, 0, "", 0)

    @abstractmethod
    def predict(self, obd_data: List[Dict]) -> Any:
        """Make a prediction."""
        pass

    @abstractmethod
    def train(self, training_data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Train the model."""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        pass

    def is_available(self) -> bool:
        """Check if model is available for predictions."""
        return self.is_trained

    def get_capabilities(self) -> ModelCapabilities:
        """Get model capabilities."""
        # Default implementation - override in subclasses
        return ModelCapabilities(
            architecture=self.architecture,
            supported_tasks=[PredictionTask.FAILURE_PREDICTION],
            requires_training=True,
            supports_incremental=False,
            typical_accuracy=0.7,
            training_time_minutes=30,
            memory_mb=500,
            latency_ms=100,
            physics_aware=False,
            attention_mechanism=False
        )


class LSTMModelWrapper(BaseModelWrapper):
    """Wrapper for baseline LSTM model."""

    def __init__(self, config=None):
        super().__init__(ModelArchitecture.LSTM_BASELINE, config)
        self.model = None

        # Lazy import to avoid circular dependencies
        try:
            from lstm_predictor import get_lstm_predictor
            self.model = get_lstm_predictor()
            self.is_trained = self.model.is_trained
        except ImportError:
            logger.warning("LSTM predictor not available")

    def predict(self, obd_data: List[Dict]) -> Any:
        if not self.model:
            return None
        return self.model.predict(obd_data)

    def train(self, training_data: List[Dict], **kwargs) -> Dict[str, Any]:
        if not self.model:
            return {'error': 'Model not available'}
        return self.model.train(training_data, **kwargs)

    def get_model_info(self) -> Dict[str, Any]:
        if not self.model:
            return {'error': 'Model not available'}
        return self.model.get_model_info()

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            architecture=ModelArchitecture.LSTM_BASELINE,
            supported_tasks=[PredictionTask.FAILURE_PREDICTION, PredictionTask.RUL_ESTIMATION],
            requires_training=True,
            supports_incremental=False,
            typical_accuracy=0.75,
            training_time_minutes=20,
            memory_mb=300,
            latency_ms=50,
            physics_aware=False,
            attention_mechanism=False
        )


class CNNLSTMModelWrapper(BaseModelWrapper):
    """Wrapper for CNN-LSTM hybrid model."""

    def __init__(self, config=None):
        super().__init__(ModelArchitecture.CNN_LSTM_HYBRID, config)
        self.model = None

        try:
            from cnn_lstm_model import get_cnn_lstm_model
            self.model = get_cnn_lstm_model()
            self.is_trained = self.model.is_trained
        except ImportError:
            logger.warning("CNN-LSTM model not available")

    def predict(self, obd_data: List[Dict]) -> Any:
        if not self.model:
            return None
        return self.model.predict(obd_data)

    def train(self, training_data: List[Dict], **kwargs) -> Dict[str, Any]:
        if not self.model:
            return {'error': 'Model not available'}
        return self.model.train(training_data, **kwargs)

    def get_model_info(self) -> Dict[str, Any]:
        if not self.model:
            return {'error': 'Model not available'}
        return self.model.get_model_info()

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            architecture=ModelArchitecture.CNN_LSTM_HYBRID,
            supported_tasks=[PredictionTask.FAILURE_PREDICTION, PredictionTask.HEALTH_ASSESSMENT],
            requires_training=True,
            supports_incremental=False,
            typical_accuracy=0.82,
            training_time_minutes=45,
            memory_mb=800,
            latency_ms=80,
            physics_aware=True,
            attention_mechanism=False
        )


class AttentionLSTMModelWrapper(BaseModelWrapper):
    """Wrapper for Attention-LSTM model."""

    def __init__(self, config=None):
        super().__init__(ModelArchitecture.ATTENTION_LSTM, config)
        self.model = None

        try:
            from attention_lstm_model import get_attention_lstm_model
            self.model = get_attention_lstm_model()
            self.is_trained = self.model.is_trained
        except ImportError:
            logger.warning("Attention-LSTM model not available")

    def predict(self, obd_data: List[Dict]) -> Any:
        if not self.model:
            return None
        return self.model.predict(obd_data)

    def train(self, training_data: List[Dict], **kwargs) -> Dict[str, Any]:
        if not self.model:
            return {'error': 'Model not available'}
        return self.model.train(training_data, **kwargs)

    def get_model_info(self) -> Dict[str, Any]:
        if not self.model:
            return {'error': 'Model not available'}
        return self.model.get_model_info()

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            architecture=ModelArchitecture.ATTENTION_LSTM,
            supported_tasks=[PredictionTask.FAILURE_PREDICTION, PredictionTask.HEALTH_ASSESSMENT],
            requires_training=True,
            supports_incremental=True,
            typical_accuracy=0.85,
            training_time_minutes=60,
            memory_mb=1000,
            latency_ms=120,
            physics_aware=True,
            attention_mechanism=True
        )


class LSTMAutoencoderWrapper(BaseModelWrapper):
    """Wrapper for LSTM Autoencoder."""

    def __init__(self, config=None):
        super().__init__(ModelArchitecture.LSTM_AUTOENCODER, config)
        self.model = None

        try:
            from lstm_autoencoder import get_lstm_autoencoder
            self.model = get_lstm_autoencoder()
            self.is_trained = self.model.is_trained
        except ImportError:
            logger.warning("LSTM Autoencoder not available")

    def predict(self, obd_data: List[Dict]) -> Any:
        if not self.model:
            return None
        return self.model.detect_anomalies(obd_data)

    def train(self, training_data: List[List[Dict]], **kwargs) -> Dict[str, Any]:
        if not self.model:
            return {'error': 'Model not available'}
        return self.model.train(training_data, **kwargs)

    def get_model_info(self) -> Dict[str, Any]:
        if not self.model:
            return {'error': 'Model not available'}
        return self.model.get_model_info()

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            architecture=ModelArchitecture.LSTM_AUTOENCODER,
            supported_tasks=[PredictionTask.ANOMALY_DETECTION],
            requires_training=True,
            supports_incremental=True,
            typical_accuracy=0.78,
            training_time_minutes=35,
            memory_mb=600,
            latency_ms=70,
            physics_aware=False,
            attention_mechanism=False
        )


class EnsembleModelWrapper(BaseModelWrapper):
    """Ensemble model combining multiple architectures."""

    def __init__(self, config=None):
        super().__init__(ModelArchitecture.ENSEMBLE, config)
        self.models = {}
        self.weights = EnsembleWeights()
        self.weights.normalize()

        # Initialize all component models
        self._init_component_models()

    def _init_component_models(self):
        """Initialize all component models."""
        self.models = {
            ModelArchitecture.LSTM_BASELINE: LSTMModelWrapper(),
            ModelArchitecture.CNN_LSTM_HYBRID: CNNLSTMModelWrapper(),
            ModelArchitecture.ATTENTION_LSTM: AttentionLSTMModelWrapper(),
            ModelArchitecture.LSTM_AUTOENCODER: LSTMAutoencoderWrapper()
        }

    def predict(self, obd_data: List[Dict]) -> Dict[str, Any]:
        """Make ensemble prediction."""
        predictions = {}
        weights_used = {}

        # Get predictions from all available models
        for arch, model in self.models.items():
            if model.is_available():
                try:
                    pred = model.predict(obd_data)
                    if pred is not None:
                        predictions[arch] = pred
                        weights_used[arch] = getattr(self.weights, arch.value.replace('_', '').lower(), 0.0)
                except Exception as e:
                    logger.warning(f"Ensemble prediction failed for {arch.value}: {e}")

        if not predictions:
            return {'error': 'No models available for ensemble prediction'}

        # Ensemble different prediction types
        return self._ensemble_predictions(predictions, weights_used)

    def _ensemble_predictions(self, predictions: Dict[ModelArchitecture, Any],
                            weights: Dict[ModelArchitecture, float]) -> Dict[str, Any]:
        """Combine predictions from multiple models."""

        # Handle failure prediction ensemble
        failure_predictions = []
        failure_weights = []

        for arch, pred in predictions.items():
            if arch != ModelArchitecture.LSTM_AUTOENCODER:  # Skip autoencoder for failure pred
                if hasattr(pred, 'failure_probability'):
                    failure_predictions.append(pred.failure_probability)
                    failure_weights.append(weights.get(arch, 0.0))

        # Weighted average for failure probability
        if failure_predictions and failure_weights:
            total_weight = sum(failure_weights)
            if total_weight > 0:
                ensemble_failure_prob = sum(p * w for p, w in zip(failure_predictions, failure_weights)) / total_weight
            else:
                ensemble_failure_prob = sum(failure_predictions) / len(failure_predictions)
        else:
            ensemble_failure_prob = 0.5

        # Get anomaly detection from autoencoder
        anomaly_result = predictions.get(ModelArchitecture.LSTM_AUTOENCODER)

        # Determine overall assessment
        anomaly_detected = anomaly_result.anomaly_detected if anomaly_result else False
        anomaly_score = anomaly_result.anomaly_score if anomaly_result else 0.0

        # Combined confidence
        base_confidence = 1 - abs(ensemble_failure_prob - 0.5) * 2  # Higher confidence away from 0.5
        anomaly_boost = anomaly_score * 0.3 if anomaly_detected else 0.0
        ensemble_confidence = min(1.0, base_confidence + anomaly_boost)

        return {
            'ensemble_failure_probability': round(ensemble_failure_prob, 3),
            'anomaly_detected': anomaly_detected,
            'anomaly_score': round(anomaly_score, 3),
            'ensemble_confidence': round(ensemble_confidence, 3),
            'models_used': len(predictions),
            'component_predictions': {
                arch.value: self._serialize_prediction(pred) for arch, pred in predictions.items()
            }
        }

    def _serialize_prediction(self, prediction: Any) -> Dict[str, Any]:
        """Serialize prediction for JSON compatibility."""
        if hasattr(prediction, '__dict__'):
            return {k: v for k, v in prediction.__dict__.items() if not k.startswith('_')}
        elif isinstance(prediction, dict):
            return prediction
        else:
            return str(prediction)

    def train(self, training_data: List[Dict], **kwargs) -> Dict[str, Any]:
        """Train ensemble (trains all component models)."""
        results = {}

        for arch, model in self.models.items():
            try:
                logger.info(f"Training ensemble component: {arch.value}")
                if arch == ModelArchitecture.LSTM_AUTOENCODER:
                    # Autoencoder needs sequences
                    sequences = [item.get('sequence', [item]) for item in training_data]
                    result = model.train(sequences, **kwargs)
                else:
                    result = model.train(training_data, **kwargs)

                results[arch.value] = result

                if result.get('success'):
                    logger.info(f"✅ {arch.value} training completed")
                else:
                    logger.warning(f"⚠️ {arch.value} training failed: {result.get('error')}")

            except Exception as e:
                logger.error(f"Ensemble training failed for {arch.value}: {e}")
                results[arch.value] = {'error': str(e)}

        # Update ensemble availability
        self.is_trained = any(model.is_trained for model in self.models.values())

        return {
            'success': self.is_trained,
            'component_results': results,
            'models_trained': sum(1 for r in results.values() if not r.get('error'))
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Get ensemble model information."""
        component_info = {}
        for arch, model in self.models.items():
            component_info[arch.value] = model.get_model_info()

        return {
            'architecture': 'ensemble',
            'components': component_info,
            'weights': {
                'lstm_baseline': self.weights.lstm_baseline,
                'cnn_lstm_hybrid': self.weights.cnn_lstm_hybrid,
                'attention_lstm': self.weights.attention_lstm,
                'lstm_autoencoder': self.weights.lstm_autoencoder
            },
            'is_trained': self.is_trained,
            'available_components': sum(1 for m in self.models.values() if m.is_available())
        }

    def get_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            architecture=ModelArchitecture.ENSEMBLE,
            supported_tasks=[PredictionTask.FAILURE_PREDICTION, PredictionTask.ANOMALY_DETECTION,
                           PredictionTask.HEALTH_ASSESSMENT],
            requires_training=True,
            supports_incremental=True,
            typical_accuracy=0.88,
            training_time_minutes=120,
            memory_mb=2000,
            latency_ms=200,
            physics_aware=True,
            attention_mechanism=True
        )


class AdvancedModelFactory:
    """
    Factory for creating and managing AI model instances.

    Provides unified interface for model selection, instantiation,
    and performance optimization.
    """

    def __init__(self):
        self.model_classes = {
            ModelArchitecture.LSTM_BASELINE: LSTMModelWrapper,
            ModelArchitecture.CNN_LSTM_HYBRID: CNNLSTMModelWrapper,
            ModelArchitecture.ATTENTION_LSTM: AttentionLSTMModelWrapper,
            ModelArchitecture.LSTM_AUTOENCODER: LSTMAutoencoderWrapper,
            ModelArchitecture.ENSEMBLE: EnsembleModelWrapper
        }

        self.active_models = {}
        self.performance_history = {}

        # Auto-select best model for each task
        self.task_model_mapping = {
            PredictionTask.FAILURE_PREDICTION: ModelArchitecture.ATTENTION_LSTM,
            PredictionTask.ANOMALY_DETECTION: ModelArchitecture.LSTM_AUTOENCODER,
            PredictionTask.RUL_ESTIMATION: ModelArchitecture.LSTM_BASELINE,
            PredictionTask.HEALTH_ASSESSMENT: ModelArchitecture.ENSEMBLE
        }

        logger.info("Advanced Model Factory initialized")

    def get_model(self, architecture: ModelArchitecture, config: Any = None) -> Optional[BaseModelWrapper]:
        """Get or create a model instance."""
        if architecture not in self.active_models:
            if architecture in self.model_classes:
                try:
                    model_class = self.model_classes[architecture]
                    self.active_models[architecture] = model_class(config)
                    logger.info(f"Created model instance: {architecture.value}")
                except Exception as e:
                    logger.error(f"Failed to create model {architecture.value}: {e}")
                    return None
            else:
                logger.error(f"Unknown architecture: {architecture}")
                return None

        return self.active_models[architecture]

    def predict(self, request: PredictionRequest) -> PredictionResult:
        """Make a prediction using the best available model."""
        import time
        start_time = time.time()

        # Select architecture
        architecture = self._select_architecture(request)

        if not architecture:
            return PredictionResult(
                success=False,
                prediction=None,
                architecture_used=ModelArchitecture.LSTM_BASELINE,
                confidence=0.0,
                processing_time_ms=(time.time() - start_time) * 1000,
                model_version="0.0.0",
                timestamp=datetime.now().isoformat(),
                error_message="No suitable model available"
            )

        # Get model
        model = self.get_model(architecture)
        if not model or not model.is_available():
            # Try fallback if allowed
            if request.allow_fallback:
                fallback_arch = self._get_fallback_architecture(request.task)
                if fallback_arch and fallback_arch != architecture:
                    model = self.get_model(fallback_arch)
                    architecture = fallback_arch

        if not model or not model.is_available():
            return PredictionResult(
                success=False,
                prediction=None,
                architecture_used=architecture,
                confidence=0.0,
                processing_time_ms=(time.time() - start_time) * 1000,
                model_version="0.0.0",
                timestamp=datetime.now().isoformat(),
                error_message="Model not available"
            )

        # Make prediction
        try:
            prediction = model.predict(request.obd_data)

            # Calculate confidence
            confidence = self._calculate_prediction_confidence(prediction, model)

            processing_time = (time.time() - start_time) * 1000

            return PredictionResult(
                success=True,
                prediction=prediction,
                architecture_used=architecture,
                confidence=confidence,
                processing_time_ms=processing_time,
                model_version=model.model_version,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"Prediction failed for {architecture.value}: {e}")
            return PredictionResult(
                success=False,
                prediction=None,
                architecture_used=architecture,
                confidence=0.0,
                processing_time_ms=(time.time() - start_time) * 1000,
                model_version=model.model_version,
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )

    def _select_architecture(self, request: PredictionRequest) -> Optional[ModelArchitecture]:
        """Select the best architecture for the request."""

        # Check preferred architectures first
        if request.preferred_architectures:
            for arch in request.preferred_architectures:
                model = self.get_model(arch)
                if model and model.is_available():
                    return arch

        # Use task-based default
        default_arch = self.task_model_mapping.get(request.task)
        if default_arch:
            model = self.get_model(default_arch)
            if model and model.is_available():
                return default_arch

        # Find any available model for the task
        for arch, model in self.active_models.items():
            if model and model.is_available():
                capabilities = model.get_capabilities()
                if request.task in capabilities.supported_tasks:
                    return arch

        # Last resort: try to create the default model
        if default_arch:
            model = self.get_model(default_arch)
            if model:
                return default_arch

        return None

    def _get_fallback_architecture(self, task: PredictionTask) -> Optional[ModelArchitecture]:
        """Get fallback architecture for a task."""
        fallbacks = {
            PredictionTask.FAILURE_PREDICTION: ModelArchitecture.LSTM_BASELINE,
            PredictionTask.ANOMALY_DETECTION: ModelArchitecture.LSTM_BASELINE,
            PredictionTask.RUL_ESTIMATION: ModelArchitecture.LSTM_BASELINE,
            PredictionTask.HEALTH_ASSESSMENT: ModelArchitecture.LSTM_BASELINE
        }
        return fallbacks.get(task)

    def _calculate_prediction_confidence(self, prediction: Any, model: BaseModelWrapper) -> float:
        """Calculate confidence in the prediction."""
        # Base confidence from model capabilities
        capabilities = model.get_capabilities()
        base_confidence = capabilities.typical_accuracy

        # Adjust based on prediction characteristics
        if hasattr(prediction, 'confidence'):
            prediction_confidence = prediction.confidence
        elif isinstance(prediction, dict) and 'confidence' in prediction:
            prediction_confidence = prediction['confidence']
        else:
            prediction_confidence = 0.5

        # Combine model and prediction confidence
        combined_confidence = (base_confidence * 0.6) + (prediction_confidence * 0.4)

        return min(1.0, combined_confidence)

    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all available models."""
        available = {}

        for arch in ModelArchitecture:
            model = self.get_model(arch)
            if model:
                capabilities = model.get_capabilities()
                available[arch.value] = {
                    'available': model.is_available(),
                    'capabilities': {
                        'supported_tasks': [t.value for t in capabilities.supported_tasks],
                        'requires_training': capabilities.requires_training,
                        'typical_accuracy': capabilities.typical_accuracy,
                        'physics_aware': capabilities.physics_aware,
                        'attention_mechanism': capabilities.attention_mechanism
                    },
                    'performance': {
                        'latency_ms': capabilities.latency_ms,
                        'memory_mb': capabilities.memory_mb,
                        'training_time_minutes': capabilities.training_time_minutes
                    }
                }

        return available

    def get_model_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all models."""
        summary = {
            'total_models': len(ModelArchitecture),
            'available_models': 0,
            'trained_models': 0,
            'by_architecture': {},
            'by_task': {}
        }

        for arch in ModelArchitecture:
            model = self.get_model(arch)
            if model:
                capabilities = model.get_capabilities()
                is_available = model.is_available()

                summary['by_architecture'][arch.value] = {
                    'available': is_available,
                    'capabilities': capabilities.typical_accuracy,
                    'tasks': len(capabilities.supported_tasks)
                }

                if is_available:
                    summary['available_models'] += 1
                    if hasattr(model, 'is_trained') and model.is_trained:
                        summary['trained_models'] += 1

                # Count by task
                for task in capabilities.supported_tasks:
                    if task.value not in summary['by_task']:
                        summary['by_task'][task.value] = {'available': 0, 'total': 0}
                    summary['by_task'][task.value]['total'] += 1
                    if is_available:
                        summary['by_task'][task.value]['available'] += 1

        return summary


# Singleton instance
_model_factory = None

def get_model_factory() -> AdvancedModelFactory:
    """Get the singleton AdvancedModelFactory instance."""
    global _model_factory
    if _model_factory is None:
        _model_factory = AdvancedModelFactory()
    return _model_factory

def create_prediction_request(task: PredictionTask, obd_data: List[Dict[str, Any]],
                            **kwargs) -> PredictionRequest:
    """Helper function to create prediction requests."""
    return PredictionRequest(task=task, obd_data=obd_data, **kwargs)