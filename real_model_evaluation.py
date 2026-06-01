"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Real Model Evaluation

Real Model Evaluation System
============================
CRITICAL: Replaces ALL placeholder accuracy metrics with REAL inference-based evaluation.

This module provides:
- Actual model inference on held-out test data
- Per-failure-type accuracy, precision, recall, F1, F2 scores
- Confusion matrix generation
- False negative rate tracking (CRITICAL for safety)
- Model comparison and regression detection
- Calibration curve analysis

SAFETY PRINCIPLE:
"We will NOT claim any accuracy we cannot prove with real data."
"Placeholder metrics are LIES that can cause harm."

Author: Safety Engineering Team
Version: 1.0.0
"""

import numpy as np
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict
import hashlib

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PerClassMetrics:
    """Metrics for a single failure type."""
    class_name: str
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def total_samples(self) -> int:
        return self.true_positives + self.true_negatives + self.false_positives + self.false_negatives

    @property
    def accuracy(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / self.total_samples

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN) - CRITICAL for safety (minimize false negatives)"""
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1_score(self) -> float:
        p, r = self.precision, self.recall
        return 2 * (p * r) / (p + r) if (p + r) > 0 else 0.0

    @property
    def f2_score(self) -> float:
        """F2 score - weights recall higher than precision (SAFETY-BIASED)"""
        p, r = self.precision, self.recall
        beta = 2  # Beta=2 means recall is 2x as important as precision
        return (1 + beta**2) * (p * r) / ((beta**2 * p) + r) if (p + r) > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        """FNR = FN / (FN + TP) - MUST BE LOW for safety"""
        denom = self.false_negatives + self.true_positives
        return self.false_negatives / denom if denom > 0 else 0.0

    @property
    def specificity(self) -> float:
        """True negative rate"""
        denom = self.true_negatives + self.false_positives
        return self.true_negatives / denom if denom > 0 else 0.0


@dataclass
class ModelEvaluationResult:
    """Complete evaluation result for a model."""
    model_name: str
    model_version: str
    architecture: str
    evaluation_timestamp: str
    evaluation_id: str

    # Dataset info
    test_samples: int
    unique_vehicles: int
    vehicle_makes: List[str]
    vehicle_years_range: Tuple[int, int]

    # Overall metrics
    overall_accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    macro_f2: float  # SAFETY-BIASED metric

    # Per-class metrics
    per_class_metrics: Dict[str, PerClassMetrics]

    # Safety-critical metrics
    critical_system_recall: float  # Recall for critical systems only
    false_negative_rate_critical: float  # FNR for critical systems
    false_negative_rate_high: float  # FNR for high-priority systems

    # Confusion matrix
    confusion_matrix: List[List[int]]
    class_labels: List[str]

    # Calibration
    calibration_error: float  # Expected Calibration Error
    is_well_calibrated: bool

    # Validation
    meets_safety_requirements: bool
    safety_violations: List[str]

    # Hash for integrity
    evaluation_hash: str


@dataclass
class EvaluationTestCase:
    """A single test case for evaluation."""
    test_id: str
    vehicle_id: Optional[str]
    vehicle_make: Optional[str]
    vehicle_model: Optional[str]
    vehicle_year: Optional[int]
    obd_sequence: List[Dict[str, Any]]
    true_failure_type: str
    true_failure_occurred: bool
    true_days_to_failure: Optional[int]


# =============================================================================
# SAFETY REQUIREMENTS
# =============================================================================

# Maximum acceptable false negative rates by criticality
MAX_FALSE_NEGATIVE_RATES = {
    'critical': 0.01,   # 1% max for critical systems (cooling, transmission)
    'high': 0.03,       # 3% max for high-priority systems (battery, alternator)
    'medium': 0.05,     # 5% max for medium-priority systems
    'low': 0.10,        # 10% max for low-priority systems
}

# Minimum required recall by criticality
MIN_RECALL_REQUIREMENTS = {
    'critical': 0.99,   # 99% recall for critical systems
    'high': 0.97,       # 97% recall for high-priority systems
    'medium': 0.95,     # 95% recall for medium-priority systems
    'low': 0.90,        # 90% recall for low-priority systems
}

