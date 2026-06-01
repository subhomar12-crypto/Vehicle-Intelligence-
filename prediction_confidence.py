"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Prediction Confidence

Prediction Confidence Scoring System
====================================
Calculates confidence levels for AI predictions based on multiple factors.

Features:
- Data quality assessment
- Historical accuracy tracking
- Multi-factor confidence calculation
- Confidence calibration
- Uncertainty quantification
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json
import logging
from pathlib import Path
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


@dataclass
class ConfidenceFactors:
    """Factors contributing to prediction confidence."""
    data_quality: float = 0.0  # 0-1: Quality of input data
    sample_count: float = 0.0  # 0-1: Amount of historical data
    model_accuracy: float = 0.0  # 0-1: Historical prediction accuracy
    pattern_strength: float = 0.0  # 0-1: Strength of detected pattern
    corroboration: float = 0.0  # 0-1: Agreement from multiple indicators
    recency: float = 0.0  # 0-1: How recent the supporting data is
    baseline_deviation: float = 0.0  # 0-1: Confidence based on deviation from baseline
    attention_focus: float = 0.0  # 0-1: Attention mechanism focus (new)
    physics_consistency: float = 0.0  # 0-1: Physics constraint satisfaction (new)


@dataclass
class ConfidenceScore:
    """Complete confidence assessment for a prediction."""
    overall_confidence: float  # 0-1 combined confidence
    confidence_level: str  # "very_low", "low", "medium", "high", "very_high"
    factors: ConfidenceFactors
    explanation: str
    recommendation: str
    timestamp: str


@dataclass
class PredictionFeedback:
    """Feedback on a prediction's accuracy."""
    prediction_id: str
    prediction_type: str
    predicted_outcome: str
    actual_outcome: str
    was_correct: bool
    confidence_at_prediction: float
    timestamp: str


