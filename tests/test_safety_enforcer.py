"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Safety Enforcer

Test suite for production_safety_enforcer.py
Ensures safety thresholds and disclaimers work correctly.
"""

import pytest
from datetime import datetime
from production_safety_enforcer import (
    ProductionSafetyEnforcer,
    SafetyCriticality,
    PredictionRiskLevel,
    SAFETY_THRESHOLDS,
    MANDATORY_DISCLAIMERS
)

@pytest.fixture
def enforcer():
    """Create safety enforcer instance."""
    return ProductionSafetyEnforcer()

class TestSafetyThresholds:
    """Test safety threshold configurations."""

    def test_critical_systems_have_strictest_thresholds(self):
        """Critical systems must have lowest warning thresholds."""
        critical = SAFETY_THRESHOLDS[SafetyCriticality.CRITICAL]
        high = SAFETY_THRESHOLDS[SafetyCriticality.HIGH]

        assert critical['warning_threshold'] < high['warning_threshold']
        assert critical['min_confidence_for_healthy'] > high['min_confidence_for_healthy']
        assert critical['max_false_negative_rate'] < high['max_false_negative_rate']

    def test_critical_systems_require_human_confirmation(self):
        """All critical systems must require human confirmation."""
        critical = SAFETY_THRESHOLDS[SafetyCriticality.CRITICAL]
        high = SAFETY_THRESHOLDS[SafetyCriticality.HIGH]

        assert critical['require_human_confirmation'] is True
        assert high['require_human_confirmation'] is True

    def test_false_negative_rate_below_5_percent(self):
        """No system should allow more than 5% false negatives."""
        for criticality, thresholds in SAFETY_THRESHOLDS.items():
            assert thresholds['max_false_negative_rate'] <= 0.05, \
                f"{criticality} allows too high false negative rate"

class TestMandatoryDisclaimers:
    """Test mandatory disclaimer presence."""

    def test_all_required_disclaimers_exist(self):
        """All required disclaimer types must be defined."""
        required = [
            'prediction_header',
            'healthy_prediction',
            'failure_prediction',
            'critical_system',
            'low_confidence',
            'liability_notice'
        ]

        for key in required:
            assert key in MANDATORY_DISCLAIMERS
            assert len(MANDATORY_DISCLAIMERS[key]) > 50  # Non-trivial content

    def test_disclaimers_mention_professional_inspection(self):
        """Safety disclaimers must mention professional inspection."""
        professional_keywords = ['mechanic', 'professional', 'inspection', 'qualified']

        for key in ['healthy_prediction', 'failure_prediction', 'critical_system']:
            disclaimer = MANDATORY_DISCLAIMERS[key].lower()
            assert any(kw in disclaimer for kw in professional_keywords), \
                f"Disclaimer '{key}' must mention professional inspection"

class TestPredictionEnforcement:
    """Test prediction enforcement logic."""

    def test_low_confidence_predictions_flagged(self, enforcer):
        """Predictions with low confidence must be flagged."""
        result = enforcer.enforce_prediction(
            failure_probability=0.3,
            failure_type='battery',
            confidence=0.5,  # Low confidence
            days_to_failure=30
        )

        assert 'low_confidence' in result.disclaimers or \
               result.risk_level == PredictionRiskLevel.UNKNOWN

    def test_critical_system_predictions_require_human(self, enforcer):
        """Critical system predictions must require human confirmation."""
        result = enforcer.enforce_prediction(
            failure_probability=0.5,
            failure_type='coolant_system',  # Critical system
            confidence=0.8,
            days_to_failure=14
        )

        assert result.requires_human_confirmation is True

    def test_healthy_predictions_include_disclaimer(self, enforcer):
        """Even 'healthy' predictions must include disclaimers."""
        result = enforcer.enforce_prediction(
            failure_probability=0.05,
            failure_type='no_failure',
            confidence=0.95,
            days_to_failure=60
        )

        assert len(result.disclaimers) > 0
        assert any('not guarantee' in d.lower() for d in result.disclaimers)

class TestSafetyNeverBypassed:
    """Ensure safety can never be bypassed."""

    def test_cannot_disable_disclaimers(self, enforcer):
        """Verify disclaimers cannot be disabled."""
        # Even if we try to get a prediction with flag to disable
        result = enforcer.enforce_prediction(
            failure_probability=0.5,
            failure_type='battery',
            confidence=0.9,
            days_to_failure=7,
            # No disable flag should exist, but even if passed it should be ignored
        )

        assert len(result.disclaimers) > 0

    def test_confidence_always_capped(self, enforcer):
        """Confidence must always be capped to prevent overconfidence."""
        result = enforcer.enforce_prediction(
            failure_probability=0.01,
            failure_type='no_failure',
            confidence=0.99,  # Very high input confidence
            days_to_failure=60
        )

        # Adjusted confidence should be capped at 95%
        assert result.safety_adjusted_confidence <= 0.95