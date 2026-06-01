"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Ai Prediction Integrity

AI Prediction Integrity System
Ensures trustworthy, traceable, and accountable AI predictions.

REQUIREMENTS:
- Model versioning and rollback
- Prediction confidence scoring
- Ground-truth feedback loop
- Complete audit trail
- Suppress low-confidence predictions
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict

from config import get_config
from audit_logger import log_audit_event, AuditEventType

logger = logging.getLogger(__name__)


@dataclass
class PredictionRecord:
    """Complete prediction record for audit trail"""
    prediction_id: str
    customer_id: str
    vehicle_id: str
    model_version: str
    model_name: str
    timestamp: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    confidence_score: float  # 0.0-1.0
    data_quality_score: float  # 0.0-1.0
    prediction_type: str  # e.g., "failure_risk", "maintenance_needed"
    suppressed: bool  # True if confidence too low
    suppression_reason: Optional[str]
    feedback_received: bool = False
    ground_truth: Optional[Any] = None
    feedback_timestamp: Optional[str] = None


@dataclass
class ModelMetadata:
    """AI model metadata"""
    model_id: str
    model_name: str
    version: str
    trained_at: str
    accuracy_metrics: Dict[str, float]
    training_data_count: int
    features_used: List[str]
    deployed_at: Optional[str] = None
    deprecated_at: Optional[str] = None
    rollback_from: Optional[str] = None


