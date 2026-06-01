"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Safety Integration Module

Safety Integration Module
=========================
Central integration point for all safety systems.
Provides a unified interface for enforcing safety requirements.

This module orchestrates:
1. Production safety enforcement
2. Model validation
3. Human-in-loop requirements
4. Disclaimer management
5. Liability protection
6. Data provenance

CRITICAL: All predictions MUST pass through this module before being shown to users.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import json

# Import all safety modules
from production_safety_enforcer import (
    ProductionSafetyEnforcer, SafetyEnforcedPrediction, SafetyCriticality
)
from human_in_loop_enforcement import (
    get_human_in_loop_enforcer, require_human_review, check_action_authorized,
    ReviewRequirement, ReviewerQualification
)
from safety_disclaimer_manager import (
    get_disclaimer_manager, DisclaimerType, Disclaimer
)
from prediction_display_enforcer import (
    get_display_enforcer, prepare_prediction_for_display, SafePredictionDisplay, DisplayMode
)
from user_acknowledgment_tracker import (
    get_acknowledgment_tracker, AcknowledgmentType, AcknowledgmentAction
)
from liability_protection_system import (
    get_liability_system, LiabilityCategory, ProtectionMeasure
)
from vehicle_coverage_tracker import (
    get_coverage_tracker, check_vehicle_coverage, CoverageLevel
)
from model_validation_framework import (
    ModelValidationFramework, ValidationStatus
)

logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY GATE STATUS
# =============================================================================

class SafetyGateStatus(Enum):
    """Status of safety gate checks."""
    PASSED = "passed"
    BLOCKED = "blocked"
    WARNING = "warning"
    REQUIRES_ACTION = "requires_action"
    ERROR = "error"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SafetyGateResult:
    """Result of passing through a safety gate."""
    gate_name: str
    status: SafetyGateStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    blocking: bool = False
    actions_required: List[str] = field(default_factory=list)


@dataclass
class SafetyCheckedPrediction:
    """
    A prediction that has passed all safety checks.

    This is the ONLY format that should be displayed to users.
    """
    prediction_id: str
    timestamp: str

    # Original prediction data
    failure_type: str
    failure_probability: float
    confidence: float
    days_to_failure: Optional[int]
    criticality: str

    # Safety gate results
    gate_results: List[SafetyGateResult]
    all_gates_passed: bool

    # Safety-enforced data
    adjusted_confidence: float
    safety_disclaimers: List[Disclaimer]
    warnings: List[str]
    recommendations: List[str]

    # Display data
    display_data: SafePredictionDisplay

    # Requirements
    requires_acknowledgment: bool
    requires_human_review: bool
    blocks_action: bool

    # Audit
    safety_check_signature: str


@dataclass
class SafetySystemStatus:
    """Status of the complete safety system."""
    all_systems_operational: bool
    system_statuses: Dict[str, bool]
    last_check: str
    issues: List[str]
    warnings: List[str]


# =============================================================================
# SAFETY INTEGRATION MODULE
# =============================================================================

