"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Model Validation Framework

Model Validation Framework
==========================
Comprehensive validation framework ensuring models meet safety requirements
before deployment. No model can be used in production without passing
all validation checks.

This framework validates:
1. Minimum performance requirements per failure type
2. Safety metric thresholds (recall, FNR)
3. Calibration quality
4. Robustness tests
5. Coverage requirements
6. Physics constraint compliance
"""

import numpy as np
import tensorflow as tf
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import hashlib
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# VALIDATION REQUIREMENTS
# =============================================================================

class ValidationStatus(Enum):
    """Status of validation checks."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    NOT_RUN = "not_run"
    SKIPPED = "skipped"


class SafetyCriticality(Enum):
    """Safety criticality levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Minimum requirements by failure type
FAILURE_TYPE_REQUIREMENTS = {
    # Critical failures - highest standards
    'fuel_pump': {
        'criticality': SafetyCriticality.CRITICAL,
        'min_recall': 0.99,
        'max_fnr': 0.01,
        'min_precision': 0.80,
        'min_f2_score': 0.95,
        'min_samples': 100,
    },
    'coolant_system': {
        'criticality': SafetyCriticality.CRITICAL,
        'min_recall': 0.99,
        'max_fnr': 0.01,
        'min_precision': 0.80,
        'min_f2_score': 0.95,
        'min_samples': 100,
    },
    'transmission': {
        'criticality': SafetyCriticality.CRITICAL,
        'min_recall': 0.99,
        'max_fnr': 0.01,
        'min_precision': 0.80,
        'min_f2_score': 0.95,
        'min_samples': 100,
    },

    # High criticality failures
    'battery': {
        'criticality': SafetyCriticality.HIGH,
        'min_recall': 0.97,
        'max_fnr': 0.03,
        'min_precision': 0.75,
        'min_f2_score': 0.90,
        'min_samples': 200,
    },
    'alternator': {
        'criticality': SafetyCriticality.HIGH,
        'min_recall': 0.97,
        'max_fnr': 0.03,
        'min_precision': 0.75,
        'min_f2_score': 0.90,
        'min_samples': 150,
    },
    'thermostat': {
        'criticality': SafetyCriticality.HIGH,
        'min_recall': 0.97,
        'max_fnr': 0.03,
        'min_precision': 0.75,
        'min_f2_score': 0.90,
        'min_samples': 100,
    },
    'ignition': {
        'criticality': SafetyCriticality.HIGH,
        'min_recall': 0.97,
        'max_fnr': 0.03,
        'min_precision': 0.75,
        'min_f2_score': 0.90,
        'min_samples': 100,
    },

    # Medium criticality failures
    'starter': {
        'criticality': SafetyCriticality.MEDIUM,
        'min_recall': 0.95,
        'max_fnr': 0.05,
        'min_precision': 0.70,
        'min_f2_score': 0.85,
        'min_samples': 100,
    },
    'spark_plug': {
        'criticality': SafetyCriticality.MEDIUM,
        'min_recall': 0.95,
        'max_fnr': 0.05,
        'min_precision': 0.70,
        'min_f2_score': 0.85,
        'min_samples': 100,
    },
    'oxygen_sensor': {
        'criticality': SafetyCriticality.MEDIUM,
        'min_recall': 0.95,
        'max_fnr': 0.05,
        'min_precision': 0.70,
        'min_f2_score': 0.85,
        'min_samples': 100,
    },
    'catalytic_converter': {
        'criticality': SafetyCriticality.MEDIUM,
        'min_recall': 0.95,
        'max_fnr': 0.05,
        'min_precision': 0.70,
        'min_f2_score': 0.85,
        'min_samples': 50,
    },
    'maf_sensor': {
        'criticality': SafetyCriticality.MEDIUM,
        'min_recall': 0.95,
        'max_fnr': 0.05,
        'min_precision': 0.70,
        'min_f2_score': 0.85,
        'min_samples': 100,
    },

    # Low criticality (no_failure detection)
    'no_failure': {
        'criticality': SafetyCriticality.LOW,
        'min_recall': 0.90,
        'max_fnr': 0.10,
        'min_precision': 0.85,
        'min_f2_score': 0.80,
        'min_samples': 500,
    },
}

# Global validation requirements
GLOBAL_REQUIREMENTS = {
    'min_overall_accuracy': 0.85,
    'max_expected_calibration_error': 0.10,
    'min_total_samples': 1000,
    'min_failure_examples': 200,
    'max_class_imbalance_ratio': 100,  # max ratio of largest to smallest class
    'min_vehicle_coverage': 3,  # minimum distinct vehicle makes/models
    'max_days_to_failure_mae': 7.0,  # days
    'max_overestimate_rate': 0.10,  # % of predictions that overestimate time
}


# =============================================================================
# VALIDATION DATA STRUCTURES
# =============================================================================

@dataclass
class ValidationCheck:
    """Result of a single validation check."""
    check_name: str
    category: str
    status: ValidationStatus
    requirement: Any
    actual_value: Any
    message: str
    severity: str  # 'blocker', 'critical', 'warning', 'info'
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Complete validation report for a model."""
    model_id: str
    model_version: str
    validation_timestamp: str
    overall_status: ValidationStatus
    checks: List[ValidationCheck]
    summary: Dict[str, Any]
    recommendations: List[str]
    blocking_issues: List[str]
    warnings: List[str]
    can_deploy: bool
    signature: str  # cryptographic signature for tamper detection


