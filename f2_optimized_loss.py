"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: F2 Optimized Loss

F2-Optimized Loss Functions for Safety-Critical Training
=========================================================
Implements loss functions that favor recall over precision to minimize
false negatives in safety-critical failure predictions.

In automotive predictive maintenance:
- FALSE NEGATIVE (missing a failure) = Dangerous, potential accidents
- FALSE POSITIVE (false alarm) = Inconvenient but safe

F2-Score weights recall 4x more than precision:
F2 = (1 + 2²) × (precision × recall) / (2² × precision + recall)
   = 5 × (precision × recall) / (4 × precision + recall)

This module provides:
- F2-optimized binary cross-entropy loss
- Per-class weighted losses based on safety criticality
- Asymmetric loss functions that penalize false negatives heavily
- Focal loss variants for handling class imbalance
"""

import tensorflow as tf
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY CRITICALITY WEIGHTS
# =============================================================================

class SafetyCriticality(Enum):
    """Safety criticality levels for failure types."""
    CRITICAL = "critical"  # Immediate safety hazard
    HIGH = "high"          # Could become dangerous
    MEDIUM = "medium"      # Maintenance needed
    LOW = "low"            # Minor issue


# False negative penalties by criticality
# Higher values = more severe penalty for missing this failure type
FALSE_NEGATIVE_PENALTIES = {
    SafetyCriticality.CRITICAL: 10.0,  # 10x penalty for missing critical failures
    SafetyCriticality.HIGH: 5.0,       # 5x penalty for missing high-risk failures
    SafetyCriticality.MEDIUM: 2.0,     # 2x penalty for medium-risk
    SafetyCriticality.LOW: 1.0,        # Standard penalty for low-risk
}

# Failure type to criticality mapping (must match production_safety_enforcer.py)
FAILURE_CRITICALITY = {
    'battery': SafetyCriticality.HIGH,
    'alternator': SafetyCriticality.HIGH,
    'starter': SafetyCriticality.MEDIUM,
    'fuel_pump': SafetyCriticality.CRITICAL,
    'spark_plug': SafetyCriticality.MEDIUM,
    'oxygen_sensor': SafetyCriticality.MEDIUM,
    'catalytic_converter': SafetyCriticality.MEDIUM,
    'maf_sensor': SafetyCriticality.MEDIUM,
    'thermostat': SafetyCriticality.HIGH,
    'coolant_system': SafetyCriticality.CRITICAL,
    'transmission': SafetyCriticality.CRITICAL,
    'ignition': SafetyCriticality.HIGH,
    'no_failure': SafetyCriticality.LOW,
}

# Class indices for the 13 failure types
FAILURE_TYPE_INDICES = {
    'battery': 0,
    'alternator': 1,
    'starter': 2,
    'fuel_pump': 3,
    'spark_plug': 4,
    'oxygen_sensor': 5,
    'catalytic_converter': 6,
    'maf_sensor': 7,
    'thermostat': 8,
    'coolant_system': 9,
    'transmission': 10,
    'ignition': 11,
    'no_failure': 12,
}


# =============================================================================
# F2-OPTIMIZED LOSS CONFIGURATION
# =============================================================================

@dataclass
class F2LossConfig:
    """Configuration for F2-optimized loss functions."""

    # F-beta score parameter (beta=2 for F2, weighs recall 4x more than precision)
    beta: float = 2.0

    # Base false negative penalty multiplier
    fn_penalty_multiplier: float = 3.0

    # Base false positive penalty (lower than FN)
    fp_penalty_multiplier: float = 1.0

    # Use per-class safety weights
    use_safety_weights: bool = True

    # Focal loss parameters (for class imbalance)
    use_focal_loss: bool = True
    focal_gamma: float = 2.0
    focal_alpha: float = 0.25

    # Label smoothing (prevents overconfidence)
    label_smoothing: float = 0.1

    # Minimum recall threshold - loss increases sharply if recall drops below this
    min_recall_threshold: float = 0.95
    recall_penalty_weight: float = 5.0

    # Temperature scaling for calibration
    temperature: float = 1.0

    # Whether to log detailed loss components
    log_components: bool = True


# =============================================================================
# CORE F2-OPTIMIZED LOSS FUNCTIONS
# =============================================================================

class F2OptimizedBinaryLoss(tf.keras.losses.Loss):
    """
    Binary cross-entropy loss optimized for F2-score (recall-focused).

    Used for the failure_probability output head.
    Heavily penalizes false negatives (missing actual failures).
    """

    def __init__(
        self,
        config: Optional[F2LossConfig] = None,
        name: str = "f2_binary_loss",
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.config = config or F2LossConfig()
        self._loss_components = {}

    def call(self, y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
        """
        Calculate F2-optimized binary loss.

        Args:
            y_true: Ground truth labels (0 or 1)
            y_pred: Predicted probabilities (0 to 1)

        Returns:
            Scalar loss value
        """
        # Ensure numerical stability
        y_pred = tf.clip_by_value(y_pred, 1e-7, 1 - 1e-7)
        y_true = tf.cast(y_true, tf.float32)

        # Apply temperature scaling
        if self.config.temperature != 1.0:
            y_pred = tf.nn.sigmoid(
                tf.math.log(y_pred / (1 - y_pred)) / self.config.temperature
            )

        # Apply label smoothing
        if self.config.label_smoothing > 0:
            y_true = y_true * (1 - self.config.label_smoothing) + 0.5 * self.config.label_smoothing

        # Standard binary cross-entropy components
        # For positive samples (actual failures): -log(y_pred)
        # For negative samples (no failure): -log(1 - y_pred)

        # FALSE NEGATIVE penalty: When y_true=1 but y_pred is low
        # This is the dangerous case - missing an actual failure
        fn_loss = y_true * (-tf.math.log(y_pred))
        fn_loss = fn_loss * self.config.fn_penalty_multiplier

        # FALSE POSITIVE penalty: When y_true=0 but y_pred is high
        # This is inconvenient but safe - false alarm
        fp_loss = (1 - y_true) * (-tf.math.log(1 - y_pred))
        fp_loss = fp_loss * self.config.fp_penalty_multiplier

        # Apply focal loss modulation if enabled
        if self.config.use_focal_loss:
            # Focal loss: (1 - p_t)^gamma * CE
            # For positives: (1 - y_pred)^gamma when y_true=1
            # For negatives: y_pred^gamma when y_true=0
            focal_weight_pos = tf.pow(1 - y_pred, self.config.focal_gamma)
            focal_weight_neg = tf.pow(y_pred, self.config.focal_gamma)

            fn_loss = fn_loss * focal_weight_pos
            fp_loss = fp_loss * focal_weight_neg

        # Combine losses
        total_loss = fn_loss + fp_loss

        # Add recall penalty if below threshold
        recall_penalty = self._calculate_recall_penalty(y_true, y_pred)
        total_loss = total_loss + recall_penalty

        # Store components for logging
        if self.config.log_components:
            self._loss_components = {
                'fn_loss': tf.reduce_mean(fn_loss).numpy(),
                'fp_loss': tf.reduce_mean(fp_loss).numpy(),
                'recall_penalty': tf.reduce_mean(recall_penalty).numpy(),
                'total_loss': tf.reduce_mean(total_loss).numpy(),
            }

        return tf.reduce_mean(total_loss)

    def _calculate_recall_penalty(
        self,
        y_true: tf.Tensor,
        y_pred: tf.Tensor
    ) -> tf.Tensor:
        """
        Calculate additional penalty if recall drops below threshold.

        This ensures the model maintains high recall even during training.
        """
        # Soft recall calculation (differentiable)
        # True positives (soft): sum of y_pred where y_true=1
        tp_soft = tf.reduce_sum(y_true * y_pred)

        # Actual positives
        p = tf.reduce_sum(y_true) + 1e-7

        # Soft recall
        recall_soft = tp_soft / p

        # Penalty increases sharply when recall drops below threshold
        recall_deficit = tf.maximum(0.0, self.config.min_recall_threshold - recall_soft)

        # Quadratic penalty for more aggressive correction
        penalty = self.config.recall_penalty_weight * tf.square(recall_deficit)

        return penalty

    def get_loss_components(self) -> Dict[str, float]:
        """Get the last computed loss components for logging."""
        return self._loss_components.copy()


class F2OptimizedCategoricalLoss(tf.keras.losses.Loss):
    """
    Categorical cross-entropy loss optimized for F2-score with per-class safety weights.

    Used for the failure_type output head (13 classes).
    Applies different penalties based on safety criticality of each failure type.
    """

    def __init__(
        self,
        config: Optional[F2LossConfig] = None,
        name: str = "f2_categorical_loss",
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.config = config or F2LossConfig()
        self._loss_components = {}

        # Build class weight tensor based on safety criticality
        self.class_weights = self._build_class_weights()

    def _build_class_weights(self) -> tf.Tensor:
        """Build per-class weight tensor based on safety criticality."""
        weights = np.ones(len(FAILURE_TYPE_INDICES), dtype=np.float32)

        if self.config.use_safety_weights:
            for failure_type, idx in FAILURE_TYPE_INDICES.items():
                criticality = FAILURE_CRITICALITY.get(failure_type, SafetyCriticality.MEDIUM)
                penalty = FALSE_NEGATIVE_PENALTIES.get(criticality, 2.0)
                weights[idx] = penalty

        # Normalize so mean weight is 1.0
        weights = weights / np.mean(weights)

        logger.info(f"Class weights for F2 loss: {dict(zip(FAILURE_TYPE_INDICES.keys(), weights))}")

        return tf.constant(weights, dtype=tf.float32)

    def call(self, y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
        """
        Calculate F2-optimized categorical loss with safety weights.

        Args:
            y_true: One-hot encoded ground truth (batch, 13)
            y_pred: Predicted probabilities (batch, 13)

        Returns:
            Scalar loss value
        """
        # Ensure numerical stability
        y_pred = tf.clip_by_value(y_pred, 1e-7, 1 - 1e-7)
        y_true = tf.cast(y_true, tf.float32)

        # Apply temperature scaling
        if self.config.temperature != 1.0:
            # Convert probs to logits, scale, convert back
            logits = tf.math.log(y_pred)
            y_pred = tf.nn.softmax(logits / self.config.temperature)

        # Apply label smoothing
        if self.config.label_smoothing > 0:
            num_classes = tf.shape(y_true)[-1]
            y_true = y_true * (1 - self.config.label_smoothing) + \
                     self.config.label_smoothing / tf.cast(num_classes, tf.float32)

        # Standard categorical cross-entropy: -sum(y_true * log(y_pred))
        ce_loss = -tf.reduce_sum(y_true * tf.math.log(y_pred), axis=-1)

        # Apply per-class safety weights
        # Weight is applied based on the true class
        # Find the true class for each sample
        true_class = tf.argmax(y_true, axis=-1)
        sample_weights = tf.gather(self.class_weights, true_class)

        weighted_loss = ce_loss * sample_weights

        # Apply focal loss modulation if enabled
        if self.config.use_focal_loss:
            # Get probability of true class
            pt = tf.reduce_sum(y_true * y_pred, axis=-1)
            focal_weight = tf.pow(1 - pt, self.config.focal_gamma)
            weighted_loss = weighted_loss * focal_weight

        # Add per-class recall penalties for critical classes
        recall_penalties = self._calculate_per_class_recall_penalty(y_true, y_pred)
        total_loss = weighted_loss + recall_penalties

        # Store components for logging
        if self.config.log_components:
            self._loss_components = {
                'ce_loss': tf.reduce_mean(ce_loss).numpy(),
                'weighted_loss': tf.reduce_mean(weighted_loss).numpy(),
                'recall_penalties': tf.reduce_mean(recall_penalties).numpy(),
                'total_loss': tf.reduce_mean(total_loss).numpy(),
            }

        return tf.reduce_mean(total_loss)

    def _calculate_per_class_recall_penalty(
        self,
        y_true: tf.Tensor,
        y_pred: tf.Tensor
    ) -> tf.Tensor:
        """
        Calculate recall penalty for each safety-critical class.

        Critical classes (fuel_pump, coolant_system, transmission) get
        additional penalties if their recall is low.
        """
        total_penalty = tf.constant(0.0)

        critical_indices = [
            FAILURE_TYPE_INDICES['fuel_pump'],
            FAILURE_TYPE_INDICES['coolant_system'],
            FAILURE_TYPE_INDICES['transmission'],
        ]

        for idx in critical_indices:
            # Get predictions and labels for this class
            class_true = y_true[:, idx]
            class_pred = y_pred[:, idx]

            # Soft recall for this class
            tp = tf.reduce_sum(class_true * class_pred)
            p = tf.reduce_sum(class_true) + 1e-7
            recall = tp / p

            # Penalty for low recall on critical classes
            recall_deficit = tf.maximum(0.0, 0.99 - recall)  # 99% min for critical
            penalty = self.config.recall_penalty_weight * tf.square(recall_deficit)
            total_penalty = total_penalty + penalty

        return total_penalty

    def get_loss_components(self) -> Dict[str, float]:
        """Get the last computed loss components for logging."""
        return self._loss_components.copy()


class SafetyAwareMSELoss(tf.keras.losses.Loss):
    """
    MSE loss for days_to_failure with safety-aware modifications.

    Penalizes over-estimation of time more than under-estimation.
    If model says "30 days" but actual is "5 days", that's dangerous.
    If model says "5 days" but actual is "30 days", that's just cautious.
    """

    def __init__(
        self,
        config: Optional[F2LossConfig] = None,
        underestimate_penalty: float = 0.5,
        overestimate_penalty: float = 2.0,
        name: str = "safety_mse_loss",
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.config = config or F2LossConfig()
        self.underestimate_penalty = underestimate_penalty  # Predicting sooner than actual
        self.overestimate_penalty = overestimate_penalty    # Predicting later than actual (DANGEROUS)
        self._loss_components = {}

    def call(self, y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
        """
        Calculate safety-aware MSE loss.

        Args:
            y_true: Actual days to failure
            y_pred: Predicted days to failure

        Returns:
            Scalar loss value
        """
        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.cast(y_pred, tf.float32)

        # Calculate error (positive = overestimate = dangerous)
        error = y_pred - y_true

        # Squared error base
        sq_error = tf.square(error)

        # Apply asymmetric weighting
        # Overestimate (error > 0): Higher penalty - predicting more time than actually available
        # Underestimate (error < 0): Lower penalty - being cautious
        weight = tf.where(
            error > 0,
            self.overestimate_penalty,  # Dangerous: said 30 days, was 5
            self.underestimate_penalty   # Safe: said 5 days, was 30
        )

        weighted_loss = sq_error * weight

        # Additional penalty for large overestimates (> 15 days off)
        large_overestimate = tf.maximum(0.0, error - 15.0)
        large_overestimate_penalty = tf.square(large_overestimate) * 5.0

        total_loss = weighted_loss + large_overestimate_penalty

        # Store components for logging
        if self.config.log_components:
            self._loss_components = {
                'mse': tf.reduce_mean(sq_error).numpy(),
                'weighted_loss': tf.reduce_mean(weighted_loss).numpy(),
                'overestimate_penalty': tf.reduce_mean(large_overestimate_penalty).numpy(),
                'total_loss': tf.reduce_mean(total_loss).numpy(),
                'mean_error': tf.reduce_mean(error).numpy(),
            }

        return tf.reduce_mean(total_loss)

    def get_loss_components(self) -> Dict[str, float]:
        """Get the last computed loss components for logging."""
        return self._loss_components.copy()


# =============================================================================
# COMBINED F2 LOSS FOR MULTI-OUTPUT MODEL
# =============================================================================

class F2CombinedLoss(tf.keras.losses.Loss):
    """
    Combined loss for all three output heads with F2-optimization.

    Output heads:
    1. failure_probability (binary) - F2-optimized binary CE
    2. failure_type (categorical) - F2-optimized categorical CE with safety weights
    3. days_to_failure (regression) - Safety-aware asymmetric MSE
    """

    def __init__(
        self,
        config: Optional[F2LossConfig] = None,
        prob_weight: float = 1.5,    # Increased weight for failure detection
        type_weight: float = 1.0,
        days_weight: float = 0.5,
        name: str = "f2_combined_loss",
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.config = config or F2LossConfig()

        # Output head weights
        self.prob_weight = prob_weight
        self.type_weight = type_weight
        self.days_weight = days_weight

        # Individual loss functions
        self.binary_loss = F2OptimizedBinaryLoss(config)
        self.categorical_loss = F2OptimizedCategoricalLoss(config)
        self.regression_loss = SafetyAwareMSELoss(config)

        self._loss_components = {}

    def call(
        self,
        y_true: Dict[str, tf.Tensor],
        y_pred: Dict[str, tf.Tensor]
    ) -> tf.Tensor:
        """
        Calculate combined F2-optimized loss.

        Args:
            y_true: Dict with keys 'failure_prob', 'failure_type', 'days_to_failure'
            y_pred: Dict with same keys

        Returns:
            Scalar combined loss
        """
        # Calculate individual losses
        prob_loss = self.binary_loss(y_true['failure_prob'], y_pred['failure_prob'])
        type_loss = self.categorical_loss(y_true['failure_type'], y_pred['failure_type'])
        days_loss = self.regression_loss(y_true['days_to_failure'], y_pred['days_to_failure'])

        # Weighted combination
        total_loss = (
            self.prob_weight * prob_loss +
            self.type_weight * type_loss +
            self.days_weight * days_loss
        )

        # Store components
        self._loss_components = {
            'prob_loss': prob_loss.numpy(),
            'type_loss': type_loss.numpy(),
            'days_loss': days_loss.numpy(),
            'weighted_total': total_loss.numpy(),
            'prob_components': self.binary_loss.get_loss_components(),
            'type_components': self.categorical_loss.get_loss_components(),
            'days_components': self.regression_loss.get_loss_components(),
        }

        return total_loss

    def get_loss_components(self) -> Dict[str, Any]:
        """Get all loss components for detailed logging."""
        return self._loss_components.copy()


# =============================================================================
# LOSS FACTORY AND UTILITIES
# =============================================================================

class F2LossFactory:
    """Factory for creating F2-optimized loss functions."""

    @staticmethod
    def create_loss_dict(config: Optional[F2LossConfig] = None) -> Dict[str, tf.keras.losses.Loss]:
        """
        Create loss dictionary for model.compile().

        Returns:
            Dict mapping output names to loss functions
        """
        config = config or F2LossConfig()

        return {
            'failure_prob': F2OptimizedBinaryLoss(config),
            'failure_type': F2OptimizedCategoricalLoss(config),
            'days_to_failure': SafetyAwareMSELoss(config),
        }

    @staticmethod
    def create_loss_weights(
        emphasize_detection: bool = True
    ) -> Dict[str, float]:
        """
        Create loss weight dictionary for model.compile().

        Args:
            emphasize_detection: If True, weights failure detection higher

        Returns:
            Dict mapping output names to weights
        """
        if emphasize_detection:
            return {
                'failure_prob': 1.5,    # Most important: detecting failures
                'failure_type': 1.0,    # Important: correct diagnosis
                'days_to_failure': 0.5, # Less critical than detection
            }
        else:
            return {
                'failure_prob': 1.0,
                'failure_type': 0.5,
                'days_to_failure': 0.3,
            }

    @staticmethod
    def get_class_weights_array() -> np.ndarray:
        """Get class weights as numpy array for sample_weight in fit()."""
        weights = np.ones(len(FAILURE_TYPE_INDICES), dtype=np.float32)

        for failure_type, idx in FAILURE_TYPE_INDICES.items():
            criticality = FAILURE_CRITICALITY.get(failure_type, SafetyCriticality.MEDIUM)
            penalty = FALSE_NEGATIVE_PENALTIES.get(criticality, 2.0)
            weights[idx] = penalty

        return weights / np.mean(weights)


# =============================================================================
# METRICS FOR F2-OPTIMIZED TRAINING
# =============================================================================

class F2Score(tf.keras.metrics.Metric):
    """
    F2 Score metric for monitoring recall-weighted performance.

    F2 = (1 + 2²) × (precision × recall) / (2² × precision + recall)
       = 5 × (precision × recall) / (4 × precision + recall)
    """

    def __init__(
        self,
        threshold: float = 0.5,
        beta: float = 2.0,
        name: str = "f2_score",
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.threshold = threshold
        self.beta = beta
        self.beta_squared = beta ** 2

        self.true_positives = self.add_weight(name='tp', initializer='zeros')
        self.false_positives = self.add_weight(name='fp', initializer='zeros')
        self.false_negatives = self.add_weight(name='fn', initializer='zeros')

    def update_state(self, y_true, y_pred, sample_weight=None):
        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.cast(y_pred >= self.threshold, tf.float32)

        tp = tf.reduce_sum(y_true * y_pred)
        fp = tf.reduce_sum((1 - y_true) * y_pred)
        fn = tf.reduce_sum(y_true * (1 - y_pred))

        self.true_positives.assign_add(tp)
        self.false_positives.assign_add(fp)
        self.false_negatives.assign_add(fn)

    def result(self):
        precision = self.true_positives / (self.true_positives + self.false_positives + 1e-7)
        recall = self.true_positives / (self.true_positives + self.false_negatives + 1e-7)

        f_beta = (1 + self.beta_squared) * (precision * recall) / \
                 (self.beta_squared * precision + recall + 1e-7)

        return f_beta

    def reset_state(self):
        self.true_positives.assign(0)
        self.false_positives.assign(0)
        self.false_negatives.assign(0)


class SafetyRecall(tf.keras.metrics.Metric):
    """
    Recall metric with emphasis on safety-critical classes.

    Tracks recall separately for critical failure types.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        name: str = "safety_recall",
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.threshold = threshold

        # Track true positives and actual positives for critical classes
        self.critical_tp = self.add_weight(name='critical_tp', initializer='zeros')
        self.critical_p = self.add_weight(name='critical_p', initializer='zeros')

    def update_state(self, y_true, y_pred, sample_weight=None):
        """
        Update state for categorical predictions.

        y_true and y_pred should be one-hot encoded (batch, 13)
        """
        # Get critical class indices
        critical_indices = [
            FAILURE_TYPE_INDICES['fuel_pump'],
            FAILURE_TYPE_INDICES['coolant_system'],
            FAILURE_TYPE_INDICES['transmission'],
            FAILURE_TYPE_INDICES['alternator'],
            FAILURE_TYPE_INDICES['thermostat'],
        ]

        # Convert predictions to class indices
        y_pred_class = tf.argmax(y_pred, axis=-1)
        y_true_class = tf.argmax(y_true, axis=-1)

        for idx in critical_indices:
            # Count actual positives for this class
            is_true_class = tf.cast(y_true_class == idx, tf.float32)
            is_pred_class = tf.cast(y_pred_class == idx, tf.float32)

            tp = tf.reduce_sum(is_true_class * is_pred_class)
            p = tf.reduce_sum(is_true_class)

            self.critical_tp.assign_add(tp)
            self.critical_p.assign_add(p)

    def result(self):
        return self.critical_tp / (self.critical_p + 1e-7)

    def reset_state(self):
        self.critical_tp.assign(0)
        self.critical_p.assign(0)