class AIPredictionManager:
    """
    Manages AI predictions with full integrity guarantees.

    Features:
    - Version tracking
    - Confidence-based suppression
    - Feedback loop
    - Audit trail
    """

    # Minimum confidence threshold for displaying predictions
    MIN_CONFIDENCE_THRESHOLD = 0.70  # 70%

    # Minimum data points required for predictions
    MIN_DATA_POINTS = 50

    def __init__(self):
        self.config = get_config()
        self._active_model: Optional[ModelMetadata] = None

    def make_prediction(
        self,
        customer_id: str,
        vehicle_id: str,
        prediction_type: str,
        inputs: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Make a prediction with integrity checks.

        Args:
            customer_id: Customer making request
            vehicle_id: Vehicle for prediction
            prediction_type: Type of prediction
            inputs: Input data for prediction

        Returns:
            (success, prediction_result, error_message)
        """
        try:
            # Load active model
            model = self._get_active_model()
            if not model:
                return False, None, "No active AI model available"

            # Check data quality
            data_quality_score = self._assess_data_quality(inputs)
            if data_quality_score < 0.5:
                return False, None, "Insufficient data quality for prediction"

            # Make prediction using LSTM predictor
            prediction_result, confidence = self._run_model(model, inputs, prediction_type)

            # Generate prediction ID
            prediction_id = self._generate_prediction_id()

            # Determine if prediction should be suppressed
            suppressed = False
            suppression_reason = None

            if confidence < self.MIN_CONFIDENCE_THRESHOLD:
                suppressed = True
                suppression_reason = f"Confidence {confidence:.2%} below threshold {self.MIN_CONFIDENCE_THRESHOLD:.2%}"

            # Create prediction record
            record = PredictionRecord(
                prediction_id=prediction_id,
                customer_id=customer_id,
                vehicle_id=vehicle_id,
                model_version=model.version,
                model_name=model.model_name,
                timestamp=datetime.now().isoformat(),
                inputs=inputs,
                outputs=prediction_result,
                confidence_score=confidence,
                data_quality_score=data_quality_score,
                prediction_type=prediction_type,
                suppressed=suppressed,
                suppression_reason=suppression_reason
            )

            # Save prediction record
            self._save_prediction_record(record)

            # Audit log
            log_audit_event(
                event_type=AuditEventType.PREDICTION_GENERATED,
                customer_id=customer_id,
                details={
                    "prediction_id": prediction_id,
                    "vehicle_id": vehicle_id,
                    "model_version": model.version,
                    "confidence": confidence,
                    "suppressed": suppressed,
                    "prediction_type": prediction_type
                }
            )

            # Return result (None if suppressed)
            if suppressed:
                logger.info(f"Prediction suppressed: {suppression_reason}")
                return True, None, suppression_reason
            else:
                return True, {
                    "prediction_id": prediction_id,
                    "model_version": model.version,
                    "confidence": confidence,
                    "result": prediction_result,
                    "timestamp": record.timestamp
                }, None

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return False, None, f"Prediction failed: {str(e)}"

    def submit_feedback(
        self,
        prediction_id: str,
        ground_truth: Any,
        customer_id: str
    ) -> Tuple[bool, str]:
        """
        Submit ground-truth feedback for a prediction.

        Args:
            prediction_id: Prediction to provide feedback for
            ground_truth: Actual outcome
            customer_id: Customer submitting feedback

        Returns:
            (success, message)
        """
        try:
            # Load prediction record
            record = self._load_prediction_record(prediction_id)
            if not record:
                return False, "Prediction not found"

            # Verify customer owns this prediction
            if record.customer_id != customer_id:
                return False, "Unauthorized: prediction belongs to different customer"

            # Update record with feedback
            record.feedback_received = True
            record.ground_truth = ground_truth
            record.feedback_timestamp = datetime.now().isoformat()

            # Save updated record
            self._save_prediction_record(record)

            # Update accuracy tracking
            self._update_accuracy_metrics(record)

            # Audit log
            log_audit_event(
                event_type=AuditEventType.PREDICTION_FEEDBACK,
                customer_id=customer_id,
                details={
                    "prediction_id": prediction_id,
                    "ground_truth": ground_truth,
                    "model_version": record.model_version
                }
            )

            logger.info(f"Feedback received for prediction {prediction_id}")

            return True, "Feedback submitted successfully"

        except Exception as e:
            logger.error(f"Feedback submission error: {e}")
            return False, f"Failed to submit feedback: {str(e)}"

    def deploy_model(
        self,
        model_name: str,
        version: str,
        accuracy_metrics: Dict[str, float],
        training_data_count: int,
        features_used: List[str],
        deployed_by: str = "system"
    ) -> Tuple[bool, str]:
        """
        Deploy a new AI model version.

        Args:
            model_name: Model name
            version: Model version
            accuracy_metrics: Validation accuracy metrics
            training_data_count: Number of training examples
            features_used: List of features
            deployed_by: Who deployed the model

        Returns:
            (success, message)
        """
        try:
            # Create model metadata
            model_id = f"{model_name}_v{version}"

            metadata = ModelMetadata(
                model_id=model_id,
                model_name=model_name,
                version=version,
                trained_at=datetime.now().isoformat(),
                accuracy_metrics=accuracy_metrics,
                training_data_count=training_data_count,
                features_used=features_used,
                deployed_at=datetime.now().isoformat()
            )

            # Save model metadata
            self._save_model_metadata(metadata)

            # Update model registry
            self._update_model_registry(metadata, set_active=True)

            # Audit log
            log_audit_event(
                event_type=AuditEventType.MODEL_DEPLOYED,
                details={
                    "model_id": model_id,
                    "version": version,
                    "accuracy_metrics": accuracy_metrics,
                    "deployed_by": deployed_by
                }
            )

            logger.info(f"Model deployed: {model_id}")

            return True, f"Model {model_id} deployed successfully"

        except Exception as e:
            logger.error(f"Model deployment error: {e}")
            return False, f"Deployment failed: {str(e)}"

    def rollback_model(
        self,
        to_version: str,
        reason: str,
        rolled_back_by: str = "operator"
    ) -> Tuple[bool, str]:
        """
        Rollback to a previous model version.

        Args:
            to_version: Version to rollback to
            reason: Reason for rollback
            rolled_back_by: Who performed rollback

        Returns:
            (success, message)
        """
        try:
            # Load target model
            models = self._load_model_registry()
            target_model = None

            for model in models:
                if model["version"] == to_version:
                    target_model = ModelMetadata(**model)
                    break

            if not target_model:
                return False, f"Model version {to_version} not found"

            # Mark current model as deprecated
            current_model = self._get_active_model()
            if current_model:
                current_model.deprecated_at = datetime.now().isoformat()
                self._save_model_metadata(current_model)

            # Activate target model
            target_model.rollback_from = current_model.version if current_model else None
            self._update_model_registry(target_model, set_active=True)

            # Audit log
            log_audit_event(
                event_type=AuditEventType.MODEL_ROLLBACK,
                details={
                    "from_version": current_model.version if current_model else "none",
                    "to_version": to_version,
                    "reason": reason,
                    "rolled_back_by": rolled_back_by
                }
            )

            logger.info(f"Model rolled back to version {to_version}")

            return True, f"Rolled back to version {to_version}"

        except Exception as e:
            logger.error(f"Model rollback error: {e}")
            return False, f"Rollback failed: {str(e)}"

    def get_prediction_audit_trail(
        self,
        customer_id: str,
        vehicle_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get complete audit trail of predictions"""
        predictions_dir = self.config.AI_PREDICTIONS_DIR

        if not predictions_dir.exists():
            return []

        predictions = []
        for pred_file in sorted(predictions_dir.glob("*.json"), reverse=True):
            try:
                with open(pred_file, 'r') as f:
                    record_data = json.load(f)

                record = PredictionRecord(**record_data)

                # Filter by customer
                if record.customer_id != customer_id:
                    continue

                # Filter by vehicle if specified
                if vehicle_id and record.vehicle_id != vehicle_id:
                    continue

                predictions.append(asdict(record))

                if len(predictions) >= limit:
                    break

            except:
                continue

        return predictions

    def _get_active_model(self) -> Optional[ModelMetadata]:
        """Get currently active model"""
        if self._active_model:
            return self._active_model

        registry_file = self.config.AI_MODELS_REGISTRY

        if not registry_file.exists():
            return None

        try:
            with open(registry_file, 'r') as f:
                registry = json.load(f)

            active_model_id = registry.get("active_model")
            if not active_model_id:
                return None

            # Find active model in registry
            for model_data in registry.get("models", []):
                if model_data.get("model_id") == active_model_id:
                    self._active_model = ModelMetadata(**model_data)
                    return self._active_model

            return None

        except Exception as e:
            logger.error(f"Error loading active model: {e}")
            return None

    def _run_model(
        self,
        model: ModelMetadata,
        inputs: Dict[str, Any],
        prediction_type: str
    ) -> Tuple[Dict[str, Any], float]:
        """
        Run AI model inference using integrated LSTM predictor.

        Returns:
            (prediction_result, confidence_score)
        """
        try:
            # Try to import and use LSTM predictor
            from lstm_predictor import LSTMPredictor
            
            # Initialize predictor if not already loaded
            if not hasattr(self, '_lstm_predictor'):
                self._lstm_predictor = LSTMPredictor()
            
            predictor = self._lstm_predictor
            
            # Prepare input data for LSTM model
            # Extract relevant features from inputs
            feature_vector = self._prepare_feature_vector(inputs, prediction_type)
            
            # Get prediction from LSTM model
            prediction = predictor.predict(feature_vector)
            
            # Calculate confidence based on prediction uncertainty
            confidence = predictor.get_confidence(feature_vector)
            
            # Format prediction result
            prediction_result = self._format_prediction_result(prediction, prediction_type)
            
            logger.info(f"AI model inference completed: {model.model_id}, confidence: {confidence:.2%}")
            
            return prediction_result, confidence
            
        except ImportError:
            logger.warning("LSTM predictor not available, using fallback prediction")
            return self._fallback_prediction(inputs, prediction_type)
        except Exception as e:
            logger.error(f"AI model inference error: {e}")
            return self._fallback_prediction(inputs, prediction_type)

    def _prepare_feature_vector(self, inputs: Dict[str, Any], prediction_type: str) -> Dict[str, float]:
        """
        Prepare feature vector for LSTM model from raw inputs.
        
        Args:
            inputs: Raw sensor data
            prediction_type: Type of prediction
            
        Returns:
            Normalized feature vector
        """
        # Extract and normalize key features
        features = {}
        
        # Engine parameters
        features['rpm'] = self._normalize_value(inputs.get('rpm'), 0, 8000)
        features['coolant_temp'] = self._normalize_value(inputs.get('coolant_temp'), 0, 120)
        features['engine_load'] = self._normalize_value(inputs.get('engine_load'), 0, 100)
        features['throttle_pos'] = self._normalize_value(inputs.get('throttle_position'), 0, 100)
        features['intake_temp'] = self._normalize_value(inputs.get('intake_temp'), -20, 100)
        
        # Fuel system
        features['fuel_trim_short'] = self._normalize_value(inputs.get('fuel_trim_short'), -100, 100)
        features['fuel_trim_long'] = self._normalize_value(inputs.get('fuel_trim_long'), -100, 100)
        features['maf'] = self._normalize_value(inputs.get('maf'), 0, 500)
        
        # Electrical
        features['battery_voltage'] = self._normalize_value(inputs.get('battery_voltage'), 10, 15)
        
        # Vehicle dynamics
        features['speed'] = self._normalize_value(inputs.get('speed'), 0, 200)
        
        # Timing and emissions
        features['timing_advance'] = self._normalize_value(inputs.get('timing_advance'), 0, 60)
        features['catalyst_temp'] = self._normalize_value(inputs.get('catalyst_temp'), 0, 1000)
        
        # Add prediction type encoding
        prediction_type_map = {
            'failure_risk': [1, 0, 0],
            'maintenance_needed': [0, 1, 0],
            'component_health': [0, 0, 1]
        }
        type_encoding = prediction_type_map.get(prediction_type, [0, 0, 0])
        features['pred_type_0'] = type_encoding[0]
        features['pred_type_1'] = type_encoding[1]
        features['pred_type_2'] = type_encoding[2]
        
        return features

    def _normalize_value(self, value: Optional[float], min_val: float, max_val: float) -> float:
        """
        Normalize a value to [0, 1] range.
        
        Args:
            value: Value to normalize
            min_val: Expected minimum value
            max_val: Expected maximum value
            
        Returns:
            Normalized value in [0, 1] range
        """
        if value is None:
            return 0.5  # Default to middle of range
        
        try:
            normalized = (value - min_val) / (max_val - min_val)
            return max(0.0, min(1.0, normalized))
        except (TypeError, ZeroDivisionError):
            return 0.5

    def _format_prediction_result(self, prediction: Dict[str, Any], prediction_type: str) -> Dict[str, Any]:
        """
        Format raw prediction output into standardized result.
        
        Args:
            prediction: Raw prediction from model
            prediction_type: Type of prediction
            
        Returns:
            Formatted prediction result
        """
        result = {
            'prediction_type': prediction_type,
            'timestamp': datetime.now().isoformat()
        }
        
        # Extract risk level
        risk_score = prediction.get('risk_score', 0.5)
        if risk_score < 0.3:
            result['risk_level'] = 'low'
            result['recommended_action'] = 'monitor'
        elif risk_score < 0.7:
            result['risk_level'] = 'medium'
            result['recommended_action'] = 'schedule_inspection'
        else:
            result['risk_level'] = 'high'
            result['recommended_action'] = 'immediate_attention'
        
        # Add time to failure estimate if available
        if 'estimated_ttf_days' in prediction:
            result['estimated_ttf_days'] = prediction['estimated_ttf_days']
        else:
            # Estimate based on risk score
            if risk_score < 0.3:
                result['estimated_ttf_days'] = 180
            elif risk_score < 0.7:
                result['estimated_ttf_days'] = 60
            else:
                result['estimated_ttf_days'] = 14
        
        # Add component-specific predictions if available
        if 'component_predictions' in prediction:
            result['component_predictions'] = prediction['feature_importance']
        
        # Add confidence breakdown
        if 'confidence_breakdown' in prediction:
            result['confidence_breakdown'] = prediction['confidence_breakdown']
        
        return result

    def _fallback_prediction(self, inputs: Dict[str, Any], prediction_type: str) -> Tuple[Dict[str, Any], float]:
        """
        Generate fallback prediction when AI model is unavailable.
        Uses rule-based logic as a fallback.
        
        Returns:
            (prediction_result, confidence_score)
        """
        # Simple rule-based prediction
        risk_score = 0.5  # Default to medium risk
        
        # Check for obvious warning signs
        coolant_temp = inputs.get('coolant_temp')
        if coolant_temp and coolant_temp > 100:
            risk_score = 0.8
        elif coolant_temp and coolant_temp < 70:
            risk_score = 0.4
        
        engine_load = inputs.get('engine_load')
        if engine_load and engine_load > 90:
            risk_score = max(risk_score, 0.7)
        
        battery_voltage = inputs.get('battery_voltage')
        if battery_voltage and battery_voltage < 12:
            risk_score = max(risk_score, 0.9)
        
        # Format result
        if risk_score < 0.3:
            risk_level = 'low'
            recommended_action = 'monitor'
            ttf_days = 120
        elif risk_score < 0.7:
            risk_level = 'medium'
            recommended_action = 'schedule_inspection'
            ttf_days = 60
        else:
            risk_level = 'high'
            recommended_action = 'immediate_attention'
            ttf_days = 14
        
        prediction_result = {
            'risk_level': risk_level,
            'recommended_action': recommended_action,
            'estimated_ttf_days': ttf_days,
            'prediction_type': prediction_type,
            'fallback_mode': True
        }
        
        # Lower confidence for fallback predictions
        confidence = 0.6  # 60% confidence for rule-based fallback
        
        logger.warning(f"Using fallback prediction: risk={risk_level}, confidence={confidence:.2%}")
        
        return prediction_result, confidence

    def _assess_data_quality(self, inputs: Dict[str, Any]) -> float:
        """
        Assess quality of input data.

        Returns:
            Quality score 0.0-1.0
        """
        # Check for missing values
        total_fields = len(inputs)
        if total_fields == 0:
            return 0.0

        non_null_fields = sum(1 for v in inputs.values() if v is not None)

        # Basic quality score = completeness
        completeness = non_null_fields / total_fields

        # Could add more sophisticated checks:
        # - Value ranges
        # - Outlier detection
        # - Temporal consistency

        return completeness

    def _save_prediction_record(self, record: PredictionRecord):
        """Save prediction record to audit trail"""
        predictions_dir = self.config.AI_PREDICTIONS_DIR
        predictions_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{record.prediction_id}.json"
        filepath = predictions_dir / filename

        with open(filepath, 'w') as f:
            json.dump(asdict(record), f, indent=2)

    def _load_prediction_record(self, prediction_id: str) -> Optional[PredictionRecord]:
        """Load prediction record"""
        filepath = self.config.AI_PREDICTIONS_DIR / f"{prediction_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            return PredictionRecord(**data)

        except Exception as e:
            logger.error(f"Error loading prediction record: {e}")
            return None

    def _save_model_metadata(self, metadata: ModelMetadata):
        """Save model metadata"""
        models_dir = self.config.AI_MODELS_DIR
        models_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{metadata.model_id}_metadata.json"
        filepath = models_dir / filename

        with open(filepath, 'w') as f:
            json.dump(asdict(metadata), f, indent=2)

    def _update_model_registry(self, metadata: ModelMetadata, set_active: bool = False):
        """Update model registry"""
        registry_file = self.config.AI_MODELS_REGISTRY
        registry_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing registry
        if registry_file.exists():
            with open(registry_file, 'r') as f:
                registry = json.load(f)
        else:
            registry = {"models": [], "active_model": None}

        # Update or add model
        model_dict = asdict(metadata)
        existing_idx = None

        for i, model in enumerate(registry["models"]):
            if model["model_id"] == metadata.model_id:
                existing_idx = i
                break

        if existing_idx is not None:
            registry["models"][existing_idx] = model_dict
        else:
            registry["models"].append(model_dict)

        # Set as active if requested
        if set_active:
            registry["active_model"] = metadata.model_id
            self._active_model = metadata

        # Save registry
        with open(registry_file, 'w') as f:
            json.dump(registry, f, indent=2)

    def _load_model_registry(self) -> List[Dict[str, Any]]:
        """Load all models from registry"""
        registry_file = self.config.AI_MODELS_REGISTRY

        if not registry_file.exists():
            return []

        try:
            with open(registry_file, 'r') as f:
                registry = json.load(f)

            return registry.get("models", [])

        except Exception as e:
            logger.error(f"Error loading model registry: {e}")
            return []

    def _update_accuracy_metrics(self, record: PredictionRecord):
        """Update accuracy tracking with feedback"""
        accuracy_file = self.config.AI_ACCURACY_FILE
        accuracy_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing accuracy data
        if accuracy_file.exists():
            with open(accuracy_file, 'r') as f:
                accuracy_data = json.load(f)
        else:
            accuracy_data = {
                "predictions_total": 0,
                "feedback_received": 0,
                "accuracy_by_type": {}
            }

        # Update metrics
        accuracy_data["predictions_total"] += 1
        accuracy_data["feedback_received"] += 1

        # Update by type
        pred_type = record.prediction_type
        if pred_type not in accuracy_data["accuracy_by_type"]:
            accuracy_data["accuracy_by_type"][pred_type] = {
                "total": 0,
                "correct": 0,
                "accuracy": 0.0
            }

        type_metrics = accuracy_data["accuracy_by_type"][pred_type]
        type_metrics["total"] += 1

        # Check if prediction was correct (simplified)
        # In production, implement proper accuracy calculation based on prediction type
        # For now, assume prediction matches ground truth if they're equal
        if record.outputs == record.ground_truth:
            type_metrics["correct"] += 1

        type_metrics["accuracy"] = type_metrics["correct"] / type_metrics["total"]

        # Save updated accuracy data
        with open(accuracy_file, 'w') as f:
            json.dump(accuracy_data, f, indent=2)

    def _generate_prediction_id(self) -> str:
        """Generate unique prediction ID"""
        import secrets
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = secrets.token_hex(4)
        return f"pred_{timestamp}_{random_suffix}"


# ==================== MODULE-LEVEL FUNCTIONS ====================

_prediction_manager: Optional[AIPredictionManager] = None


def get_prediction_manager() -> AIPredictionManager:
    """Get global prediction manager instance"""
    global _prediction_manager
    if _prediction_manager is None:
        _prediction_manager = AIPredictionManager()
    return _prediction_manager