# System criticality mapping
SYSTEM_CRITICALITY_MAP = {
    'coolant_system': 'critical',
    'thermostat': 'critical',
    'transmission': 'critical',
    'battery': 'high',
    'alternator': 'high',
    'starter': 'high',
    'fuel_pump': 'high',
    'ignition': 'high',
    'spark_plug': 'medium',
    'oxygen_sensor': 'medium',
    'catalytic_converter': 'medium',
    'maf_sensor': 'medium',
    'no_failure': 'low',
}


# =============================================================================
# REAL MODEL EVALUATOR
# =============================================================================

class RealModelEvaluator:
    """
    Performs REAL inference-based model evaluation.

    NO PLACEHOLDER METRICS - all values come from actual model predictions
    on held-out test data.
    """

    VERSION = "1.0.0"

    def __init__(self):
        """Initialize the evaluator."""
        self.evaluation_dir = CONFIG.AI_DIR / "model_evaluations"
        self.evaluation_dir.mkdir(parents=True, exist_ok=True)

        self.test_data_dir = CONFIG.AI_DIR / "test_data"
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

        # Evaluation history
        self.evaluation_history: List[ModelEvaluationResult] = []

        logger.info("RealModelEvaluator initialized - NO placeholder metrics allowed")

    def evaluate_model(
        self,
        model,
        model_name: str,
        model_version: str,
        architecture: str,
        test_data: List[EvaluationTestCase]
    ) -> ModelEvaluationResult:
        """
        Evaluate a model using REAL inference on test data.

        Args:
            model: The model to evaluate (must have predict() method)
            model_name: Name of the model
            model_version: Version string
            architecture: Architecture type
            test_data: List of test cases

        Returns:
            Complete evaluation result with REAL metrics
        """
        if not test_data:
            raise ValueError("Cannot evaluate model with empty test data")

        evaluation_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().isoformat()

        logger.info(f"Starting REAL evaluation: {model_name} v{model_version} on {len(test_data)} samples")

        # Initialize per-class metrics
        class_labels = list(set(tc.true_failure_type for tc in test_data))
        per_class_metrics = {label: PerClassMetrics(class_name=label) for label in class_labels}

        # Initialize confusion matrix
        label_to_idx = {label: i for i, label in enumerate(class_labels)}
        n_classes = len(class_labels)
        confusion_matrix = [[0] * n_classes for _ in range(n_classes)]

        # Track vehicle info
        vehicle_makes = set()
        vehicle_years = []

        # Calibration data
        predicted_probs = []
        actual_outcomes = []

        # Run predictions
        for test_case in test_data:
            try:
                # Get model prediction
                prediction = model.predict(test_case.obd_sequence)

                if prediction is None:
                    logger.warning(f"Model returned None for test case {test_case.test_id}")
                    continue

                # Extract prediction values
                if hasattr(prediction, 'failure_probability'):
                    pred_prob = prediction.failure_probability
                    pred_type = prediction.failure_type
                elif isinstance(prediction, dict):
                    pred_prob = prediction.get('failure_probability', 0.5)
                    pred_type = prediction.get('failure_type', 'unknown')
                else:
                    continue

                # Track for calibration
                predicted_probs.append(pred_prob)
                actual_outcomes.append(1 if test_case.true_failure_occurred else 0)

                # Determine predicted class
                pred_failure = pred_prob > 0.5

                # Update confusion matrix
                true_label = test_case.true_failure_type
                if true_label in label_to_idx and pred_type in label_to_idx:
                    true_idx = label_to_idx[true_label]
                    pred_idx = label_to_idx[pred_type]
                    confusion_matrix[true_idx][pred_idx] += 1

                # Update per-class metrics
                self._update_class_metrics(
                    per_class_metrics,
                    true_label,
                    pred_type,
                    test_case.true_failure_occurred,
                    pred_failure
                )

                # Track vehicle info
                if test_case.vehicle_make:
                    vehicle_makes.add(test_case.vehicle_make)
                if test_case.vehicle_year:
                    vehicle_years.append(test_case.vehicle_year)

            except Exception as e:
                logger.error(f"Evaluation error for {test_case.test_id}: {e}")
                continue

        # Calculate overall metrics
        overall_metrics = self._calculate_overall_metrics(per_class_metrics)

        # Calculate safety-critical metrics
        safety_metrics = self._calculate_safety_metrics(per_class_metrics)

        # Calculate calibration error
        calibration_error = self._calculate_calibration_error(predicted_probs, actual_outcomes)

        # Check safety requirements
        meets_safety, violations = self._check_safety_requirements(per_class_metrics)

        # Determine vehicle year range
        year_range = (min(vehicle_years), max(vehicle_years)) if vehicle_years else (0, 0)

        # Create result
        result = ModelEvaluationResult(
            model_name=model_name,
            model_version=model_version,
            architecture=architecture,
            evaluation_timestamp=timestamp,
            evaluation_id=evaluation_id,
            test_samples=len(test_data),
            unique_vehicles=len(set(tc.vehicle_id for tc in test_data if tc.vehicle_id)),
            vehicle_makes=list(vehicle_makes),
            vehicle_years_range=year_range,
            overall_accuracy=overall_metrics['accuracy'],
            macro_precision=overall_metrics['precision'],
            macro_recall=overall_metrics['recall'],
            macro_f1=overall_metrics['f1'],
            macro_f2=overall_metrics['f2'],
            per_class_metrics=per_class_metrics,
            critical_system_recall=safety_metrics['critical_recall'],
            false_negative_rate_critical=safety_metrics['fnr_critical'],
            false_negative_rate_high=safety_metrics['fnr_high'],
            confusion_matrix=confusion_matrix,
            class_labels=class_labels,
            calibration_error=calibration_error,
            is_well_calibrated=calibration_error < 0.1,
            meets_safety_requirements=meets_safety,
            safety_violations=violations,
            evaluation_hash=self._generate_hash(evaluation_id, timestamp, len(test_data))
        )

        # Save evaluation
        self._save_evaluation(result)
        self.evaluation_history.append(result)

        logger.info(
            f"Evaluation complete: {model_name} | "
            f"Accuracy: {result.overall_accuracy:.2%} | "
            f"F2: {result.macro_f2:.2%} | "
            f"Critical FNR: {result.false_negative_rate_critical:.2%} | "
            f"Safety OK: {meets_safety}"
        )

        return result

    def _update_class_metrics(
        self,
        metrics: Dict[str, PerClassMetrics],
        true_label: str,
        pred_label: str,
        true_failure: bool,
        pred_failure: bool
    ):
        """Update per-class metrics based on prediction."""
        # For each class, determine TP/TN/FP/FN
        for class_name, class_metrics in metrics.items():
            is_true_class = (true_label == class_name)
            is_pred_class = (pred_label == class_name)

            if is_true_class and is_pred_class:
                class_metrics.true_positives += 1
            elif not is_true_class and not is_pred_class:
                class_metrics.true_negatives += 1
            elif not is_true_class and is_pred_class:
                class_metrics.false_positives += 1
            elif is_true_class and not is_pred_class:
                class_metrics.false_negatives += 1

    def _calculate_overall_metrics(
        self,
        per_class_metrics: Dict[str, PerClassMetrics]
    ) -> Dict[str, float]:
        """Calculate macro-averaged overall metrics."""
        if not per_class_metrics:
            return {'accuracy': 0, 'precision': 0, 'recall': 0, 'f1': 0, 'f2': 0}

        accuracies = [m.accuracy for m in per_class_metrics.values()]
        precisions = [m.precision for m in per_class_metrics.values()]
        recalls = [m.recall for m in per_class_metrics.values()]
        f1s = [m.f1_score for m in per_class_metrics.values()]
        f2s = [m.f2_score for m in per_class_metrics.values()]

        return {
            'accuracy': np.mean(accuracies) if accuracies else 0,
            'precision': np.mean(precisions) if precisions else 0,
            'recall': np.mean(recalls) if recalls else 0,
            'f1': np.mean(f1s) if f1s else 0,
            'f2': np.mean(f2s) if f2s else 0,
        }

    def _calculate_safety_metrics(
        self,
        per_class_metrics: Dict[str, PerClassMetrics]
    ) -> Dict[str, float]:
        """Calculate safety-critical metrics."""
        critical_recalls = []
        critical_fnrs = []
        high_fnrs = []

        for class_name, metrics in per_class_metrics.items():
            criticality = SYSTEM_CRITICALITY_MAP.get(class_name, 'medium')

            if criticality == 'critical':
                critical_recalls.append(metrics.recall)
                critical_fnrs.append(metrics.false_negative_rate)
            elif criticality == 'high':
                high_fnrs.append(metrics.false_negative_rate)

        return {
            'critical_recall': np.mean(critical_recalls) if critical_recalls else 1.0,
            'fnr_critical': np.mean(critical_fnrs) if critical_fnrs else 0.0,
            'fnr_high': np.mean(high_fnrs) if high_fnrs else 0.0,
        }

    def _calculate_calibration_error(
        self,
        predicted_probs: List[float],
        actual_outcomes: List[int]
    ) -> float:
        """Calculate Expected Calibration Error (ECE)."""
        if not predicted_probs or len(predicted_probs) != len(actual_outcomes):
            return 1.0  # Maximum error if no data

        n_bins = 10
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0

        for i in range(n_bins):
            bin_lower, bin_upper = bin_boundaries[i], bin_boundaries[i + 1]

            # Find predictions in this bin
            in_bin = [
                (p, a) for p, a in zip(predicted_probs, actual_outcomes)
                if bin_lower <= p < bin_upper
            ]

            if in_bin:
                avg_confidence = np.mean([p for p, a in in_bin])
                avg_accuracy = np.mean([a for p, a in in_bin])
                bin_weight = len(in_bin) / len(predicted_probs)
                ece += bin_weight * abs(avg_accuracy - avg_confidence)

        return ece

    def _check_safety_requirements(
        self,
        per_class_metrics: Dict[str, PerClassMetrics]
    ) -> Tuple[bool, List[str]]:
        """Check if model meets safety requirements."""
        violations = []

        for class_name, metrics in per_class_metrics.items():
            criticality = SYSTEM_CRITICALITY_MAP.get(class_name, 'medium')

            # Check false negative rate
            max_fnr = MAX_FALSE_NEGATIVE_RATES.get(criticality, 0.10)
            if metrics.false_negative_rate > max_fnr:
                violations.append(
                    f"{class_name}: FNR {metrics.false_negative_rate:.1%} > "
                    f"max allowed {max_fnr:.1%} for {criticality} systems"
                )

            # Check recall
            min_recall = MIN_RECALL_REQUIREMENTS.get(criticality, 0.90)
            if metrics.recall < min_recall:
                violations.append(
                    f"{class_name}: Recall {metrics.recall:.1%} < "
                    f"min required {min_recall:.1%} for {criticality} systems"
                )

        meets_requirements = len(violations) == 0
        return meets_requirements, violations

    def _generate_hash(self, eval_id: str, timestamp: str, samples: int) -> str:
        """Generate integrity hash."""
        data = f"{eval_id}|{timestamp}|{samples}|{self.VERSION}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _save_evaluation(self, result: ModelEvaluationResult):
        """Save evaluation result to file."""
        try:
            # Convert to dict, handling dataclasses
            result_dict = {
                'model_name': result.model_name,
                'model_version': result.model_version,
                'architecture': result.architecture,
                'evaluation_timestamp': result.evaluation_timestamp,
                'evaluation_id': result.evaluation_id,
                'test_samples': result.test_samples,
                'unique_vehicles': result.unique_vehicles,
                'vehicle_makes': result.vehicle_makes,
                'vehicle_years_range': result.vehicle_years_range,
                'overall_accuracy': result.overall_accuracy,
                'macro_precision': result.macro_precision,
                'macro_recall': result.macro_recall,
                'macro_f1': result.macro_f1,
                'macro_f2': result.macro_f2,
                'per_class_metrics': {
                    name: {
                        'accuracy': m.accuracy,
                        'precision': m.precision,
                        'recall': m.recall,
                        'f1_score': m.f1_score,
                        'f2_score': m.f2_score,
                        'false_negative_rate': m.false_negative_rate,
                        'tp': m.true_positives,
                        'tn': m.true_negatives,
                        'fp': m.false_positives,
                        'fn': m.false_negatives,
                    }
                    for name, m in result.per_class_metrics.items()
                },
                'critical_system_recall': result.critical_system_recall,
                'false_negative_rate_critical': result.false_negative_rate_critical,
                'false_negative_rate_high': result.false_negative_rate_high,
                'confusion_matrix': result.confusion_matrix,
                'class_labels': result.class_labels,
                'calibration_error': result.calibration_error,
                'is_well_calibrated': result.is_well_calibrated,
                'meets_safety_requirements': result.meets_safety_requirements,
                'safety_violations': result.safety_violations,
                'evaluation_hash': result.evaluation_hash,
            }

            file_path = self.evaluation_dir / f"{result.evaluation_id}.json"
            with open(file_path, 'w') as f:
                json.dump(result_dict, f, indent=2)

            logger.info(f"Saved evaluation: {file_path}")

        except Exception as e:
            logger.error(f"Failed to save evaluation: {e}")

    def compare_models(
        self,
        new_result: ModelEvaluationResult,
        production_result: ModelEvaluationResult
    ) -> Dict[str, Any]:
        """
        Compare new model against production model.

        Returns comparison with safety-focused analysis.
        """
        comparison = {
            'new_model': new_result.model_name,
            'production_model': production_result.model_name,
            'timestamp': datetime.now().isoformat(),

            # Accuracy comparison
            'accuracy_delta': new_result.overall_accuracy - production_result.overall_accuracy,
            'f2_delta': new_result.macro_f2 - production_result.macro_f2,

            # Safety comparison (CRITICAL)
            'critical_fnr_delta': (
                new_result.false_negative_rate_critical -
                production_result.false_negative_rate_critical
            ),
            'critical_recall_delta': (
                new_result.critical_system_recall -
                production_result.critical_system_recall
            ),

            # Decisions
            'is_improvement': False,
            'is_safe_to_deploy': False,
            'deployment_blocked_reasons': [],
        }

        # Check if new model is better
        if new_result.macro_f2 > production_result.macro_f2:
            comparison['is_improvement'] = True

        # Check if safe to deploy
        blocked_reasons = []

        # Block if regression on safety metrics
        if new_result.false_negative_rate_critical > production_result.false_negative_rate_critical:
            blocked_reasons.append(
                f"Critical FNR regression: {new_result.false_negative_rate_critical:.2%} > "
                f"{production_result.false_negative_rate_critical:.2%}"
            )

        if new_result.critical_system_recall < production_result.critical_system_recall:
            blocked_reasons.append(
                f"Critical recall regression: {new_result.critical_system_recall:.2%} < "
                f"{production_result.critical_system_recall:.2%}"
            )

        # Block if doesn't meet safety requirements
        if not new_result.meets_safety_requirements:
            blocked_reasons.extend(new_result.safety_violations)

        comparison['deployment_blocked_reasons'] = blocked_reasons
        comparison['is_safe_to_deploy'] = len(blocked_reasons) == 0

        return comparison

    def get_evaluation_summary(self) -> Dict[str, Any]:
        """Get summary of all evaluations."""
        if not self.evaluation_history:
            return {'message': 'No evaluations performed yet'}

        latest = self.evaluation_history[-1]
        return {
            'total_evaluations': len(self.evaluation_history),
            'latest_evaluation': {
                'model': latest.model_name,
                'version': latest.model_version,
                'timestamp': latest.evaluation_timestamp,
                'accuracy': latest.overall_accuracy,
                'f2_score': latest.macro_f2,
                'critical_fnr': latest.false_negative_rate_critical,
                'meets_safety': latest.meets_safety_requirements,
            },
            'evaluator_version': self.VERSION,
        }


# =============================================================================
# SINGLETON AND HELPERS
# =============================================================================

_model_evaluator: Optional[RealModelEvaluator] = None


def get_model_evaluator() -> RealModelEvaluator:
    """Get the global model evaluator instance."""
    global _model_evaluator
    if _model_evaluator is None:
        _model_evaluator = RealModelEvaluator()
    return _model_evaluator


def create_test_case(
    test_id: str,
    obd_sequence: List[Dict],
    true_failure_type: str,
    true_failure_occurred: bool,
    vehicle_info: Optional[Dict] = None
) -> EvaluationTestCase:
    """Helper to create a test case for evaluation."""
    vehicle_info = vehicle_info or {}
    return EvaluationTestCase(
        test_id=test_id,
        vehicle_id=vehicle_info.get('vehicle_id'),
        vehicle_make=vehicle_info.get('make'),
        vehicle_model=vehicle_info.get('model'),
        vehicle_year=vehicle_info.get('year'),
        obd_sequence=obd_sequence,
        true_failure_type=true_failure_type,
        true_failure_occurred=true_failure_occurred,
        true_days_to_failure=vehicle_info.get('days_to_failure')
    )