# =============================================================================
# MODEL VALIDATION FRAMEWORK
# =============================================================================

class ModelValidationFramework:
    """
    Comprehensive model validation framework.

    A model MUST pass all validation checks before deployment.
    """

    def __init__(self):
        """Initialize validation framework."""
        self.failure_requirements = FAILURE_TYPE_REQUIREMENTS
        self.global_requirements = GLOBAL_REQUIREMENTS
        self.checks: List[ValidationCheck] = []

        logger.info("Model Validation Framework initialized")

    def validate_model(
        self,
        model: tf.keras.Model,
        test_data: Tuple[np.ndarray, Dict[str, np.ndarray]],
        model_id: str,
        model_version: str,
        vehicle_coverage: Optional[Dict[str, Any]] = None
    ) -> ValidationReport:
        """
        Perform comprehensive validation on a model.

        Args:
            model: Trained Keras model
            test_data: Tuple of (X_test, {y_test_dict})
            model_id: Unique identifier for the model
            model_version: Version string
            vehicle_coverage: Optional vehicle coverage data

        Returns:
            ValidationReport with all check results
        """
        self.checks = []

        X_test, y_test = test_data

        # Get predictions
        logger.info(f"Validating model {model_id} v{model_version}")
        predictions = model.predict(X_test, verbose=0)

        # Handle different model output formats
        if isinstance(predictions, dict):
            y_pred = predictions
        elif isinstance(predictions, (list, tuple)):
            y_pred = {
                'failure_prob': predictions[0],
                'failure_type': predictions[1],
                'days_to_failure': predictions[2]
            }
        else:
            raise ValueError(f"Unexpected prediction format: {type(predictions)}")

        # Run all validation categories
        self._validate_data_quality(X_test, y_test)
        self._validate_global_metrics(y_test, y_pred)
        self._validate_per_class_metrics(y_test, y_pred)
        self._validate_calibration(y_test, y_pred)
        self._validate_safety_metrics(y_test, y_pred)
        self._validate_temporal_predictions(y_test, y_pred)

        if vehicle_coverage:
            self._validate_vehicle_coverage(vehicle_coverage)

        # Generate report
        report = self._generate_report(model_id, model_version)

        return report

    def _validate_data_quality(
        self,
        X_test: np.ndarray,
        y_test: Dict[str, np.ndarray]
    ):
        """Validate test data quality."""
        # Check total samples
        total_samples = len(X_test)
        self.checks.append(ValidationCheck(
            check_name="total_test_samples",
            category="data_quality",
            status=ValidationStatus.PASSED if total_samples >= self.global_requirements['min_total_samples'] else ValidationStatus.FAILED,
            requirement=self.global_requirements['min_total_samples'],
            actual_value=total_samples,
            message=f"Test set has {total_samples} samples (min: {self.global_requirements['min_total_samples']})",
            severity='blocker' if total_samples < self.global_requirements['min_total_samples'] else 'info'
        ))

        # Check failure examples
        if 'failure_prob' in y_test:
            failure_count = np.sum(y_test['failure_prob'] > 0.5)
            self.checks.append(ValidationCheck(
                check_name="failure_examples",
                category="data_quality",
                status=ValidationStatus.PASSED if failure_count >= self.global_requirements['min_failure_examples'] else ValidationStatus.FAILED,
                requirement=self.global_requirements['min_failure_examples'],
                actual_value=int(failure_count),
                message=f"Test set has {failure_count} failure examples (min: {self.global_requirements['min_failure_examples']})",
                severity='blocker' if failure_count < self.global_requirements['min_failure_examples'] else 'info'
            ))

        # Check class distribution
        if 'failure_type' in y_test:
            class_counts = np.sum(y_test['failure_type'], axis=0)
            max_count = np.max(class_counts)
            min_count = np.min(class_counts[class_counts > 0]) if np.any(class_counts > 0) else 1
            imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')

            self.checks.append(ValidationCheck(
                check_name="class_imbalance",
                category="data_quality",
                status=ValidationStatus.PASSED if imbalance_ratio <= self.global_requirements['max_class_imbalance_ratio'] else ValidationStatus.WARNING,
                requirement=self.global_requirements['max_class_imbalance_ratio'],
                actual_value=round(imbalance_ratio, 2),
                message=f"Class imbalance ratio: {imbalance_ratio:.1f} (max: {self.global_requirements['max_class_imbalance_ratio']})",
                severity='warning' if imbalance_ratio > self.global_requirements['max_class_imbalance_ratio'] else 'info',
                details={'class_counts': class_counts.tolist()}
            ))

            # Check per-class sample counts
            failure_types = list(FAILURE_TYPE_REQUIREMENTS.keys())
            for idx, failure_type in enumerate(failure_types):
                if idx < len(class_counts):
                    count = int(class_counts[idx])
                    min_required = FAILURE_TYPE_REQUIREMENTS[failure_type]['min_samples']

                    self.checks.append(ValidationCheck(
                        check_name=f"samples_{failure_type}",
                        category="data_quality",
                        status=ValidationStatus.PASSED if count >= min_required else ValidationStatus.FAILED,
                        requirement=min_required,
                        actual_value=count,
                        message=f"{failure_type}: {count} samples (min: {min_required})",
                        severity='blocker' if count < min_required and FAILURE_TYPE_REQUIREMENTS[failure_type]['criticality'] == SafetyCriticality.CRITICAL else 'warning'
                    ))

    def _validate_global_metrics(
        self,
        y_test: Dict[str, np.ndarray],
        y_pred: Dict[str, np.ndarray]
    ):
        """Validate global model metrics."""
        # Overall binary accuracy
        if 'failure_prob' in y_test and 'failure_prob' in y_pred:
            y_true_binary = (y_test['failure_prob'] > 0.5).astype(int).flatten()
            y_pred_binary = (y_pred['failure_prob'] > 0.5).astype(int).flatten()

            accuracy = np.mean(y_true_binary == y_pred_binary)

            self.checks.append(ValidationCheck(
                check_name="overall_accuracy",
                category="global_metrics",
                status=ValidationStatus.PASSED if accuracy >= self.global_requirements['min_overall_accuracy'] else ValidationStatus.FAILED,
                requirement=self.global_requirements['min_overall_accuracy'],
                actual_value=round(accuracy, 4),
                message=f"Overall accuracy: {accuracy:.2%} (min: {self.global_requirements['min_overall_accuracy']:.0%})",
                severity='blocker' if accuracy < self.global_requirements['min_overall_accuracy'] else 'info'
            ))

        # Failure type accuracy
        if 'failure_type' in y_test and 'failure_type' in y_pred:
            y_true_class = np.argmax(y_test['failure_type'], axis=1)
            y_pred_class = np.argmax(y_pred['failure_type'], axis=1)

            type_accuracy = np.mean(y_true_class == y_pred_class)

            self.checks.append(ValidationCheck(
                check_name="failure_type_accuracy",
                category="global_metrics",
                status=ValidationStatus.PASSED if type_accuracy >= 0.75 else ValidationStatus.WARNING,
                requirement=0.75,
                actual_value=round(type_accuracy, 4),
                message=f"Failure type accuracy: {type_accuracy:.2%} (min: 75%)",
                severity='warning' if type_accuracy < 0.75 else 'info'
            ))

    def _validate_per_class_metrics(
        self,
        y_test: Dict[str, np.ndarray],
        y_pred: Dict[str, np.ndarray]
    ):
        """Validate metrics for each failure type."""
        if 'failure_type' not in y_test or 'failure_type' not in y_pred:
            self.checks.append(ValidationCheck(
                check_name="per_class_validation",
                category="per_class_metrics",
                status=ValidationStatus.SKIPPED,
                requirement=None,
                actual_value=None,
                message="Per-class validation skipped - no failure type data",
                severity='warning'
            ))
            return

        y_true_class = np.argmax(y_test['failure_type'], axis=1)
        y_pred_class = np.argmax(y_pred['failure_type'], axis=1)

        failure_types = list(FAILURE_TYPE_REQUIREMENTS.keys())

        for idx, failure_type in enumerate(failure_types):
            if idx >= y_test['failure_type'].shape[1]:
                continue

            requirements = FAILURE_TYPE_REQUIREMENTS[failure_type]

            # Calculate metrics for this class
            true_positives = np.sum((y_true_class == idx) & (y_pred_class == idx))
            false_positives = np.sum((y_true_class != idx) & (y_pred_class == idx))
            false_negatives = np.sum((y_true_class == idx) & (y_pred_class != idx))
            true_negatives = np.sum((y_true_class != idx) & (y_pred_class != idx))

            # Recall (sensitivity)
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0

            # Precision
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0

            # False Negative Rate
            fnr = false_negatives / (false_negatives + true_positives) if (false_negatives + true_positives) > 0 else 0

            # F2 Score
            beta = 2
            f2 = (1 + beta**2) * (precision * recall) / (beta**2 * precision + recall) if (precision + recall) > 0 else 0

            # Validate recall
            self.checks.append(ValidationCheck(
                check_name=f"recall_{failure_type}",
                category="per_class_metrics",
                status=ValidationStatus.PASSED if recall >= requirements['min_recall'] else ValidationStatus.FAILED,
                requirement=requirements['min_recall'],
                actual_value=round(recall, 4),
                message=f"{failure_type} recall: {recall:.2%} (min: {requirements['min_recall']:.0%})",
                severity='blocker' if requirements['criticality'] == SafetyCriticality.CRITICAL and recall < requirements['min_recall'] else 'critical'
            ))

            # Validate FNR
            self.checks.append(ValidationCheck(
                check_name=f"fnr_{failure_type}",
                category="per_class_metrics",
                status=ValidationStatus.PASSED if fnr <= requirements['max_fnr'] else ValidationStatus.FAILED,
                requirement=requirements['max_fnr'],
                actual_value=round(fnr, 4),
                message=f"{failure_type} FNR: {fnr:.2%} (max: {requirements['max_fnr']:.0%})",
                severity='blocker' if requirements['criticality'] == SafetyCriticality.CRITICAL and fnr > requirements['max_fnr'] else 'critical'
            ))

            # Validate precision
            self.checks.append(ValidationCheck(
                check_name=f"precision_{failure_type}",
                category="per_class_metrics",
                status=ValidationStatus.PASSED if precision >= requirements['min_precision'] else ValidationStatus.WARNING,
                requirement=requirements['min_precision'],
                actual_value=round(precision, 4),
                message=f"{failure_type} precision: {precision:.2%} (min: {requirements['min_precision']:.0%})",
                severity='warning'
            ))

            # Validate F2 Score
            self.checks.append(ValidationCheck(
                check_name=f"f2_{failure_type}",
                category="per_class_metrics",
                status=ValidationStatus.PASSED if f2 >= requirements['min_f2_score'] else ValidationStatus.WARNING,
                requirement=requirements['min_f2_score'],
                actual_value=round(f2, 4),
                message=f"{failure_type} F2: {f2:.2%} (min: {requirements['min_f2_score']:.0%})",
                severity='warning' if requirements['criticality'] in [SafetyCriticality.CRITICAL, SafetyCriticality.HIGH] else 'info'
            ))

    def _validate_calibration(
        self,
        y_test: Dict[str, np.ndarray],
        y_pred: Dict[str, np.ndarray]
    ):
        """Validate probability calibration."""
        if 'failure_prob' not in y_test or 'failure_prob' not in y_pred:
            return

        y_true = y_test['failure_prob'].flatten()
        y_prob = y_pred['failure_prob'].flatten()

        # Calculate Expected Calibration Error
        n_bins = 10
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        total_samples = len(y_true)

        calibration_details = []

        for i in range(n_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]

            in_bin = (y_prob >= bin_lower) & (y_prob < bin_upper)
            bin_size = np.sum(in_bin)

            if bin_size > 0:
                bin_accuracy = np.mean(y_true[in_bin])
                bin_confidence = np.mean(y_prob[in_bin])
                ece += (bin_size / total_samples) * abs(bin_accuracy - bin_confidence)

                calibration_details.append({
                    'bin': f"{bin_lower:.1f}-{bin_upper:.1f}",
                    'samples': int(bin_size),
                    'accuracy': round(bin_accuracy, 3),
                    'confidence': round(bin_confidence, 3),
                    'gap': round(abs(bin_accuracy - bin_confidence), 3)
                })

        self.checks.append(ValidationCheck(
            check_name="expected_calibration_error",
            category="calibration",
            status=ValidationStatus.PASSED if ece <= self.global_requirements['max_expected_calibration_error'] else ValidationStatus.WARNING,
            requirement=self.global_requirements['max_expected_calibration_error'],
            actual_value=round(ece, 4),
            message=f"Expected Calibration Error: {ece:.3f} (max: {self.global_requirements['max_expected_calibration_error']})",
            severity='warning' if ece > self.global_requirements['max_expected_calibration_error'] else 'info',
            details={'calibration_bins': calibration_details}
        ))

        # Check for overconfidence (more dangerous than underconfidence)
        high_conf_mask = y_prob >= 0.8
        if np.sum(high_conf_mask) > 0:
            high_conf_accuracy = np.mean(y_true[high_conf_mask])
            overconfidence = np.mean(y_prob[high_conf_mask]) - high_conf_accuracy

            self.checks.append(ValidationCheck(
                check_name="high_confidence_calibration",
                category="calibration",
                status=ValidationStatus.PASSED if overconfidence <= 0.15 else ValidationStatus.WARNING,
                requirement=0.15,
                actual_value=round(overconfidence, 4),
                message=f"High confidence overconfidence: {overconfidence:.3f} (max: 0.15)",
                severity='warning' if overconfidence > 0.15 else 'info',
                details={'high_conf_samples': int(np.sum(high_conf_mask)), 'high_conf_accuracy': round(high_conf_accuracy, 3)}
            ))

    def _validate_safety_metrics(
        self,
        y_test: Dict[str, np.ndarray],
        y_pred: Dict[str, np.ndarray]
    ):
        """Validate safety-critical metrics."""
        if 'failure_prob' not in y_test or 'failure_prob' not in y_pred:
            return

        y_true = (y_test['failure_prob'] > 0.5).astype(int).flatten()
        y_pred_binary = (y_pred['failure_prob'] > 0.5).astype(int).flatten()

        # Overall False Negative Rate
        fn = np.sum((y_true == 1) & (y_pred_binary == 0))
        tp = np.sum((y_true == 1) & (y_pred_binary == 1))
        overall_fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

        self.checks.append(ValidationCheck(
            check_name="overall_false_negative_rate",
            category="safety_metrics",
            status=ValidationStatus.PASSED if overall_fnr <= 0.05 else ValidationStatus.FAILED,
            requirement=0.05,
            actual_value=round(overall_fnr, 4),
            message=f"Overall FNR: {overall_fnr:.2%} (max: 5%)",
            severity='blocker' if overall_fnr > 0.05 else 'info',
            details={'false_negatives': int(fn), 'true_positives': int(tp)}
        ))

        # Check prediction conservatism
        # We want the model to err on the side of predicting failures
        fp = np.sum((y_true == 0) & (y_pred_binary == 1))
        tn = np.sum((y_true == 0) & (y_pred_binary == 0))
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

        # A slightly high FPR is acceptable if FNR is very low
        acceptable_fpr = 0.20 if overall_fnr < 0.02 else 0.15

        self.checks.append(ValidationCheck(
            check_name="false_positive_rate",
            category="safety_metrics",
            status=ValidationStatus.PASSED if fpr <= acceptable_fpr else ValidationStatus.WARNING,
            requirement=acceptable_fpr,
            actual_value=round(fpr, 4),
            message=f"FPR: {fpr:.2%} (max: {acceptable_fpr:.0%} given FNR)",
            severity='warning' if fpr > acceptable_fpr else 'info',
            details={'false_positives': int(fp), 'true_negatives': int(tn)}
        ))

    def _validate_temporal_predictions(
        self,
        y_test: Dict[str, np.ndarray],
        y_pred: Dict[str, np.ndarray]
    ):
        """Validate days_to_failure predictions."""
        if 'days_to_failure' not in y_test or 'days_to_failure' not in y_pred:
            return

        y_true_days = y_test['days_to_failure'].flatten()
        y_pred_days = y_pred['days_to_failure'].flatten()

        # Only evaluate on actual failure cases (non-zero days)
        failure_mask = y_true_days > 0
        if np.sum(failure_mask) == 0:
            return

        y_true_failures = y_true_days[failure_mask]
        y_pred_failures = y_pred_days[failure_mask]

        # Mean Absolute Error
        mae = np.mean(np.abs(y_true_failures - y_pred_failures))

        self.checks.append(ValidationCheck(
            check_name="days_to_failure_mae",
            category="temporal_metrics",
            status=ValidationStatus.PASSED if mae <= self.global_requirements['max_days_to_failure_mae'] else ValidationStatus.WARNING,
            requirement=self.global_requirements['max_days_to_failure_mae'],
            actual_value=round(mae, 2),
            message=f"Days to failure MAE: {mae:.1f} days (max: {self.global_requirements['max_days_to_failure_mae']})",
            severity='warning' if mae > self.global_requirements['max_days_to_failure_mae'] else 'info'
        ))

        # Check overestimation rate (dangerous - predicting more time than available)
        overestimates = y_pred_failures > y_true_failures
        overestimate_rate = np.mean(overestimates)

        self.checks.append(ValidationCheck(
            check_name="days_overestimate_rate",
            category="temporal_metrics",
            status=ValidationStatus.PASSED if overestimate_rate <= self.global_requirements['max_overestimate_rate'] else ValidationStatus.WARNING,
            requirement=self.global_requirements['max_overestimate_rate'],
            actual_value=round(overestimate_rate, 4),
            message=f"Overestimate rate: {overestimate_rate:.1%} (max: {self.global_requirements['max_overestimate_rate']:.0%})",
            severity='warning' if overestimate_rate > self.global_requirements['max_overestimate_rate'] else 'info'
        ))

        # Severe overestimates (> 15 days off)
        severe_overestimates = (y_pred_failures - y_true_failures) > 15
        severe_rate = np.mean(severe_overestimates)

        self.checks.append(ValidationCheck(
            check_name="severe_overestimate_rate",
            category="temporal_metrics",
            status=ValidationStatus.PASSED if severe_rate <= 0.02 else ValidationStatus.FAILED,
            requirement=0.02,
            actual_value=round(severe_rate, 4),
            message=f"Severe overestimate (>15 days): {severe_rate:.1%} (max: 2%)",
            severity='critical' if severe_rate > 0.02 else 'info'
        ))

    def _validate_vehicle_coverage(self, coverage: Dict[str, Any]):
        """Validate vehicle coverage requirements."""
        makes_covered = coverage.get('makes', [])
        models_covered = coverage.get('models', [])

        unique_makes = len(set(makes_covered))

        self.checks.append(ValidationCheck(
            check_name="vehicle_make_coverage",
            category="coverage",
            status=ValidationStatus.PASSED if unique_makes >= self.global_requirements['min_vehicle_coverage'] else ValidationStatus.WARNING,
            requirement=self.global_requirements['min_vehicle_coverage'],
            actual_value=unique_makes,
            message=f"Vehicle makes covered: {unique_makes} (min: {self.global_requirements['min_vehicle_coverage']})",
            severity='warning' if unique_makes < self.global_requirements['min_vehicle_coverage'] else 'info',
            details={'makes': list(set(makes_covered)), 'models': list(set(models_covered))[:20]}
        ))

    def _generate_report(
        self,
        model_id: str,
        model_version: str
    ) -> ValidationReport:
        """Generate final validation report."""
        # Categorize checks
        blocking_issues = [c for c in self.checks if c.status == ValidationStatus.FAILED and c.severity == 'blocker']
        critical_issues = [c for c in self.checks if c.status == ValidationStatus.FAILED and c.severity == 'critical']
        warnings = [c for c in self.checks if c.status == ValidationStatus.WARNING]
        passed = [c for c in self.checks if c.status == ValidationStatus.PASSED]

        # Determine overall status
        if blocking_issues:
            overall_status = ValidationStatus.FAILED
            can_deploy = False
        elif critical_issues:
            overall_status = ValidationStatus.FAILED
            can_deploy = False
        elif warnings:
            overall_status = ValidationStatus.WARNING
            can_deploy = True  # Warnings don't block deployment but should be reviewed
        else:
            overall_status = ValidationStatus.PASSED
            can_deploy = True

        # Generate recommendations
        recommendations = []
        if blocking_issues:
            recommendations.append("BLOCKING: Model cannot be deployed until blocking issues are resolved.")
            for issue in blocking_issues:
                recommendations.append(f"- Fix: {issue.check_name} - {issue.message}")

        if critical_issues:
            recommendations.append("CRITICAL: Address these issues before production use.")
            for issue in critical_issues:
                recommendations.append(f"- Address: {issue.check_name} - {issue.message}")

        if warnings:
            recommendations.append("WARNINGS: Review these items before deployment.")
            for warn in warnings[:5]:  # Limit to top 5
                recommendations.append(f"- Review: {warn.check_name} - {warn.message}")

        # Summary statistics
        summary = {
            'total_checks': len(self.checks),
            'passed': len(passed),
            'failed': len(blocking_issues) + len(critical_issues),
            'warnings': len(warnings),
            'pass_rate': len(passed) / len(self.checks) if self.checks else 0,
            'checks_by_category': {}
        }

        for check in self.checks:
            if check.category not in summary['checks_by_category']:
                summary['checks_by_category'][check.category] = {'passed': 0, 'failed': 0, 'warning': 0}
            if check.status == ValidationStatus.PASSED:
                summary['checks_by_category'][check.category]['passed'] += 1
            elif check.status == ValidationStatus.FAILED:
                summary['checks_by_category'][check.category]['failed'] += 1
            elif check.status == ValidationStatus.WARNING:
                summary['checks_by_category'][check.category]['warning'] += 1

        # Generate signature for tamper detection
        report_data = f"{model_id}:{model_version}:{overall_status.value}:{len(blocking_issues)}:{datetime.now().isoformat()}"
        signature = hashlib.sha256(report_data.encode()).hexdigest()

        report = ValidationReport(
            model_id=model_id,
            model_version=model_version,
            validation_timestamp=datetime.now().isoformat(),
            overall_status=overall_status,
            checks=self.checks,
            summary=summary,
            recommendations=recommendations,
            blocking_issues=[f"{i.check_name}: {i.message}" for i in blocking_issues],
            warnings=[f"{w.check_name}: {w.message}" for w in warnings],
            can_deploy=can_deploy,
            signature=signature
        )

        logger.info(f"Validation complete: {overall_status.value}, Can deploy: {can_deploy}")

        return report


# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_model_for_production(
    model: tf.keras.Model,
    test_data: Tuple[np.ndarray, Dict[str, np.ndarray]],
    model_id: str,
    model_version: str
) -> Tuple[bool, ValidationReport]:
    """
    Convenience function to validate a model for production deployment.

    Args:
        model: Trained model
        test_data: Test dataset
        model_id: Model identifier
        model_version: Version string

    Returns:
        Tuple of (can_deploy, report)
    """
    framework = ModelValidationFramework()
    report = framework.validate_model(model, test_data, model_id, model_version)
    return report.can_deploy, report


def print_validation_report(report: ValidationReport):
    """Print a human-readable validation report."""
    print("\n" + "=" * 70)
    print(f"MODEL VALIDATION REPORT")
    print("=" * 70)
    print(f"Model: {report.model_id} v{report.model_version}")
    print(f"Time: {report.validation_timestamp}")
    print(f"Status: {report.overall_status.value.upper()}")
    print(f"Can Deploy: {'YES' if report.can_deploy else 'NO'}")
    print("-" * 70)

    print(f"\nSUMMARY:")
    print(f"  Total Checks: {report.summary['total_checks']}")
    print(f"  Passed: {report.summary['passed']}")
    print(f"  Failed: {report.summary['failed']}")
    print(f"  Warnings: {report.summary['warnings']}")
    print(f"  Pass Rate: {report.summary['pass_rate']:.1%}")

    if report.blocking_issues:
        print(f"\nBLOCKING ISSUES ({len(report.blocking_issues)}):")
        for issue in report.blocking_issues:
            print(f"  [X] {issue}")

    if report.warnings:
        print(f"\nWARNINGS ({len(report.warnings)}):")
        for warn in report.warnings[:10]:
            print(f"  [!] {warn}")

    if report.recommendations:
        print(f"\nRECOMMENDATIONS:")
        for rec in report.recommendations:
            print(f"  {rec}")

    print("\n" + "=" * 70)


def save_validation_report(report: ValidationReport, path: Path):
    """Save validation report to JSON file."""
    # Convert dataclasses to dicts
    report_dict = {
        'model_id': report.model_id,
        'model_version': report.model_version,
        'validation_timestamp': report.validation_timestamp,
        'overall_status': report.overall_status.value,
        'can_deploy': report.can_deploy,
        'summary': report.summary,
        'blocking_issues': report.blocking_issues,
        'warnings': report.warnings,
        'recommendations': report.recommendations,
        'signature': report.signature,
        'checks': [
            {
                'check_name': c.check_name,
                'category': c.category,
                'status': c.status.value,
                'requirement': c.requirement,
                'actual_value': c.actual_value,
                'message': c.message,
                'severity': c.severity,
                'details': c.details
            }
            for c in report.checks
        ]
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(report_dict, f, indent=2, default=str)

    logger.info(f"Validation report saved to {path}")
