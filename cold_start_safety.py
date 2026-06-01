"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Cold Start Safety

Predict OBD - Cold-Start Safety Module
CRITICAL: Prevents unreliable predictions from being trusted.

This module enforces hard safety limits on predictions for vehicles
with insufficient data history.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class DataSufficiency(Enum):
    """Data sufficiency levels for prediction confidence."""
    INSUFFICIENT = "insufficient"      # < 100 samples - predictions blocked or heavily warned
    MINIMAL = "minimal"                # 100-500 samples - low confidence cap
    DEVELOPING = "developing"          # 500-2000 samples - moderate confidence cap
    ESTABLISHED = "established"        # 2000-5000 samples - normal confidence
    MATURE = "mature"                  # > 5000 samples - full confidence allowed


@dataclass
class ColdStartAssessment:
    """Assessment result for cold-start safety."""
    vehicle_id: str
    data_sufficiency: DataSufficiency
    sample_count: int
    days_of_data: int
    max_allowed_confidence: float
    prediction_allowed: bool
    warning_message: Optional[str]
    requires_disclaimer: bool
    timestamp: str


# Hard-coded safety thresholds - NOT configurable to prevent bypass
SAFETY_THRESHOLDS = {
    DataSufficiency.INSUFFICIENT: {
        "min_samples": 0,
        "max_samples": 100,
        "max_confidence": 0.0,  # NO predictions allowed
        "prediction_allowed": False,
        "warning": "INSUFFICIENT DATA: Cannot generate reliable predictions. Need at least 100 data samples."
    },
    DataSufficiency.MINIMAL: {
        "min_samples": 100,
        "max_samples": 500,
        "max_confidence": 0.35,  # Hard cap at 35%
        "prediction_allowed": True,
        "warning": "LIMITED DATA: Predictions are preliminary. Confidence capped at 35%. Verify with professional inspection."
    },
    DataSufficiency.DEVELOPING: {
        "min_samples": 500,
        "max_samples": 2000,
        "max_confidence": 0.60,  # Hard cap at 60%
        "prediction_allowed": True,
        "warning": "DEVELOPING BASELINE: Prediction accuracy improving. Confidence capped at 60%."
    },
    DataSufficiency.ESTABLISHED: {
        "min_samples": 2000,
        "max_samples": 5000,
        "max_confidence": 0.85,  # Cap at 85%
        "prediction_allowed": True,
        "warning": None
    },
    DataSufficiency.MATURE: {
        "min_samples": 5000,
        "max_samples": float('inf'),
        "max_confidence": 1.0,  # Full confidence allowed
        "prediction_allowed": True,
        "warning": None
    }
}


