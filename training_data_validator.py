"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Training Data Validator

Training Data Validator
=======================
Validates training data quality before model training.
Ensures data meets minimum requirements for safety-critical predictions.

This module validates:
1. Data completeness and integrity
2. Label quality and balance
3. Temporal consistency
4. Feature distributions
5. Outlier detection
6. Data provenance tracking
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, Set
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

class DataQualityLevel(Enum):
    """Quality level of training data."""
    PRODUCTION = "production"      # Meets all requirements for production
    DEVELOPMENT = "development"    # Acceptable for development/testing
    INSUFFICIENT = "insufficient"  # Does not meet minimum requirements
    INVALID = "invalid"            # Data has critical issues


# Feature names expected in training data
EXPECTED_FEATURES = [
    'rpm', 'speed', 'coolant_temp', 'engine_load', 'intake_temp',
    'maf', 'throttle_pos', 'fuel_pressure', 'timing_advance',
    'short_fuel_trim', 'long_fuel_trim', 'voltage',
    'rpm_stability', 'load_stability', 'temp_rate_of_change', 'voltage_trend'
]

# Valid ranges for each feature (for OBD data)
FEATURE_VALID_RANGES = {
    'rpm': (0, 10000),
    'speed': (0, 300),
    'coolant_temp': (-40, 150),
    'engine_load': (0, 100),
    'intake_temp': (-40, 100),
    'maf': (0, 700),
    'throttle_pos': (0, 100),
    'fuel_pressure': (0, 800),
    'timing_advance': (-60, 60),
    'short_fuel_trim': (-50, 50),
    'long_fuel_trim': (-50, 50),
    'voltage': (0, 20),
    'rpm_stability': (0, 5000),
    'load_stability': (0, 100),
    'temp_rate_of_change': (-10, 10),
    'voltage_trend': (-5, 5),
}

# Failure type labels
FAILURE_TYPES = [
    'battery', 'alternator', 'starter', 'fuel_pump', 'spark_plug',
    'oxygen_sensor', 'catalytic_converter', 'maf_sensor', 'thermostat',
    'coolant_system', 'transmission', 'ignition', 'no_failure'
]