class PredictionConfidenceScorer:
    """
    Calculates and calibrates confidence scores for predictions.
    Tracks historical accuracy to improve calibration over time.
    """

    def __init__(self, config=None):
        """Initialize confidence scorer."""
        self.config = config

        # Storage path
        self.storage_path = CONFIG.AI_DIR / "confidence_data"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Prediction feedback history
        self.feedback_history: deque = deque(maxlen=10000)

        # Accuracy by prediction type
        self.accuracy_by_type: Dict[str, Dict[str, Any]] = {}

        # Calibration factors (learned from feedback)
        self.calibration: Dict[str, float] = {
            'default': 1.0
        }

        # Confidence thresholds
        self.thresholds = {
            'very_low': 0.3,
            'low': 0.5,
            'medium': 0.7,
            'high': 0.85,
            'very_high': 1.0
        }

        # Factor weights
        self.factor_weights = {
            'data_quality': 0.15,
            'sample_count': 0.12,
            'model_accuracy': 0.20,
            'pattern_strength': 0.12,
            'corroboration': 0.12,
            'recency': 0.04,
            'baseline_deviation': 0.04,
            'attention_focus': 0.12,  # New: attention mechanism confidence
            'physics_consistency': 0.09  # New: physics validation confidence
        }

        # Load historical data
        self._load_data()

        logger.info("Prediction Confidence Scorer initialized")

    def _load_data(self):
        """Load saved feedback and calibration data."""
        feedback_file = self.storage_path / "feedback_history.json"
        if feedback_file.exists():
            try:
                with open(feedback_file, 'r') as f:
                    data = json.load(f)
                    for item in data.get('feedback', []):
                        self.feedback_history.append(PredictionFeedback(**item))
                    self.accuracy_by_type = data.get('accuracy_by_type', {})
                    self.calibration = data.get('calibration', {'default': 1.0})
                logger.info(f"Loaded {len(self.feedback_history)} feedback entries")
            except Exception as e:
                logger.warning(f"Failed to load feedback data: {e}")

    def _save_data(self):
        """Save feedback and calibration data."""
        feedback_file = self.storage_path / "feedback_history.json"
        try:
            data = {
                'feedback': [vars(f) for f in self.feedback_history],
                'accuracy_by_type': self.accuracy_by_type,
                'calibration': self.calibration
            }
            with open(feedback_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save feedback data: {e}")

    def calculate_confidence(
        self,
        prediction_type: str,
        data_points: int = 0,
        supporting_evidence: int = 0,
        contradicting_evidence: int = 0,
        pattern_strength: float = 0.5,
        data_age_hours: float = 0,
        baseline_z_score: float = 0,
        related_dtcs: int = 0,
        vehicle_has_baseline: bool = False,
        attention_weights: Optional[Dict[str, Any]] = None,
        physics_validation: Optional[Dict[str, Any]] = None
    ) -> ConfidenceScore:
        """
        Calculate confidence score for a prediction.

        Args:
            prediction_type: Type of prediction (e.g., "failure_battery", "rul_alternator")
            data_points: Number of data points used for prediction
            supporting_evidence: Number of supporting indicators
            contradicting_evidence: Number of contradicting indicators
            pattern_strength: Strength of detected pattern (0-1)
            data_age_hours: Age of most recent data in hours
            baseline_z_score: Z-score deviation from vehicle baseline
            related_dtcs: Number of related DTCs present
            vehicle_has_baseline: Whether vehicle has learned baseline

        Returns:
            ConfidenceScore object
        """
        factors = ConfidenceFactors()

        # Data Quality Factor
        factors.data_quality = self._assess_data_quality(
            data_points, data_age_hours, vehicle_has_baseline
        )

        # Sample Count Factor
        factors.sample_count = self._assess_sample_count(data_points)

        # Model Accuracy Factor
        factors.model_accuracy = self._get_model_accuracy(prediction_type)

        # Pattern Strength Factor
        factors.pattern_strength = min(1.0, pattern_strength)

        # Corroboration Factor
        factors.corroboration = self._assess_corroboration(
            supporting_evidence, contradicting_evidence, related_dtcs
        )

        # Recency Factor
        factors.recency = self._assess_recency(data_age_hours)

        # Baseline Deviation Factor
        factors.baseline_deviation = self._assess_baseline_deviation(
            baseline_z_score, vehicle_has_baseline
        )

        # Attention Focus Factor (new)
        factors.attention_focus = self._assess_attention_focus(attention_weights)

        # Physics Consistency Factor (new)
        factors.physics_consistency = self._assess_physics_consistency(physics_validation)

        # Calculate weighted overall confidence
        overall = (
            factors.data_quality * self.factor_weights['data_quality'] +
            factors.sample_count * self.factor_weights['sample_count'] +
            factors.model_accuracy * self.factor_weights['model_accuracy'] +
            factors.pattern_strength * self.factor_weights['pattern_strength'] +
            factors.corroboration * self.factor_weights['corroboration'] +
            factors.recency * self.factor_weights['recency'] +
            factors.baseline_deviation * self.factor_weights['baseline_deviation'] +
            factors.attention_focus * self.factor_weights['attention_focus'] +
            factors.physics_consistency * self.factor_weights['physics_consistency']
        )

        # Apply calibration
        calibration_factor = self.calibration.get(prediction_type, self.calibration['default'])
        overall = min(1.0, overall * calibration_factor)

        # Determine confidence level
        level = self._get_confidence_level(overall)

        # Generate explanation and recommendation
        explanation = self._generate_explanation(factors, level)
        recommendation = self._generate_recommendation(level, prediction_type)

        return ConfidenceScore(
            overall_confidence=round(overall, 3),
            confidence_level=level,
            factors=factors,
            explanation=explanation,
            recommendation=recommendation,
            timestamp=datetime.now().isoformat()
        )

    def _assess_data_quality(self, data_points: int, data_age_hours: float,
                              has_baseline: bool) -> float:
        """Assess quality of input data."""
        score = 0.0

        # Points for data volume
        if data_points >= 100:
            score += 0.4
        elif data_points >= 30:
            score += 0.3
        elif data_points >= 10:
            score += 0.2
        else:
            score += 0.1

        # Points for data freshness
        if data_age_hours < 1:
            score += 0.3
        elif data_age_hours < 24:
            score += 0.2
        elif data_age_hours < 168:  # 1 week
            score += 0.1

        # Points for having baseline
        if has_baseline:
            score += 0.3

        return min(1.0, score)

    def _assess_sample_count(self, data_points: int) -> float:
        """Assess confidence based on sample count."""
        if data_points >= 500:
            return 1.0
        elif data_points >= 100:
            return 0.8
        elif data_points >= 50:
            return 0.6
        elif data_points >= 20:
            return 0.4
        elif data_points >= 5:
            return 0.2
        return 0.1

    def _get_model_accuracy(self, prediction_type: str) -> float:
        """Get historical model accuracy for prediction type.

        CRITICAL: Returns LOW confidence when there's insufficient training data.
        Absence of evidence != moderate confidence. This prevents overconfident
        predictions on new vehicles with no history.
        """
        if prediction_type in self.accuracy_by_type:
            accuracy_data = self.accuracy_by_type[prediction_type]
            total = accuracy_data.get('total', 0)
            correct = accuracy_data.get('correct', 0)

            if total >= 10:
                # Enough samples for reliable accuracy estimate
                return correct / total
            elif total >= 5:
                # Fewer samples - apply uncertainty penalty
                return (correct / total) * 0.7
            else:
                # Very few samples - low confidence (was 0.5, now 0.25)
                return 0.25

        # No history at all - INSUFFICIENT DATA, not "moderate confidence"
        # Changed from 0.6 to 0.2 to prevent overconfident predictions
        return 0.2

    def _assess_corroboration(self, supporting: int, contradicting: int,
                               related_dtcs: int) -> float:
        """Assess corroboration from multiple sources.

        Returns LOW confidence when no corroborating evidence exists.
        """
        if contradicting > supporting:
            # More contradicting than supporting - low confidence
            return 0.2

        total_evidence = supporting + contradicting
        if total_evidence == 0:
            # No evidence = low confidence, not "moderate"
            return 0.3  # Changed from 0.5

        support_ratio = supporting / total_evidence

        # Boost for related DTCs
        dtc_boost = min(0.2, related_dtcs * 0.1)

        return min(1.0, support_ratio * 0.8 + dtc_boost + 0.1)

    def _assess_recency(self, data_age_hours: float) -> float:
        """Assess confidence based on data recency."""
        if data_age_hours < 0.5:  # 30 minutes
            return 1.0
        elif data_age_hours < 2:
            return 0.9
        elif data_age_hours < 24:
            return 0.7
        elif data_age_hours < 168:  # 1 week
            return 0.5
        elif data_age_hours < 720:  # 30 days
            return 0.3
        return 0.1

    def _assess_baseline_deviation(self, z_score: float, has_baseline: bool) -> float:
        """Assess confidence based on deviation from baseline."""
        if not has_baseline:
            return 0.5  # Neutral if no baseline

        # Higher z-scores (bigger deviations) can mean higher confidence in anomaly detection
        # But also could indicate sensor issues

        if z_score < 1:
            return 0.4  # Small deviation - less confident something is wrong
        elif z_score < 2:
            return 0.6  # Moderate deviation
        elif z_score < 3:
            return 0.8  # Significant deviation
        else:
            return 0.9  # Large deviation - high confidence in anomaly

    def _get_confidence_level(self, confidence: float) -> str:
        """Convert numerical confidence to level string."""
        if confidence < self.thresholds['very_low']:
            return 'very_low'
        elif confidence < self.thresholds['low']:
            return 'low'
        elif confidence < self.thresholds['medium']:
            return 'medium'
        elif confidence < self.thresholds['high']:
            return 'high'
        return 'very_high'

    def _generate_explanation(self, factors: ConfidenceFactors, level: str) -> str:
        """Generate human-readable explanation of confidence."""
        parts = []

        if factors.data_quality < 0.5:
            parts.append("limited data quality")
        if factors.sample_count < 0.5:
            parts.append("few historical samples")
        if factors.model_accuracy < 0.5:
            parts.append("uncertain model accuracy")
        if factors.pattern_strength > 0.7:
            parts.append("strong pattern detected")
        if factors.corroboration > 0.7:
            parts.append("multiple indicators agree")
        if factors.corroboration < 0.3:
            parts.append("conflicting indicators")
        if factors.attention_focus > 0.7:
            parts.append("attention mechanism shows focused patterns")
        if factors.attention_focus < 0.3:
            parts.append("attention mechanism shows unfocused patterns")
        if factors.physics_consistency > 0.7:
            parts.append("physics constraints satisfied")
        if factors.physics_consistency < 0.3:
            parts.append("physics constraint violations detected")

        if not parts:
            if level in ['high', 'very_high']:
                return "Good data quality and consistent indicators support this prediction."
            else:
                return "Moderate evidence supports this prediction."

        return f"Confidence is {level} due to: {', '.join(parts)}."

    def _generate_recommendation(self, level: str, prediction_type: str) -> str:
        """Generate recommendation based on confidence level."""
        if level == 'very_high':
            return "This prediction is highly reliable. Recommended action can proceed."
        elif level == 'high':
            return "This prediction is reliable. Consider acting on it."
        elif level == 'medium':
            return "Moderate confidence. Monitor the situation and gather more data."
        elif level == 'low':
            return "Low confidence. Verify with additional diagnostics before acting."
        else:
            return "Very low confidence. This is speculative. Professional inspection recommended."

    def record_feedback(self, prediction_id: str, prediction_type: str,
                        predicted_outcome: str, actual_outcome: str,
                        confidence_at_prediction: float):
        """
        Record feedback on a prediction's accuracy.
        Used to calibrate future confidence scores.
        """
        was_correct = predicted_outcome == actual_outcome

        feedback = PredictionFeedback(
            prediction_id=prediction_id,
            prediction_type=prediction_type,
            predicted_outcome=predicted_outcome,
            actual_outcome=actual_outcome,
            was_correct=was_correct,
            confidence_at_prediction=confidence_at_prediction,
            timestamp=datetime.now().isoformat()
        )

        self.feedback_history.append(feedback)

        # Update accuracy tracking
        if prediction_type not in self.accuracy_by_type:
            self.accuracy_by_type[prediction_type] = {'total': 0, 'correct': 0}

        self.accuracy_by_type[prediction_type]['total'] += 1
        if was_correct:
            self.accuracy_by_type[prediction_type]['correct'] += 1

        # Recalibrate if we have enough feedback
        if len(self.feedback_history) % 20 == 0:
            self._recalibrate()

        self._save_data()

        return {
            'recorded': True,
            'was_correct': was_correct,
            'current_accuracy': self._get_model_accuracy(prediction_type)
        }

    def _recalibrate(self):
        """Recalibrate confidence scores based on feedback."""
        for pred_type, accuracy_data in self.accuracy_by_type.items():
            total = accuracy_data.get('total', 0)
            if total < 10:
                continue

            correct = accuracy_data.get('correct', 0)
            accuracy = correct / total

            # Adjust calibration based on accuracy
            if accuracy > 0.8:
                self.calibration[pred_type] = 1.1  # Slightly boost confidence
            elif accuracy < 0.5:
                self.calibration[pred_type] = 0.8  # Reduce confidence
            else:
                self.calibration[pred_type] = 1.0  # Keep neutral

        logger.info(f"Recalibrated confidence for {len(self.accuracy_by_type)} prediction types")

    def get_accuracy_report(self) -> Dict[str, Any]:
        """Get accuracy report for all prediction types."""
        report = {
            'total_predictions': len(self.feedback_history),
            'by_type': {}
        }

        for pred_type, data in self.accuracy_by_type.items():
            total = data.get('total', 0)
            correct = data.get('correct', 0)

            report['by_type'][pred_type] = {
                'total': total,
                'correct': correct,
                'accuracy': round(correct / total, 3) if total > 0 else None,
                'calibration_factor': self.calibration.get(pred_type, 1.0)
            }

        return report

    def get_calibration_status(self) -> Dict[str, Any]:
        """Get current calibration status."""
        return {
            'calibration_factors': self.calibration,
            'feedback_count': len(self.feedback_history),
            'prediction_types': list(self.accuracy_by_type.keys())
        }