class ColdStartSafetyEnforcer:
    """
    Enforces cold-start safety for all predictions.

    GUARANTEES:
    1. Vehicles with <100 samples CANNOT receive predictions
    2. Confidence scores are HARD CAPPED based on data sufficiency
    3. All cold-start predictions include mandatory warnings
    4. API responses clearly indicate data sufficiency state
    5. No configuration can bypass these safety limits
    """

    def __init__(self):
        self._assessment_cache: Dict[str, ColdStartAssessment] = {}

    def assess_vehicle(self, vehicle_id: str, sample_count: int,
                       first_sample_date: Optional[datetime] = None) -> ColdStartAssessment:
        """
        Assess a vehicle's data sufficiency for predictions.

        Args:
            vehicle_id: Vehicle identifier
            sample_count: Number of data samples collected
            first_sample_date: Date of first data sample

        Returns:
            ColdStartAssessment with safety parameters
        """
        # Determine data sufficiency level
        sufficiency = self._determine_sufficiency(sample_count)
        thresholds = SAFETY_THRESHOLDS[sufficiency]

        # Calculate days of data
        days_of_data = 0
        if first_sample_date:
            days_of_data = (datetime.now() - first_sample_date).days

        assessment = ColdStartAssessment(
            vehicle_id=vehicle_id,
            data_sufficiency=sufficiency,
            sample_count=sample_count,
            days_of_data=days_of_data,
            max_allowed_confidence=thresholds["max_confidence"],
            prediction_allowed=thresholds["prediction_allowed"],
            warning_message=thresholds["warning"],
            requires_disclaimer=sufficiency in [DataSufficiency.INSUFFICIENT,
                                                 DataSufficiency.MINIMAL,
                                                 DataSufficiency.DEVELOPING],
            timestamp=datetime.now().isoformat()
        )

        # Cache assessment
        self._assessment_cache[vehicle_id] = assessment

        logger.info(f"Cold-start assessment for {vehicle_id}: {sufficiency.value} "
                    f"({sample_count} samples, max_conf={thresholds['max_confidence']})")

        return assessment

    def _determine_sufficiency(self, sample_count: int) -> DataSufficiency:
        """Determine data sufficiency level from sample count."""
        for level, thresholds in SAFETY_THRESHOLDS.items():
            if thresholds["min_samples"] <= sample_count < thresholds["max_samples"]:
                return level
        return DataSufficiency.MATURE

    def enforce_confidence_cap(self, vehicle_id: str, raw_confidence: float,
                               sample_count: int) -> Tuple[float, bool, Optional[str]]:
        """
        Enforce confidence cap based on data sufficiency.

        Args:
            vehicle_id: Vehicle identifier
            raw_confidence: Model's raw confidence score
            sample_count: Number of data samples

        Returns:
            (capped_confidence, was_capped, warning_message)
        """
        assessment = self.assess_vehicle(vehicle_id, sample_count)

        if not assessment.prediction_allowed:
            # Block prediction entirely
            logger.warning(f"COLD-START BLOCK: Prediction blocked for {vehicle_id} "
                          f"(only {sample_count} samples)")
            return 0.0, True, assessment.warning_message

        # Apply hard cap
        capped_confidence = min(raw_confidence, assessment.max_allowed_confidence)
        was_capped = capped_confidence < raw_confidence

        if was_capped:
            logger.info(f"COLD-START CAP: Confidence for {vehicle_id} capped from "
                        f"{raw_confidence:.2f} to {capped_confidence:.2f}")

        return capped_confidence, was_capped, assessment.warning_message

    def validate_prediction_request(self, vehicle_id: str,
                                     sample_count: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate if prediction request should proceed.

        Args:
            vehicle_id: Vehicle identifier
            sample_count: Number of data samples

        Returns:
            (is_allowed, response_metadata)
        """
        assessment = self.assess_vehicle(vehicle_id, sample_count)

        metadata = {
            "data_sufficiency": assessment.data_sufficiency.value,
            "sample_count": sample_count,
            "max_confidence": assessment.max_allowed_confidence,
            "requires_disclaimer": assessment.requires_disclaimer,
            "warning": assessment.warning_message
        }

        if not assessment.prediction_allowed:
            metadata["error"] = "INSUFFICIENT_DATA"
            metadata["error_message"] = assessment.warning_message
            return False, metadata

        return True, metadata

    def wrap_prediction_response(self, vehicle_id: str, prediction: Dict[str, Any],
                                  sample_count: int) -> Dict[str, Any]:
        """
        Wrap prediction response with cold-start safety metadata.

        This ensures API consumers CANNOT ignore cold-start warnings.

        Args:
            vehicle_id: Vehicle identifier
            prediction: Raw prediction result
            sample_count: Number of data samples

        Returns:
            Wrapped prediction with mandatory safety metadata
        """
        assessment = self.assess_vehicle(vehicle_id, sample_count)

        # Apply confidence cap to prediction
        if "confidence" in prediction:
            original_confidence = prediction["confidence"]
            prediction["confidence"], was_capped, _ = self.enforce_confidence_cap(
                vehicle_id, original_confidence, sample_count
            )
            if was_capped:
                prediction["confidence_was_capped"] = True
                prediction["original_confidence"] = original_confidence

        # Add mandatory cold-start metadata
        wrapped = {
            "prediction": prediction,
            "cold_start_safety": {
                "data_sufficiency": assessment.data_sufficiency.value,
                "sample_count": sample_count,
                "max_allowed_confidence": assessment.max_allowed_confidence,
                "requires_disclaimer": assessment.requires_disclaimer,
                "prediction_reliability": self._get_reliability_label(assessment.data_sufficiency)
            }
        }

        # Add warning that MUST be displayed
        if assessment.warning_message:
            wrapped["cold_start_safety"]["mandatory_warning"] = assessment.warning_message
            wrapped["cold_start_safety"]["display_warning"] = True

        return wrapped

    def _get_reliability_label(self, sufficiency: DataSufficiency) -> str:
        """Get human-readable reliability label."""
        labels = {
            DataSufficiency.INSUFFICIENT: "NOT AVAILABLE - Insufficient data",
            DataSufficiency.MINIMAL: "LOW - Limited data, verify independently",
            DataSufficiency.DEVELOPING: "MODERATE - Improving accuracy",
            DataSufficiency.ESTABLISHED: "GOOD - Reliable predictions",
            DataSufficiency.MATURE: "EXCELLENT - High accuracy expected"
        }
        return labels.get(sufficiency, "UNKNOWN")

    def get_cached_assessment(self, vehicle_id: str) -> Optional[ColdStartAssessment]:
        """Get cached assessment for a vehicle."""
        return self._assessment_cache.get(vehicle_id)


# Global enforcer instance
_cold_start_enforcer: Optional[ColdStartSafetyEnforcer] = None


def get_cold_start_enforcer() -> ColdStartSafetyEnforcer:
    """Get global cold-start safety enforcer."""
    global _cold_start_enforcer
    if _cold_start_enforcer is None:
        _cold_start_enforcer = ColdStartSafetyEnforcer()
    return _cold_start_enforcer


def enforce_cold_start_safety(vehicle_id: str, prediction: Dict[str, Any],
                               sample_count: int) -> Dict[str, Any]:
    """
    Convenience function to enforce cold-start safety on a prediction.

    Usage:
        result = enforce_cold_start_safety(vehicle_id, raw_prediction, sample_count)
    """
    enforcer = get_cold_start_enforcer()
    return enforcer.wrap_prediction_response(vehicle_id, prediction, sample_count)


def validate_prediction_allowed(vehicle_id: str, sample_count: int) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if prediction is allowed for a vehicle.

    Usage:
        allowed, metadata = validate_prediction_allowed(vehicle_id, sample_count)
        if not allowed:
            return error_response(metadata)
    """
    enforcer = get_cold_start_enforcer()
    return enforcer.validate_prediction_request(vehicle_id, sample_count)


class InsufficientDataError(Exception):
    """Raised when prediction is requested with insufficient data."""

    def __init__(self, vehicle_id: str, sample_count: int, required: int = 100):
        self.vehicle_id = vehicle_id
        self.sample_count = sample_count
        self.required = required
        super().__init__(
            f"Cannot generate prediction for {vehicle_id}: "
            f"only {sample_count} samples available (minimum {required} required)"
        )