# Minimum requirements
MIN_REQUIREMENTS = {
    'production': {
        'total_samples': 10000,
        'min_samples_per_class': 100,
        'min_failure_samples': 1000,
        'max_missing_ratio': 0.01,
        'max_duplicate_ratio': 0.05,
        'min_vehicle_count': 50,
        'min_time_span_days': 90,
        'max_class_imbalance': 50,
    },
    'development': {
        'total_samples': 1000,
        'min_samples_per_class': 20,
        'min_failure_samples': 100,
        'max_missing_ratio': 0.05,
        'max_duplicate_ratio': 0.10,
        'min_vehicle_count': 5,
        'min_time_span_days': 30,
        'max_class_imbalance': 100,
    }
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DataIssue:
    """A single data quality issue."""
    issue_type: str
    severity: str  # 'critical', 'warning', 'info'
    description: str
    affected_samples: int
    affected_features: List[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class FeatureStatistics:
    """Statistics for a single feature."""
    name: str
    count: int
    missing_count: int
    missing_ratio: float
    min_value: float
    max_value: float
    mean: float
    std: float
    median: float
    out_of_range_count: int
    out_of_range_ratio: float


@dataclass
class LabelStatistics:
    """Statistics for labels."""
    class_name: str
    count: int
    ratio: float


@dataclass
class DataValidationReport:
    """Complete data validation report."""
    validation_id: str
    validation_timestamp: str
    quality_level: DataQualityLevel
    total_samples: int
    total_features: int
    issues: List[DataIssue]
    feature_stats: List[FeatureStatistics]
    label_stats: List[LabelStatistics]
    summary: Dict[str, Any]
    data_hash: str
    can_train: bool
    recommendations: List[str]


# =============================================================================
# TRAINING DATA VALIDATOR
# =============================================================================

class TrainingDataValidator:
    """
    Validates training data quality for safety-critical model training.

    CRITICAL: No model should be trained on data that fails validation.
    """

    def __init__(self, target_level: str = 'production'):
        """
        Initialize validator.

        Args:
            target_level: 'production' or 'development'
        """
        self.target_level = target_level
        self.requirements = MIN_REQUIREMENTS.get(target_level, MIN_REQUIREMENTS['production'])
        self.issues: List[DataIssue] = []
        self.feature_stats: List[FeatureStatistics] = []
        self.label_stats: List[LabelStatistics] = []

        logger.info(f"Training Data Validator initialized for {target_level} level")

    def validate(
        self,
        X: np.ndarray,
        y: Dict[str, np.ndarray],
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataValidationReport:
        """
        Validate training data.

        Args:
            X: Feature array (samples, timesteps, features) or (samples, features)
            y: Dictionary of label arrays
            metadata: Optional metadata (vehicle_ids, timestamps, etc.)

        Returns:
            DataValidationReport
        """
        self.issues = []
        self.feature_stats = []
        self.label_stats = []

        logger.info(f"Validating training data: {X.shape}")

        # Generate data hash for tracking
        data_hash = self._compute_data_hash(X, y)

        # Run all validation checks
        self._validate_shape(X, y)
        self._validate_features(X)
        self._validate_labels(y)
        self._validate_missing_values(X)
        self._validate_duplicates(X)
        self._validate_outliers(X)
        self._validate_temporal_consistency(X)

        if metadata:
            self._validate_metadata(metadata)

        # Generate report
        report = self._generate_report(X, y, data_hash)

        return report

    def _compute_data_hash(self, X: np.ndarray, y: Dict[str, np.ndarray]) -> str:
        """Compute hash of data for tracking."""
        hash_input = f"{X.shape}:{X.mean():.6f}:{X.std():.6f}"
        for key, arr in y.items():
            hash_input += f":{key}:{arr.shape}:{arr.mean():.6f}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _validate_shape(self, X: np.ndarray, y: Dict[str, np.ndarray]):
        """Validate data shapes."""
        total_samples = X.shape[0]

        # Check total samples
        if total_samples < self.requirements['total_samples']:
            self.issues.append(DataIssue(
                issue_type="insufficient_samples",
                severity="critical",
                description=f"Only {total_samples} samples, need {self.requirements['total_samples']}",
                affected_samples=total_samples,
                recommendation=f"Collect at least {self.requirements['total_samples'] - total_samples} more samples"
            ))

        # Check feature count
        if len(X.shape) == 3:
            n_features = X.shape[2]
        else:
            n_features = X.shape[1]

        if n_features != len(EXPECTED_FEATURES):
            self.issues.append(DataIssue(
                issue_type="feature_count_mismatch",
                severity="critical",
                description=f"Expected {len(EXPECTED_FEATURES)} features, got {n_features}",
                affected_samples=total_samples,
                recommendation="Ensure all expected features are present"
            ))

        # Check label shapes match
        for key, arr in y.items():
            if arr.shape[0] != total_samples:
                self.issues.append(DataIssue(
                    issue_type="label_shape_mismatch",
                    severity="critical",
                    description=f"Label '{key}' has {arr.shape[0]} samples, X has {total_samples}",
                    affected_samples=abs(arr.shape[0] - total_samples),
                    recommendation="Ensure X and y have matching sample counts"
                ))

    def _validate_features(self, X: np.ndarray):
        """Validate feature distributions."""
        # Reshape if 3D (samples, timesteps, features)
        if len(X.shape) == 3:
            X_flat = X.reshape(-1, X.shape[2])
        else:
            X_flat = X

        n_features = X_flat.shape[1]

        for i in range(min(n_features, len(EXPECTED_FEATURES))):
            feature_name = EXPECTED_FEATURES[i] if i < len(EXPECTED_FEATURES) else f"feature_{i}"
            feature_data = X_flat[:, i]

            # Calculate statistics
            valid_data = feature_data[~np.isnan(feature_data)]
            missing_count = np.sum(np.isnan(feature_data))
            missing_ratio = missing_count / len(feature_data)

            # Check valid range
            valid_range = FEATURE_VALID_RANGES.get(feature_name, (float('-inf'), float('inf')))
            out_of_range = np.sum((valid_data < valid_range[0]) | (valid_data > valid_range[1]))
            out_of_range_ratio = out_of_range / len(valid_data) if len(valid_data) > 0 else 0

            stats = FeatureStatistics(
                name=feature_name,
                count=len(feature_data),
                missing_count=int(missing_count),
                missing_ratio=float(missing_ratio),
                min_value=float(np.min(valid_data)) if len(valid_data) > 0 else 0,
                max_value=float(np.max(valid_data)) if len(valid_data) > 0 else 0,
                mean=float(np.mean(valid_data)) if len(valid_data) > 0 else 0,
                std=float(np.std(valid_data)) if len(valid_data) > 0 else 0,
                median=float(np.median(valid_data)) if len(valid_data) > 0 else 0,
                out_of_range_count=int(out_of_range),
                out_of_range_ratio=float(out_of_range_ratio)
            )
            self.feature_stats.append(stats)

            # Report issues
            if missing_ratio > 0.1:
                self.issues.append(DataIssue(
                    issue_type="high_missing_ratio",
                    severity="warning",
                    description=f"Feature '{feature_name}' has {missing_ratio:.1%} missing values",
                    affected_samples=int(missing_count),
                    affected_features=[feature_name],
                    recommendation="Investigate data collection for this feature"
                ))

            if out_of_range_ratio > 0.05:
                self.issues.append(DataIssue(
                    issue_type="out_of_range_values",
                    severity="warning",
                    description=f"Feature '{feature_name}' has {out_of_range_ratio:.1%} values outside valid range {valid_range}",
                    affected_samples=int(out_of_range),
                    affected_features=[feature_name],
                    recommendation="Check sensor calibration or data processing"
                ))

    def _validate_labels(self, y: Dict[str, np.ndarray]):
        """Validate label distributions."""
        # Validate failure_prob
        if 'failure_prob' in y:
            failure_prob = y['failure_prob'].flatten()
            failure_count = np.sum(failure_prob > 0.5)
            no_failure_count = np.sum(failure_prob <= 0.5)

            self.label_stats.append(LabelStatistics(
                class_name="failure",
                count=int(failure_count),
                ratio=float(failure_count / len(failure_prob))
            ))
            self.label_stats.append(LabelStatistics(
                class_name="no_failure_binary",
                count=int(no_failure_count),
                ratio=float(no_failure_count / len(failure_prob))
            ))

            if failure_count < self.requirements['min_failure_samples']:
                self.issues.append(DataIssue(
                    issue_type="insufficient_failure_samples",
                    severity="critical",
                    description=f"Only {failure_count} failure samples, need {self.requirements['min_failure_samples']}",
                    affected_samples=failure_count,
                    recommendation="Collect more failure examples"
                ))

        # Validate failure_type
        if 'failure_type' in y:
            failure_type = y['failure_type']
            class_counts = np.sum(failure_type, axis=0)

            for i, count in enumerate(class_counts):
                class_name = FAILURE_TYPES[i] if i < len(FAILURE_TYPES) else f"class_{i}"
                self.label_stats.append(LabelStatistics(
                    class_name=class_name,
                    count=int(count),
                    ratio=float(count / len(failure_type))
                ))

                if count < self.requirements['min_samples_per_class']:
                    # Determine severity based on class
                    severity = "critical" if class_name in ['fuel_pump', 'coolant_system', 'transmission'] else "warning"
                    self.issues.append(DataIssue(
                        issue_type="insufficient_class_samples",
                        severity=severity,
                        description=f"Class '{class_name}' has only {int(count)} samples, need {self.requirements['min_samples_per_class']}",
                        affected_samples=int(count),
                        recommendation=f"Collect more examples of {class_name} failures"
                    ))

            # Check class imbalance
            max_count = np.max(class_counts)
            min_count = np.min(class_counts[class_counts > 0]) if np.any(class_counts > 0) else 1
            imbalance = max_count / min_count if min_count > 0 else float('inf')

            if imbalance > self.requirements['max_class_imbalance']:
                self.issues.append(DataIssue(
                    issue_type="class_imbalance",
                    severity="warning",
                    description=f"Class imbalance ratio is {imbalance:.1f}, max allowed is {self.requirements['max_class_imbalance']}",
                    affected_samples=0,
                    recommendation="Consider data augmentation or weighted sampling"
                ))

    def _validate_missing_values(self, X: np.ndarray):
        """Validate missing value ratio."""
        total_values = X.size
        missing_count = np.sum(np.isnan(X))
        missing_ratio = missing_count / total_values

        if missing_ratio > self.requirements['max_missing_ratio']:
            self.issues.append(DataIssue(
                issue_type="high_missing_ratio",
                severity="critical" if missing_ratio > 0.1 else "warning",
                description=f"Overall missing ratio is {missing_ratio:.2%}, max allowed is {self.requirements['max_missing_ratio']:.1%}",
                affected_samples=int(missing_count),
                recommendation="Improve data collection or implement imputation"
            ))

    def _validate_duplicates(self, X: np.ndarray):
        """Check for duplicate samples."""
        # Flatten to 2D for comparison
        if len(X.shape) == 3:
            X_flat = X.reshape(X.shape[0], -1)
        else:
            X_flat = X

        # Use string representation for exact matching
        unique_count = len(np.unique(X_flat, axis=0))
        duplicate_count = X_flat.shape[0] - unique_count
        duplicate_ratio = duplicate_count / X_flat.shape[0]

        if duplicate_ratio > self.requirements['max_duplicate_ratio']:
            self.issues.append(DataIssue(
                issue_type="high_duplicate_ratio",
                severity="warning",
                description=f"Duplicate ratio is {duplicate_ratio:.2%}, max allowed is {self.requirements['max_duplicate_ratio']:.1%}",
                affected_samples=duplicate_count,
                recommendation="Remove duplicate samples or investigate data collection"
            ))

    def _validate_outliers(self, X: np.ndarray):
        """Detect statistical outliers."""
        if len(X.shape) == 3:
            X_flat = X.reshape(-1, X.shape[2])
        else:
            X_flat = X

        total_outliers = 0
        outlier_features = []

        for i in range(X_flat.shape[1]):
            feature_data = X_flat[:, i]
            valid_data = feature_data[~np.isnan(feature_data)]

            if len(valid_data) == 0:
                continue

            # Use IQR method
            q1 = np.percentile(valid_data, 25)
            q3 = np.percentile(valid_data, 75)
            iqr = q3 - q1
            lower_bound = q1 - 3 * iqr
            upper_bound = q3 + 3 * iqr

            outliers = np.sum((valid_data < lower_bound) | (valid_data > upper_bound))
            outlier_ratio = outliers / len(valid_data)

            if outlier_ratio > 0.05:  # More than 5% outliers
                total_outliers += outliers
                feature_name = EXPECTED_FEATURES[i] if i < len(EXPECTED_FEATURES) else f"feature_{i}"
                outlier_features.append(feature_name)

        if total_outliers > 0 and len(outlier_features) > 0:
            self.issues.append(DataIssue(
                issue_type="statistical_outliers",
                severity="info",
                description=f"Detected {total_outliers} statistical outliers in {len(outlier_features)} features",
                affected_samples=total_outliers,
                affected_features=outlier_features,
                recommendation="Review outliers - may be sensor errors or valid extreme cases"
            ))

    def _validate_temporal_consistency(self, X: np.ndarray):
        """Validate temporal consistency in sequences."""
        if len(X.shape) != 3:
            return  # Only for sequence data

        # Check for sudden jumps in sequential data
        n_samples, n_timesteps, n_features = X.shape

        # Sample check (full check would be too slow)
        sample_indices = np.random.choice(n_samples, min(1000, n_samples), replace=False)

        temporal_issues = 0

        for idx in sample_indices:
            sequence = X[idx]
            for feat_idx in range(n_features):
                feat_data = sequence[:, feat_idx]
                valid_data = feat_data[~np.isnan(feat_data)]

                if len(valid_data) < 2:
                    continue

                # Check for unrealistic jumps
                diffs = np.abs(np.diff(valid_data))
                mean_diff = np.mean(diffs)
                max_diff = np.max(diffs)

                # If max jump is > 10x mean, flag it
                if mean_diff > 0 and max_diff > 10 * mean_diff:
                    temporal_issues += 1

        if temporal_issues > len(sample_indices) * 0.1:  # More than 10% of samples
            self.issues.append(DataIssue(
                issue_type="temporal_discontinuities",
                severity="warning",
                description=f"Detected {temporal_issues} sequences with temporal discontinuities",
                affected_samples=temporal_issues,
                recommendation="Check for data gaps or sensor reconnections in sequences"
            ))

    def _validate_metadata(self, metadata: Dict[str, Any]):
        """Validate metadata if provided."""
        # Check vehicle count
        if 'vehicle_ids' in metadata:
            vehicle_ids = metadata['vehicle_ids']
            unique_vehicles = len(set(vehicle_ids))

            if unique_vehicles < self.requirements['min_vehicle_count']:
                self.issues.append(DataIssue(
                    issue_type="insufficient_vehicle_diversity",
                    severity="warning",
                    description=f"Only {unique_vehicles} unique vehicles, need {self.requirements['min_vehicle_count']}",
                    affected_samples=0,
                    recommendation="Collect data from more diverse vehicles"
                ))

        # Check time span
        if 'timestamps' in metadata:
            timestamps = metadata['timestamps']
            if len(timestamps) > 0:
                try:
                    min_time = min(timestamps)
                    max_time = max(timestamps)

                    if isinstance(min_time, str):
                        min_time = datetime.fromisoformat(min_time)
                        max_time = datetime.fromisoformat(max_time)

                    time_span = (max_time - min_time).days

                    if time_span < self.requirements['min_time_span_days']:
                        self.issues.append(DataIssue(
                            issue_type="insufficient_time_span",
                            severity="warning",
                            description=f"Data spans only {time_span} days, need {self.requirements['min_time_span_days']}",
                            affected_samples=0,
                            recommendation="Collect data over a longer time period"
                        ))
                except Exception as e:
                    logger.warning(f"Could not parse timestamps: {e}")

    def _generate_report(
        self,
        X: np.ndarray,
        y: Dict[str, np.ndarray],
        data_hash: str
    ) -> DataValidationReport:
        """Generate final validation report."""
        # Determine quality level
        critical_issues = [i for i in self.issues if i.severity == 'critical']
        warning_issues = [i for i in self.issues if i.severity == 'warning']

        if len(critical_issues) > 0:
            quality_level = DataQualityLevel.INSUFFICIENT
            can_train = False
        elif len(warning_issues) > 3:
            quality_level = DataQualityLevel.DEVELOPMENT
            can_train = self.target_level == 'development'
        else:
            quality_level = DataQualityLevel.PRODUCTION
            can_train = True

        # Generate recommendations
        recommendations = []
        if critical_issues:
            recommendations.append("CRITICAL: Address these issues before training:")
            for issue in critical_issues:
                recommendations.append(f"  - {issue.description}: {issue.recommendation}")

        if warning_issues:
            recommendations.append("WARNINGS: Consider addressing:")
            for issue in warning_issues[:5]:
                recommendations.append(f"  - {issue.description}")

        # Summary statistics
        summary = {
            'total_samples': X.shape[0],
            'total_features': X.shape[-1],
            'timesteps': X.shape[1] if len(X.shape) == 3 else 1,
            'total_issues': len(self.issues),
            'critical_issues': len(critical_issues),
            'warning_issues': len(warning_issues),
            'quality_score': 1.0 - (len(critical_issues) * 0.2 + len(warning_issues) * 0.05),
            'label_types': list(y.keys()),
        }

        report = DataValidationReport(
            validation_id=f"dv_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            validation_timestamp=datetime.now().isoformat(),
            quality_level=quality_level,
            total_samples=X.shape[0],
            total_features=X.shape[-1],
            issues=self.issues,
            feature_stats=self.feature_stats,
            label_stats=self.label_stats,
            summary=summary,
            data_hash=data_hash,
            can_train=can_train,
            recommendations=recommendations
        )

        logger.info(f"Data validation complete: {quality_level.value}, can_train={can_train}")

        return report


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_training_data(
    X: np.ndarray,
    y: Dict[str, np.ndarray],
    target_level: str = 'production'
) -> Tuple[bool, DataValidationReport]:
    """
    Convenience function to validate training data.

    Args:
        X: Feature array
        y: Label dictionary
        target_level: 'production' or 'development'

    Returns:
        Tuple of (can_train, report)
    """
    validator = TrainingDataValidator(target_level)
    report = validator.validate(X, y)
    return report.can_train, report


def print_validation_report(report: DataValidationReport):
    """Print human-readable validation report."""
    print("\n" + "=" * 70)
    print("TRAINING DATA VALIDATION REPORT")
    print("=" * 70)
    print(f"Validation ID: {report.validation_id}")
    print(f"Timestamp: {report.validation_timestamp}")
    print(f"Data Hash: {report.data_hash}")
    print(f"Quality Level: {report.quality_level.value.upper()}")
    print(f"Can Train: {'YES' if report.can_train else 'NO'}")
    print("-" * 70)

    print(f"\nDATA SUMMARY:")
    print(f"  Total Samples: {report.total_samples:,}")
    print(f"  Total Features: {report.total_features}")
    print(f"  Timesteps: {report.summary.get('timesteps', 1)}")
    print(f"  Quality Score: {report.summary.get('quality_score', 0):.2f}")

    print(f"\nLABEL DISTRIBUTION:")
    for stat in report.label_stats:
        print(f"  {stat.class_name}: {stat.count:,} ({stat.ratio:.1%})")

    if report.issues:
        print(f"\nISSUES FOUND ({len(report.issues)}):")
        for issue in report.issues:
            icon = "[X]" if issue.severity == 'critical' else "[!]" if issue.severity == 'warning' else "[i]"
            print(f"  {icon} {issue.issue_type}: {issue.description}")

    if report.recommendations:
        print(f"\nRECOMMENDATIONS:")
        for rec in report.recommendations:
            print(f"  {rec}")

    print("\n" + "=" * 70)


def save_validation_report(report: DataValidationReport, path: Path):
    """Save validation report to JSON."""
    report_dict = {
        'validation_id': report.validation_id,
        'validation_timestamp': report.validation_timestamp,
        'quality_level': report.quality_level.value,
        'total_samples': report.total_samples,
        'total_features': report.total_features,
        'data_hash': report.data_hash,
        'can_train': report.can_train,
        'summary': report.summary,
        'recommendations': report.recommendations,
        'issues': [
            {
                'issue_type': i.issue_type,
                'severity': i.severity,
                'description': i.description,
                'affected_samples': i.affected_samples,
                'affected_features': i.affected_features,
                'recommendation': i.recommendation
            }
            for i in report.issues
        ],
        'feature_stats': [
            {
                'name': s.name,
                'count': s.count,
                'missing_count': s.missing_count,
                'missing_ratio': s.missing_ratio,
                'min_value': s.min_value,
                'max_value': s.max_value,
                'mean': s.mean,
                'std': s.std
            }
            for s in report.feature_stats
        ],
        'label_stats': [
            {
                'class_name': s.class_name,
                'count': s.count,
                'ratio': s.ratio
            }
            for s in report.label_stats
        ]
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(report_dict, f, indent=2)

    logger.info(f"Validation report saved to {path}")