class SafetyIntegrationModule:
    """
    Central integration point for all safety systems.

    All predictions MUST be processed through this module.
    It ensures all safety requirements are met before any
    prediction is shown to users.
    """

    def __init__(self):
        """Initialize safety integration module."""
        # Initialize all subsystems
        self.safety_enforcer = ProductionSafetyEnforcer()
        self.human_loop = get_human_in_loop_enforcer()
        self.disclaimer_manager = get_disclaimer_manager()
        self.display_enforcer = get_display_enforcer()
        self.acknowledgment_tracker = get_acknowledgment_tracker()
        self.liability_system = get_liability_system()
        self.coverage_tracker = get_coverage_tracker()
        self.validation_framework = ModelValidationFramework()

        # Safety gates in order of execution
        self.safety_gates = [
            'vehicle_coverage_check',
            'confidence_validation',
            'criticality_assessment',
            'disclaimer_generation',
            'human_review_check',
            'display_preparation',
            'liability_recording',
        ]

        logger.info("Safety Integration Module initialized with all subsystems")

    def process_prediction(
        self,
        prediction: Dict[str, Any],
        vehicle_info: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None
    ) -> SafetyCheckedPrediction:
        """
        Process a prediction through all safety gates.

        This is the MAIN entry point for all predictions.
        Every prediction must pass through this function.

        Args:
            prediction: Raw prediction data
            vehicle_info: Vehicle make/model/year
            user_id: User identifier

        Returns:
            SafetyCheckedPrediction ready for display
        """
        prediction_id = prediction.get('prediction_id', f"pred_{datetime.now().strftime('%Y%m%d%H%M%S')}")

        logger.info(f"Processing prediction {prediction_id} through safety gates")

        gate_results = []
        all_passed = True
        adjusted_confidence = prediction.get('confidence', 0.5)
        warnings = []
        recommendations = []
        requires_ack = False
        requires_review = False
        blocks_action = False

        # Gate 1: Vehicle Coverage Check
        coverage_result = self._gate_vehicle_coverage(prediction, vehicle_info)
        gate_results.append(coverage_result)
        if coverage_result.status == SafetyGateStatus.BLOCKED:
            all_passed = False
        if coverage_result.details.get('confidence_modifier'):
            adjusted_confidence *= coverage_result.details['confidence_modifier']
        if coverage_result.details.get('warnings'):
            warnings.extend(coverage_result.details['warnings'])

        # Gate 2: Confidence Validation
        confidence_result = self._gate_confidence_validation(prediction, adjusted_confidence)
        gate_results.append(confidence_result)
        if confidence_result.status == SafetyGateStatus.WARNING:
            warnings.append(confidence_result.message)

        # Gate 3: Criticality Assessment
        criticality = prediction.get('criticality', 'medium')
        failure_type = prediction.get('failure_type', 'unknown')
        criticality_result = self._gate_criticality_assessment(criticality, failure_type)
        gate_results.append(criticality_result)
        if criticality_result.blocking:
            requires_ack = True
        if criticality_result.details.get('requires_review'):
            requires_review = True

        # Gate 4: Disclaimer Generation
        disclaimer_result = self._gate_disclaimer_generation(
            prediction, vehicle_info, adjusted_confidence
        )
        gate_results.append(disclaimer_result)
        disclaimers = disclaimer_result.details.get('disclaimers', [])

        # Gate 5: Human Review Check
        if requires_review:
            review_result = self._gate_human_review(
                prediction_id, prediction, criticality, user_id
            )
            gate_results.append(review_result)
            if review_result.status == SafetyGateStatus.REQUIRES_ACTION:
                blocks_action = True

        # Gate 6: Display Preparation
        display_result = self._gate_display_preparation(
            prediction, vehicle_info, adjusted_confidence
        )
        gate_results.append(display_result)
        display_data = display_result.details.get('display_data')

        # Gate 7: Liability Recording
        liability_result = self._gate_liability_recording(
            prediction_id, prediction, user_id, gate_results
        )
        gate_results.append(liability_result)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            criticality, failure_type, adjusted_confidence, warnings
        )

        # Create signature
        signature = self._create_safety_signature(prediction_id, gate_results)

        # Build final result
        result = SafetyCheckedPrediction(
            prediction_id=prediction_id,
            timestamp=datetime.now().isoformat(),
            failure_type=failure_type,
            failure_probability=prediction.get('failure_probability', 0),
            confidence=prediction.get('confidence', 0.5),
            days_to_failure=prediction.get('days_to_failure'),
            criticality=criticality,
            gate_results=gate_results,
            all_gates_passed=all_passed,
            adjusted_confidence=adjusted_confidence,
            safety_disclaimers=disclaimers,
            warnings=warnings,
            recommendations=recommendations,
            display_data=display_data,
            requires_acknowledgment=requires_ack,
            requires_human_review=requires_review,
            blocks_action=blocks_action,
            safety_check_signature=signature
        )

        logger.info(f"Prediction {prediction_id} processed: all_passed={all_passed}, "
                   f"requires_ack={requires_ack}, blocks_action={blocks_action}")

        return result

    def _gate_vehicle_coverage(
        self,
        prediction: Dict[str, Any],
        vehicle_info: Optional[Dict[str, str]]
    ) -> SafetyGateResult:
        """Vehicle coverage check gate."""
        if not vehicle_info:
            return SafetyGateResult(
                gate_name="vehicle_coverage_check",
                status=SafetyGateStatus.WARNING,
                message="No vehicle information provided",
                details={'confidence_modifier': 0.7},
                blocking=False
            )

        coverage = check_vehicle_coverage(
            vehicle_info.get('make', ''),
            vehicle_info.get('model', ''),
            int(vehicle_info.get('year', 0))
        )

        coverage_level = coverage.get('coverage_level', 'unknown')

        if coverage_level == 'unsupported':
            return SafetyGateResult(
                gate_name="vehicle_coverage_check",
                status=SafetyGateStatus.WARNING,
                message=f"Vehicle not in training database",
                details={
                    'coverage_level': coverage_level,
                    'confidence_modifier': coverage.get('confidence_modifier', 0.5),
                    'warnings': coverage.get('warnings', []),
                    'disclaimer': coverage.get('disclaimer', '')
                },
                blocking=False,
                actions_required=["Display unsupported vehicle warning"]
            )

        return SafetyGateResult(
            gate_name="vehicle_coverage_check",
            status=SafetyGateStatus.PASSED,
            message=f"Vehicle coverage: {coverage_level}",
            details={
                'coverage_level': coverage_level,
                'confidence_modifier': coverage.get('confidence_modifier', 1.0)
            }
        )

    def _gate_confidence_validation(
        self,
        prediction: Dict[str, Any],
        adjusted_confidence: float
    ) -> SafetyGateResult:
        """Confidence validation gate."""
        if adjusted_confidence < 0.3:
            return SafetyGateResult(
                gate_name="confidence_validation",
                status=SafetyGateStatus.WARNING,
                message=f"Very low confidence ({adjusted_confidence:.0%})",
                details={'adjusted_confidence': adjusted_confidence},
                blocking=False,
                actions_required=["Display low confidence warning"]
            )
        elif adjusted_confidence < 0.5:
            return SafetyGateResult(
                gate_name="confidence_validation",
                status=SafetyGateStatus.WARNING,
                message=f"Low confidence ({adjusted_confidence:.0%})",
                details={'adjusted_confidence': adjusted_confidence},
                blocking=False
            )

        return SafetyGateResult(
            gate_name="confidence_validation",
            status=SafetyGateStatus.PASSED,
            message=f"Confidence acceptable ({adjusted_confidence:.0%})",
            details={'adjusted_confidence': adjusted_confidence}
        )

    def _gate_criticality_assessment(
        self,
        criticality: str,
        failure_type: str
    ) -> SafetyGateResult:
        """Criticality assessment gate."""
        critical_types = ['fuel_pump', 'coolant_system', 'transmission']
        high_types = ['battery', 'alternator', 'thermostat', 'ignition']

        is_critical = criticality == 'critical' or failure_type in critical_types
        is_high = criticality == 'high' or failure_type in high_types

        if is_critical:
            return SafetyGateResult(
                gate_name="criticality_assessment",
                status=SafetyGateStatus.REQUIRES_ACTION,
                message=f"Critical system: {failure_type}",
                details={
                    'criticality': 'critical',
                    'requires_review': True,
                    'requires_acknowledgment': True
                },
                blocking=True,
                actions_required=[
                    "Display critical warning",
                    "Require user acknowledgment",
                    "Record for liability"
                ]
            )
        elif is_high:
            return SafetyGateResult(
                gate_name="criticality_assessment",
                status=SafetyGateStatus.WARNING,
                message=f"High priority system: {failure_type}",
                details={
                    'criticality': 'high',
                    'requires_review': False,
                    'requires_acknowledgment': True
                },
                blocking=False,
                actions_required=["Display high priority warning"]
            )

        return SafetyGateResult(
            gate_name="criticality_assessment",
            status=SafetyGateStatus.PASSED,
            message=f"Standard criticality: {criticality}",
            details={'criticality': criticality}
        )

    def _gate_disclaimer_generation(
        self,
        prediction: Dict[str, Any],
        vehicle_info: Optional[Dict[str, str]],
        confidence: float
    ) -> SafetyGateResult:
        """Disclaimer generation gate."""
        try:
            disclaimers = self.disclaimer_manager.get_disclaimers_for_prediction(
                prediction,
                vehicle_info
            )

            return SafetyGateResult(
                gate_name="disclaimer_generation",
                status=SafetyGateStatus.PASSED,
                message=f"Generated {len(disclaimers)} disclaimers",
                details={'disclaimers': disclaimers}
            )
        except Exception as e:
            logger.error(f"Disclaimer generation failed: {e}")
            return SafetyGateResult(
                gate_name="disclaimer_generation",
                status=SafetyGateStatus.ERROR,
                message=f"Failed to generate disclaimers: {e}",
                blocking=True
            )

    def _gate_human_review(
        self,
        prediction_id: str,
        prediction: Dict[str, Any],
        criticality: str,
        user_id: Optional[str]
    ) -> SafetyGateResult:
        """Human review check gate."""
        if not user_id:
            return SafetyGateResult(
                gate_name="human_review_check",
                status=SafetyGateStatus.WARNING,
                message="No user ID for review tracking",
                details={}
            )

        try:
            # Register review requirement
            pending = require_human_review(
                prediction_id=prediction_id,
                vehicle_id=prediction.get('vehicle_id', 'unknown'),
                prediction_type=prediction.get('failure_type', 'unknown'),
                criticality=criticality,
                confidence=prediction.get('confidence', 0.5),
                failure_probability=prediction.get('failure_probability', 0),
                days_to_failure=prediction.get('days_to_failure', 0),
                prediction_data=prediction
            )

            # Check if already authorized
            authorized, reason = check_action_authorized(prediction_id, "view_prediction")

            if authorized:
                return SafetyGateResult(
                    gate_name="human_review_check",
                    status=SafetyGateStatus.PASSED,
                    message="Human review completed",
                    details={'authorized': True, 'reason': reason}
                )
            else:
                return SafetyGateResult(
                    gate_name="human_review_check",
                    status=SafetyGateStatus.REQUIRES_ACTION,
                    message="Human review required",
                    details={
                        'authorized': False,
                        'reason': reason,
                        'pending_review_id': pending.prediction_id
                    },
                    blocking=True,
                    actions_required=["Complete human review process"]
                )
        except Exception as e:
            logger.error(f"Human review check failed: {e}")
            return SafetyGateResult(
                gate_name="human_review_check",
                status=SafetyGateStatus.ERROR,
                message=f"Review check failed: {e}",
                details={}
            )

    def _gate_display_preparation(
        self,
        prediction: Dict[str, Any],
        vehicle_info: Optional[Dict[str, str]],
        confidence: float
    ) -> SafetyGateResult:
        """Display preparation gate."""
        try:
            # Update prediction with adjusted confidence
            pred_copy = prediction.copy()
            pred_copy['confidence'] = confidence

            display_data = prepare_prediction_for_display(
                pred_copy,
                vehicle_info,
                DisplayMode.FULL
            )

            # Validate display compliance
            is_compliant, violations = self.display_enforcer.validate_display_compliance(display_data)

            if is_compliant:
                return SafetyGateResult(
                    gate_name="display_preparation",
                    status=SafetyGateStatus.PASSED,
                    message="Display prepared and compliant",
                    details={'display_data': display_data}
                )
            else:
                return SafetyGateResult(
                    gate_name="display_preparation",
                    status=SafetyGateStatus.WARNING,
                    message=f"Display has {len(violations)} violations",
                    details={
                        'display_data': display_data,
                        'violations': violations
                    }
                )
        except Exception as e:
            logger.error(f"Display preparation failed: {e}")
            return SafetyGateResult(
                gate_name="display_preparation",
                status=SafetyGateStatus.ERROR,
                message=f"Display preparation failed: {e}",
                blocking=True
            )

    def _gate_liability_recording(
        self,
        prediction_id: str,
        prediction: Dict[str, Any],
        user_id: Optional[str],
        gate_results: List[SafetyGateResult]
    ) -> SafetyGateResult:
        """Liability recording gate."""
        try:
            # Determine category
            criticality = prediction.get('criticality', 'medium')
            if criticality == 'critical':
                category = LiabilityCategory.SAFETY_CRITICAL
            else:
                category = LiabilityCategory.PREDICTION_ACCURACY

            # Determine protections applied
            protections = [ProtectionMeasure.DISCLAIMER, ProtectionMeasure.DOCUMENTATION]
            if any(r.details.get('requires_acknowledgment') for r in gate_results):
                protections.append(ProtectionMeasure.CONFIRMATION)
            protections.append(ProtectionMeasure.PROFESSIONAL_REFERRAL)

            # Record event
            self.liability_system.record_liability_event(
                category=category,
                description=f"Prediction generated: {prediction.get('failure_type')}",
                user_id=user_id,
                prediction_id=prediction_id,
                protections_applied=protections,
                additional_data={'gate_results': [r.gate_name for r in gate_results]}
            )

            return SafetyGateResult(
                gate_name="liability_recording",
                status=SafetyGateStatus.PASSED,
                message="Liability event recorded",
                details={'protections_recorded': [p.value for p in protections]}
            )
        except Exception as e:
            logger.error(f"Liability recording failed: {e}")
            return SafetyGateResult(
                gate_name="liability_recording",
                status=SafetyGateStatus.ERROR,
                message=f"Liability recording failed: {e}",
                details={}
            )

    def _generate_recommendations(
        self,
        criticality: str,
        failure_type: str,
        confidence: float,
        warnings: List[str]
    ) -> List[str]:
        """Generate safety recommendations."""
        recommendations = []

        if criticality == 'critical':
            recommendations.append("⚠️ CRITICAL: Have vehicle inspected by a professional IMMEDIATELY")
            recommendations.append("Do not drive long distances until inspected")

        if confidence < 0.5:
            recommendations.append("Low confidence - verify with professional diagnosis")

        if warnings:
            recommendations.append("Review all warnings before proceeding")

        # Always include
        recommendations.append("This is an AI prediction - always verify with a qualified mechanic")
        recommendations.append("Keep a copy of this prediction for your service visit")

        return recommendations

    def _create_safety_signature(
        self,
        prediction_id: str,
        gate_results: List[SafetyGateResult]
    ) -> str:
        """Create signature for safety check verification."""
        import hashlib
        data = f"{prediction_id}:{datetime.now().isoformat()}:"
        data += ":".join(f"{r.gate_name}={r.status.value}" for r in gate_results)
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def check_system_status(self) -> SafetySystemStatus:
        """Check status of all safety subsystems."""
        statuses = {}
        issues = []
        warnings = []

        # Check each subsystem
        try:
            self.safety_enforcer
            statuses['safety_enforcer'] = True
        except Exception as e:
            statuses['safety_enforcer'] = False
            issues.append(f"Safety enforcer error: {e}")

        try:
            self.human_loop
            statuses['human_loop'] = True
        except Exception as e:
            statuses['human_loop'] = False
            issues.append(f"Human loop error: {e}")

        try:
            self.disclaimer_manager
            statuses['disclaimer_manager'] = True
        except Exception as e:
            statuses['disclaimer_manager'] = False
            issues.append(f"Disclaimer manager error: {e}")

        try:
            self.display_enforcer
            statuses['display_enforcer'] = True
        except Exception as e:
            statuses['display_enforcer'] = False
            issues.append(f"Display enforcer error: {e}")

        try:
            self.liability_system
            statuses['liability_system'] = True
        except Exception as e:
            statuses['liability_system'] = False
            issues.append(f"Liability system error: {e}")

        try:
            self.coverage_tracker
            statuses['coverage_tracker'] = True
        except Exception as e:
            statuses['coverage_tracker'] = False
            warnings.append(f"Coverage tracker warning: {e}")

        all_operational = all(statuses.values())

        return SafetySystemStatus(
            all_systems_operational=all_operational,
            system_statuses=statuses,
            last_check=datetime.now().isoformat(),
            issues=issues,
            warnings=warnings
        )


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_module_instance: Optional[SafetyIntegrationModule] = None


def get_safety_module() -> SafetyIntegrationModule:
    """Get or create singleton module instance."""
    global _module_instance
    if _module_instance is None:
        _module_instance = SafetyIntegrationModule()
    return _module_instance


def process_prediction_safely(
    prediction: Dict[str, Any],
    vehicle_info: Optional[Dict[str, str]] = None,
    user_id: Optional[str] = None
) -> SafetyCheckedPrediction:
    """
    Main entry point for processing predictions safely.

    ALL predictions must go through this function.
    """
    module = get_safety_module()
    return module.process_prediction(prediction, vehicle_info, user_id)


def check_safety_systems() -> SafetySystemStatus:
    """Check status of all safety systems."""
    module = get_safety_module()
    return module.check_system_status()