class FalseNegativeRate(tf.keras.metrics.Metric):
    """
    False Negative Rate metric - critical for safety monitoring.

    FNR = FN / (FN + TP) = 1 - Recall
    Lower is better. Target: < 1% for critical systems.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        name: str = "false_negative_rate",
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.threshold = threshold

        self.false_negatives = self.add_weight(name='fn', initializer='zeros')
        self.true_positives = self.add_weight(name='tp', initializer='zeros')

    def update_state(self, y_true, y_pred, sample_weight=None):
        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.cast(y_pred >= self.threshold, tf.float32)

        fn = tf.reduce_sum(y_true * (1 - y_pred))
        tp = tf.reduce_sum(y_true * y_pred)

        self.false_negatives.assign_add(fn)
        self.true_positives.assign_add(tp)

    def result(self):
        return self.false_negatives / (self.false_negatives + self.true_positives + 1e-7)

    def reset_state(self):
        self.false_negatives.assign(0)
        self.true_positives.assign(0)


# =============================================================================
# TRAINING CALLBACKS FOR F2 MONITORING
# =============================================================================

class F2MonitorCallback(tf.keras.callbacks.Callback):
    """
    Callback to monitor F2 score and safety metrics during training.

    Logs detailed breakdown of loss components and raises alerts
    if safety metrics fall below thresholds.
    """

    def __init__(
        self,
        min_recall: float = 0.95,
        max_fnr: float = 0.05,
        log_frequency: int = 10,
    ):
        super().__init__()
        self.min_recall = min_recall
        self.max_fnr = max_fnr
        self.log_frequency = log_frequency
        self.epoch_metrics = []

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}

        # Extract key metrics
        metrics = {
            'epoch': epoch + 1,
            'loss': logs.get('loss', 0),
            'val_loss': logs.get('val_loss', 0),
            'f2_score': logs.get('f2_score', 0),
            'val_f2_score': logs.get('val_f2_score', 0),
            'false_negative_rate': logs.get('false_negative_rate', 0),
            'val_false_negative_rate': logs.get('val_false_negative_rate', 0),
        }

        self.epoch_metrics.append(metrics)

        # Log every N epochs
        if (epoch + 1) % self.log_frequency == 0:
            logger.info(f"Epoch {epoch + 1}: F2={metrics['val_f2_score']:.4f}, "
                       f"FNR={metrics['val_false_negative_rate']:.4f}")

        # Safety alerts
        val_fnr = metrics['val_false_negative_rate']
        if val_fnr > self.max_fnr:
            logger.warning(
                f"⚠️ SAFETY ALERT: False Negative Rate {val_fnr:.4f} exceeds "
                f"threshold {self.max_fnr:.4f} at epoch {epoch + 1}"
            )

        val_f2 = metrics['val_f2_score']
        if val_f2 < 0.5:
            logger.warning(
                f"⚠️ LOW F2 SCORE: {val_f2:.4f} at epoch {epoch + 1}. "
                f"Model may be missing too many failures."
            )

    def get_training_history(self) -> List[Dict[str, Any]]:
        """Get complete training history with safety metrics."""
        return self.epoch_metrics.copy()


class EarlyStoppingOnFNR(tf.keras.callbacks.Callback):
    """
    Early stopping that triggers if false negative rate gets too high.

    Unlike standard early stopping (which monitors val_loss), this
    ensures training doesn't produce a model that misses failures.
    """

    def __init__(
        self,
        max_fnr: float = 0.05,
        patience: int = 5,
        restore_best_weights: bool = True,
    ):
        super().__init__()
        self.max_fnr = max_fnr
        self.patience = patience
        self.restore_best_weights = restore_best_weights

        self.best_weights = None
        self.best_fnr = float('inf')
        self.wait = 0

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        current_fnr = logs.get('val_false_negative_rate', 0)

        if current_fnr < self.best_fnr:
            self.best_fnr = current_fnr
            self.wait = 0
            if self.restore_best_weights:
                self.best_weights = self.model.get_weights()
        else:
            self.wait += 1
            if self.wait >= self.patience and current_fnr > self.max_fnr:
                self.model.stop_training = True
                logger.warning(
                    f"Early stopping: FNR {current_fnr:.4f} > {self.max_fnr:.4f} "
                    f"for {self.patience} epochs"
                )
                if self.restore_best_weights and self.best_weights:
                    self.model.set_weights(self.best_weights)
                    logger.info(f"Restored best weights with FNR={self.best_fnr:.4f}")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_f2_optimized_losses(
    config: Optional[F2LossConfig] = None
) -> Tuple[Dict[str, tf.keras.losses.Loss], Dict[str, float]]:
    """
    Convenience function to get F2-optimized losses and weights.

    Returns:
        Tuple of (loss_dict, weight_dict) for model.compile()
    """
    config = config or F2LossConfig()

    losses = F2LossFactory.create_loss_dict(config)
    weights = F2LossFactory.create_loss_weights(emphasize_detection=True)

    return losses, weights


def get_f2_metrics() -> List[tf.keras.metrics.Metric]:
    """
    Get list of F2-related metrics for model.compile().

    Returns:
        List of metric instances
    """
    return [
        F2Score(threshold=0.5, name='f2_score'),
        FalseNegativeRate(threshold=0.5, name='false_negative_rate'),
        tf.keras.metrics.Recall(name='recall'),
        tf.keras.metrics.Precision(name='precision'),
        tf.keras.metrics.AUC(name='auc'),
    ]


def get_f2_callbacks(
    min_recall: float = 0.95,
    max_fnr: float = 0.05,
) -> List[tf.keras.callbacks.Callback]:
    """
    Get recommended callbacks for F2-optimized training.

    Returns:
        List of callback instances
    """
    return [
        F2MonitorCallback(min_recall=min_recall, max_fnr=max_fnr),
        EarlyStoppingOnFNR(max_fnr=max_fnr, patience=5),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_false_negative_rate',
            factor=0.5,
            patience=3,
            mode='min',
            verbose=1
        ),
    ]


def compile_model_with_f2_optimization(
    model: tf.keras.Model,
    config: Optional[F2LossConfig] = None,
    learning_rate: float = 0.001,
) -> tf.keras.Model:
    """
    Compile a model with F2-optimized losses, weights, and metrics.

    Args:
        model: Keras model with outputs named 'failure_prob', 'failure_type', 'days_to_failure'
        config: F2 loss configuration
        learning_rate: Initial learning rate

    Returns:
        Compiled model
    """
    config = config or F2LossConfig()

    losses, weights = get_f2_optimized_losses(config)
    metrics = get_f2_metrics()

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss=losses,
        loss_weights=weights,
        metrics={
            'failure_prob': metrics,
            'failure_type': [
                tf.keras.metrics.CategoricalAccuracy(name='accuracy'),
                SafetyRecall(name='safety_recall'),
            ],
            'days_to_failure': [
                tf.keras.metrics.MeanAbsoluteError(name='mae'),
            ],
        }
    )

    logger.info("Model compiled with F2-optimized losses")
    logger.info(f"Loss weights: {weights}")

    return model


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_default_config: Optional[F2LossConfig] = None


def get_f2_config() -> F2LossConfig:
    """Get or create default F2 loss configuration."""
    global _default_config
    if _default_config is None:
        _default_config = F2LossConfig()
    return _default_config


def set_f2_config(config: F2LossConfig) -> None:
    """Set the default F2 loss configuration."""
    global _default_config
    _default_config = config
    logger.info(f"F2 config updated: beta={config.beta}, fn_penalty={config.fn_penalty_multiplier}")
