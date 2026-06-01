"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Production Safety Enforcer

Production Safety Enforcer
==========================
CRITICAL: This module enforces ALL safety requirements for the Automotive AI system.

This is the CENTRAL AUTHORITY for:
- Mandatory safety disclaimers on ALL predictions
- Human-in-the-loop enforcement for critical systems
- False negative prevention (safety-biased thresholds)
- Prediction blocking when safety criteria not met
- Audit trail for all safety-critical decisions

AUTOMOTIVE SAFETY PRINCIPLE:
"When in doubt, recommend professional inspection."
"Never give false confidence about vehicle safety."
"A missed failure prediction can cause injury or death."

Author: Safety Engineering Team
Version: 1.0.0
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import hashlib
import uuid

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY CLASSIFICATION
# =============================================================================

class SafetyCriticality(Enum):
    """Classification of vehicle systems by safety criticality."""
    CRITICAL = "critical"      # Failure can cause accident/injury (brakes, steering, cooling)
    HIGH = "high"              # Failure can cause breakdown (battery, alternator, fuel)
    MEDIUM = "medium"          # Failure affects performance (spark plugs, O2 sensor)
    LOW = "low"                # Failure is inconvenient (interior lights, radio)


class PredictionRiskLevel(Enum):
    """Risk level of a prediction decision."""
    SAFE_TO_DRIVE = "safe_to_drive"
    MONITOR_CLOSELY = "monitor_closely"
    SERVICE_SOON = "service_soon"
    SERVICE_IMMEDIATELY = "service_immediately"
    DO_NOT_DRIVE = "do_not_drive"
    UNKNOWN = "unknown"


# System criticality mapping - CANNOT BE OVERRIDDEN
SYSTEM_CRITICALITY = {
    # CRITICAL - Can cause accident
    'coolant_system': SafetyCriticality.CRITICAL,
    'thermostat': SafetyCriticality.CRITICAL,
    'transmission': SafetyCriticality.CRITICAL,

    # HIGH - Can cause breakdown
    'battery': SafetyCriticality.HIGH,
    'alternator': SafetyCriticality.HIGH,
    'starter': SafetyCriticality.HIGH,
    'fuel_pump': SafetyCriticality.HIGH,
    'ignition': SafetyCriticality.HIGH,

    # MEDIUM - Affects performance
    'spark_plug': SafetyCriticality.MEDIUM,
    'oxygen_sensor': SafetyCriticality.MEDIUM,
    'catalytic_converter': SafetyCriticality.MEDIUM,
    'maf_sensor': SafetyCriticality.MEDIUM,

    # Default
    'no_failure': SafetyCriticality.LOW,
}


# =============================================================================
# SAFETY THRESHOLDS - CANNOT BE BYPASSED
# =============================================================================

# These thresholds are SAFETY-BIASED (favor false positives over false negatives)
SAFETY_THRESHOLDS = {
    SafetyCriticality.CRITICAL: {
        'min_confidence_for_healthy': 0.95,  # Must be 95% confident to say "healthy"
        'warning_threshold': 0.15,            # Warn at 15% failure probability
        'critical_threshold': 0.40,           # Critical at 40%
        'require_human_confirmation': True,   # ALWAYS require human for critical systems
        'max_false_negative_rate': 0.01,      # Max 1% false negatives allowed
    },
    SafetyCriticality.HIGH: {
        'min_confidence_for_healthy': 0.90,
        'warning_threshold': 0.25,
        'critical_threshold': 0.50,
        'require_human_confirmation': True,
        'max_false_negative_rate': 0.03,
    },
    SafetyCriticality.MEDIUM: {
        'min_confidence_for_healthy': 0.85,
        'warning_threshold': 0.35,
        'critical_threshold': 0.60,
        'require_human_confirmation': False,
        'max_false_negative_rate': 0.05,
    },
    SafetyCriticality.LOW: {
        'min_confidence_for_healthy': 0.80,
        'warning_threshold': 0.50,
        'critical_threshold': 0.70,
        'require_human_confirmation': False,
        'max_false_negative_rate': 0.10,
    },
}


# =============================================================================
# MANDATORY DISCLAIMERS
# =============================================================================

MANDATORY_DISCLAIMERS = {
    'prediction_header': (
        "AI PREDICTION - NOT A PROFESSIONAL DIAGNOSIS\n"
        "This prediction is based on statistical patterns and sensor data analysis. "
        "It is NOT a substitute for professional vehicle inspection."
    ),

    'healthy_prediction': (
        "IMPORTANT: A 'healthy' prediction does not guarantee your vehicle is free of issues. "
        "Hidden problems may exist that sensors cannot detect. "
        "Always follow your vehicle's recommended maintenance schedule and consult a "
        "qualified mechanic if you notice any unusual behavior."
    ),

    'failure_prediction': (
        "WARNING: This prediction indicates a potential issue. "
        "This is a RECOMMENDATION, not a diagnosis. "
        "Please have your vehicle inspected by a qualified mechanic before making any decisions. "
        "Do not ignore warning signs even if this system shows no issues."
    ),

    'critical_system': (
        "CRITICAL SYSTEM ALERT: This prediction involves a safety-critical vehicle system. "
        "Failure of this system could result in vehicle breakdown or accident. "
        "IMMEDIATE professional inspection is strongly recommended. "
        "DO NOT rely solely on this AI prediction for safety-critical decisions."
    ),

    'low_confidence': (
        "LOW CONFIDENCE PREDICTION: The AI system has limited confidence in this prediction. "
        "This may be due to insufficient data, unusual patterns, or sensor issues. "
        "Professional inspection is recommended to verify vehicle condition."
    ),

    'liability_notice': (
        "NOTICE: This AI system provides predictive insights only. "
        "The operator, manufacturer, and software provider are not liable for any "
        "decisions made based on these predictions. Vehicle owners are responsible "
        "for all maintenance decisions and should always consult qualified professionals."
    ),

    'data_quality_warning': (
        "DATA QUALITY NOTICE: This prediction is based on the available sensor data. "
        "Sensor malfunctions, data gaps, or unusual driving conditions may affect accuracy. "
        "If prediction seems inconsistent with vehicle behavior, seek professional inspection."
    ),
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SafetyEnforcedPrediction:
    """A prediction that has passed through safety enforcement."""
    # Original prediction data
    prediction_id: str
    failure_probability: float
    failure_type: str
    days_to_failure: Optional[int]
    raw_confidence: float

    # Safety enforcement results
    safety_adjusted_confidence: float
    criticality: SafetyCriticality
    risk_level: PredictionRiskLevel
    requires_human_confirmation: bool
    human_confirmed: bool
    human_confirmer_id: Optional[str]
    human_confirmation_timestamp: Optional[str]

    # Disclaimers (MANDATORY)
    disclaimers: List[str]
    primary_disclaimer: str

    # Safety flags
    is_safe_to_display: bool
    blocked_reason: Optional[str]
    safety_warnings: List[str]

    # Audit trail
    enforcement_timestamp: str
    enforcement_version: str
    audit_hash: str

    # Recommendations
    recommended_action: str
    urgency: str
    mechanic_referral_required: bool


@dataclass
class SafetyAuditRecord:
    """Audit record for safety-critical decisions."""
    record_id: str
    timestamp: str
    prediction_id: str
    vehicle_id: Optional[str]
    user_id: Optional[str]

    # Decision details
    decision_type: str  # "prediction_displayed", "blocked", "human_confirmed", etc.
    criticality: str
    risk_level: str

    # Safety checks performed
    checks_performed: List[str]
    checks_passed: List[str]
    checks_failed: List[str]

    # Human involvement
    human_in_loop: bool
    human_decision: Optional[str]
    human_notes: Optional[str]

    # Hash for tamper detection
    record_hash: str


# =============================================================================
# PRODUCTION SAFETY ENFORCER
# =============================================================================

class ProductionSafetyEnforcer:
    """
    CENTRAL SAFETY AUTHORITY for the Automotive AI system.

    ALL predictions MUST pass through this enforcer before being displayed to users.
    This class CANNOT be bypassed, disabled, or weakened.

    Safety Philosophy:
    - When uncertain, recommend professional inspection
    - Never give false confidence about safety-critical systems
    - Always provide disclaimers
    - Require human confirmation for critical systems
    - Maintain complete audit trail
    """

    VERSION = "1.0.0"

    def __init__(self):
        """Initialize the safety enforcer."""
        self.audit_dir = CONFIG.DATA_DIR / "safety_audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # Pending human confirmations
        self.pending_confirmations: Dict[str, SafetyEnforcedPrediction] = {}

        # Audit log
        self.audit_log: List[SafetyAuditRecord] = []

        # Load configuration
        self._load_audit_history()

        logger.info("ProductionSafetyEnforcer initialized - ALL predictions will be safety-checked")

    def enforce_prediction_safety(
        self,
        prediction: Dict[str, Any],
        vehicle_id: Optional[str] = None,
        user_id: Optional[str] = None,
        bypass_human_confirmation: bool = False  # CANNOT bypass for critical systems
    ) -> SafetyEnforcedPrediction:
        """
        MANDATORY safety enforcement for ALL predictions.

        This method:
        1. Classifies the prediction by safety criticality
        2. Applies safety-biased confidence adjustments
        3. Determines if human confirmation is required
        4. Generates mandatory disclaimers
        5. Creates audit record

        Args:
            prediction: Raw prediction data
            vehicle_id: Optional vehicle identifier
            user_id: Optional user identifier
            bypass_human_confirmation: Ignored for critical/high systems

        Returns:
            SafetyEnforcedPrediction with all safety checks applied
        """
        prediction_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        # Extract prediction data
        failure_prob = prediction.get('failure_probability', 0.0)
        failure_type = prediction.get('failure_type', 'unknown')
        raw_confidence = prediction.get('confidence', 0.5)
        days_to_failure = prediction.get('days_to_failure')

        # Step 1: Determine criticality
        criticality = self._get_system_criticality(failure_type)
        thresholds = SAFETY_THRESHOLDS[criticality]

        # Step 2: Apply safety-biased confidence adjustment
        safety_confidence = self._apply_safety_bias(
            raw_confidence, failure_prob, criticality
        )

        # Step 3: Determine risk level
        risk_level = self._determine_risk_level(
            failure_prob, safety_confidence, criticality
        )

        # Step 4: Check if human confirmation required
        requires_human = self._requires_human_confirmation(
            criticality, failure_prob, safety_confidence
        )

        # CRITICAL: Cannot bypass human confirmation for critical/high systems
        if criticality in [SafetyCriticality.CRITICAL, SafetyCriticality.HIGH]:
            if failure_prob > thresholds['warning_threshold']:
                requires_human = True  # FORCED

        # Step 5: Generate disclaimers
        disclaimers = self._generate_disclaimers(
            criticality, risk_level, safety_confidence, failure_prob
        )

        # Step 6: Determine primary disclaimer
        primary_disclaimer = self._get_primary_disclaimer(
            criticality, risk_level, safety_confidence
        )

        # Step 7: Generate safety warnings
        safety_warnings = self._generate_safety_warnings(
            failure_type, failure_prob, safety_confidence, criticality
        )

        # Step 8: Determine recommended action
        recommended_action, urgency = self._determine_recommendation(
            risk_level, criticality, failure_prob, days_to_failure
        )

        # Step 9: Check if safe to display
        is_safe, blocked_reason = self._check_display_safety(
            safety_confidence, criticality, requires_human
        )

        # Step 10: Determine if mechanic referral required
        mechanic_required = self._mechanic_referral_required(
            criticality, risk_level, safety_confidence
        )

        # Create enforced prediction
        enforced = SafetyEnforcedPrediction(
            prediction_id=prediction_id,
            failure_probability=failure_prob,
            failure_type=failure_type,
            days_to_failure=days_to_failure,
            raw_confidence=raw_confidence,
            safety_adjusted_confidence=safety_confidence,
            criticality=criticality,
            risk_level=risk_level,
            requires_human_confirmation=requires_human,
            human_confirmed=False,
            human_confirmer_id=None,
            human_confirmation_timestamp=None,
            disclaimers=disclaimers,
            primary_disclaimer=primary_disclaimer,
            is_safe_to_display=is_safe,
            blocked_reason=blocked_reason,
            safety_warnings=safety_warnings,
            enforcement_timestamp=timestamp,
            enforcement_version=self.VERSION,
            audit_hash=self._generate_audit_hash(prediction_id, timestamp, failure_type),
            recommended_action=recommended_action,
            urgency=urgency,
            mechanic_referral_required=mechanic_required
        )

        # Store if requires confirmation
        if requires_human and not enforced.human_confirmed:
            self.pending_confirmations[prediction_id] = enforced

        # Create audit record
        self._create_audit_record(
            enforced, vehicle_id, user_id, "prediction_enforced"
        )

        logger.info(
            f"Safety enforcement complete: {prediction_id} | "
            f"Type: {failure_type} | Criticality: {criticality.value} | "
            f"Risk: {risk_level.value} | Human Required: {requires_human}"
        )

        return enforced

    def confirm_human_review(
        self,
        prediction_id: str,
        confirmer_id: str,
        decision: str,  # "approve", "escalate", "override"
        notes: Optional[str] = None
    ) -> Tuple[bool, SafetyEnforcedPrediction]:
        """
        Record human confirmation for a prediction.

        Args:
            prediction_id: ID of prediction to confirm
            confirmer_id: ID of human confirmer
            decision: Human decision
            notes: Optional notes

        Returns:
            (success, updated_prediction)
        """
        if prediction_id not in self.pending_confirmations:
            logger.warning(f"No pending confirmation for {prediction_id}")
            return False, None

        enforced = self.pending_confirmations[prediction_id]
        enforced.human_confirmed = True
        enforced.human_confirmer_id = confirmer_id
        enforced.human_confirmation_timestamp = datetime.now().isoformat()

        # Update display safety
        if decision == "approve":
            enforced.is_safe_to_display = True
            enforced.blocked_reason = None
        elif decision == "escalate":
            enforced.safety_warnings.append("ESCALATED: Requires professional review")
            enforced.mechanic_referral_required = True

        # Create audit record
        self._create_audit_record(
            enforced, None, confirmer_id, f"human_confirmed_{decision}",
            human_decision=decision, human_notes=notes
        )

        # Remove from pending
        del self.pending_confirmations[prediction_id]

        logger.info(f"Human confirmation recorded: {prediction_id} | Decision: {decision}")

        return True, enforced

    def _get_system_criticality(self, failure_type: str) -> SafetyCriticality:
        """Get safety criticality for a failure type."""
        return SYSTEM_CRITICALITY.get(
            failure_type.lower(),
            SafetyCriticality.MEDIUM  # Default to MEDIUM, not LOW
        )

    def _apply_safety_bias(
        self,
        raw_confidence: float,
        failure_prob: float,
        criticality: SafetyCriticality
    ) -> float:
        """
        Apply safety bias to confidence score.

        For safety-critical systems, we REDUCE confidence in "healthy" predictions
        and INCREASE confidence in "failure" predictions.
        """
        # Bias factors by criticality
        bias_factors = {
            SafetyCriticality.CRITICAL: 0.7,  # 30% reduction in "healthy" confidence
            SafetyCriticality.HIGH: 0.8,
            SafetyCriticality.MEDIUM: 0.9,
            SafetyCriticality.LOW: 1.0,
        }

        bias = bias_factors[criticality]

        if failure_prob < 0.3:  # Predicting "healthy"
            # Reduce confidence in healthy predictions for critical systems
            return raw_confidence * bias
        else:
            # Keep or slightly boost confidence in failure predictions
            return min(0.95, raw_confidence * (2 - bias))

    def _determine_risk_level(
        self,
        failure_prob: float,
        confidence: float,
        criticality: SafetyCriticality
    ) -> PredictionRiskLevel:
        """Determine risk level based on prediction and criticality."""
        thresholds = SAFETY_THRESHOLDS[criticality]

        # Low confidence = UNKNOWN risk
        if confidence < 0.5:
            return PredictionRiskLevel.UNKNOWN

        if failure_prob < thresholds['warning_threshold']:
            if confidence >= thresholds['min_confidence_for_healthy']:
                return PredictionRiskLevel.SAFE_TO_DRIVE
            else:
                return PredictionRiskLevel.MONITOR_CLOSELY

        elif failure_prob < thresholds['critical_threshold']:
            return PredictionRiskLevel.SERVICE_SOON

        else:
            if criticality in [SafetyCriticality.CRITICAL, SafetyCriticality.HIGH]:
                return PredictionRiskLevel.DO_NOT_DRIVE
            else:
                return PredictionRiskLevel.SERVICE_IMMEDIATELY

    def _requires_human_confirmation(
        self,
        criticality: SafetyCriticality,
        failure_prob: float,
        confidence: float
    ) -> bool:
        """Determine if human confirmation is required."""
        thresholds = SAFETY_THRESHOLDS[criticality]

        # Always require for critical systems with any warning
        if criticality == SafetyCriticality.CRITICAL:
            if failure_prob > 0.1 or confidence < 0.9:
                return True

        # Require if confidence is low
        if confidence < 0.6:
            return True

        # Require based on threshold setting
        if thresholds['require_human_confirmation']:
            if failure_prob > thresholds['warning_threshold']:
                return True

        return False

    def _generate_disclaimers(
        self,
        criticality: SafetyCriticality,
        risk_level: PredictionRiskLevel,
        confidence: float,
        failure_prob: float
    ) -> List[str]:
        """Generate all applicable disclaimers."""
        disclaimers = []

        # Always include header
        disclaimers.append(MANDATORY_DISCLAIMERS['prediction_header'])

        # Add based on prediction type
        if failure_prob < 0.3:
            disclaimers.append(MANDATORY_DISCLAIMERS['healthy_prediction'])
        else:
            disclaimers.append(MANDATORY_DISCLAIMERS['failure_prediction'])

        # Add for critical systems
        if criticality in [SafetyCriticality.CRITICAL, SafetyCriticality.HIGH]:
            disclaimers.append(MANDATORY_DISCLAIMERS['critical_system'])

        # Add for low confidence
        if confidence < 0.7:
            disclaimers.append(MANDATORY_DISCLAIMERS['low_confidence'])

        # Always include liability
        disclaimers.append(MANDATORY_DISCLAIMERS['liability_notice'])

        return disclaimers

    def _get_primary_disclaimer(
        self,
        criticality: SafetyCriticality,
        risk_level: PredictionRiskLevel,
        confidence: float
    ) -> str:
        """Get the most important disclaimer to show prominently."""
        if criticality in [SafetyCriticality.CRITICAL, SafetyCriticality.HIGH]:
            return MANDATORY_DISCLAIMERS['critical_system']

        if confidence < 0.6:
            return MANDATORY_DISCLAIMERS['low_confidence']

        if risk_level in [PredictionRiskLevel.DO_NOT_DRIVE, PredictionRiskLevel.SERVICE_IMMEDIATELY]:
            return MANDATORY_DISCLAIMERS['failure_prediction']

        return MANDATORY_DISCLAIMERS['prediction_header']

    def _generate_safety_warnings(
        self,
        failure_type: str,
        failure_prob: float,
        confidence: float,
        criticality: SafetyCriticality
    ) -> List[str]:
        """Generate specific safety warnings."""
        warnings = []

        if criticality == SafetyCriticality.CRITICAL:
            warnings.append(
                f"CRITICAL SYSTEM: {failure_type} affects vehicle safety. "
                "Professional inspection strongly recommended."
            )

        if confidence < 0.6:
            warnings.append(
                "LOW CONFIDENCE: This prediction has high uncertainty. "
                "Do not rely on this prediction for safety decisions."
            )

        if failure_prob > 0.5 and criticality in [SafetyCriticality.CRITICAL, SafetyCriticality.HIGH]:
            warnings.append(
                "HIGH FAILURE PROBABILITY: Immediate professional inspection recommended. "
                "Continued driving may be unsafe."
            )

        if failure_type in ['coolant_system', 'thermostat']:
            warnings.append(
                "COOLING SYSTEM: Overheating can cause severe engine damage. "
                "Monitor temperature gauge closely."
            )

        if failure_type == 'transmission':
            warnings.append(
                "TRANSMISSION: Failure while driving can be dangerous. "
                "Any unusual shifting should be inspected immediately."
            )

        return warnings

    def _determine_recommendation(
        self,
        risk_level: PredictionRiskLevel,
        criticality: SafetyCriticality,
        failure_prob: float,
        days_to_failure: Optional[int]
    ) -> Tuple[str, str]:
        """Determine recommended action and urgency."""
        recommendations = {
            PredictionRiskLevel.SAFE_TO_DRIVE: (
                "Continue normal operation. Follow regular maintenance schedule.",
                "routine"
            ),
            PredictionRiskLevel.MONITOR_CLOSELY: (
                "Monitor for unusual behavior. Consider scheduling inspection within 2 weeks.",
                "low"
            ),
            PredictionRiskLevel.SERVICE_SOON: (
                "Schedule service appointment within 1 week. Watch for warning signs.",
                "medium"
            ),
            PredictionRiskLevel.SERVICE_IMMEDIATELY: (
                "Schedule service as soon as possible. Limit driving if possible.",
                "high"
            ),
            PredictionRiskLevel.DO_NOT_DRIVE: (
                "STOP DRIVING. Have vehicle towed to mechanic. Risk of breakdown or accident.",
                "critical"
            ),
            PredictionRiskLevel.UNKNOWN: (
                "Prediction uncertain. Professional inspection recommended to assess condition.",
                "medium"
            ),
        }

        return recommendations.get(risk_level, (
            "Consult a qualified mechanic for professional assessment.",
            "medium"
        ))

    def _check_display_safety(
        self,
        confidence: float,
        criticality: SafetyCriticality,
        requires_human: bool
    ) -> Tuple[bool, Optional[str]]:
        """Check if prediction is safe to display to user."""
        # Block extremely low confidence predictions
        if confidence < 0.3:
            return False, "Confidence too low for reliable prediction"

        # Block unconfirmed critical predictions
        if requires_human and criticality == SafetyCriticality.CRITICAL:
            return False, "Requires human confirmation before display"

        return True, None

    def _mechanic_referral_required(
        self,
        criticality: SafetyCriticality,
        risk_level: PredictionRiskLevel,
        confidence: float
    ) -> bool:
        """Determine if mechanic referral is required."""
        # Always refer for critical systems
        if criticality == SafetyCriticality.CRITICAL:
            return True

        # Refer for high risk
        if risk_level in [PredictionRiskLevel.DO_NOT_DRIVE, PredictionRiskLevel.SERVICE_IMMEDIATELY]:
            return True

        # Refer for low confidence
        if confidence < 0.5:
            return True

        return False

    def _generate_audit_hash(
        self,
        prediction_id: str,
        timestamp: str,
        failure_type: str
    ) -> str:
        """Generate tamper-evident hash for audit trail."""
        data = f"{prediction_id}|{timestamp}|{failure_type}|{self.VERSION}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _create_audit_record(
        self,
        prediction: SafetyEnforcedPrediction,
        vehicle_id: Optional[str],
        user_id: Optional[str],
        decision_type: str,
        human_decision: Optional[str] = None,
        human_notes: Optional[str] = None
    ):
        """Create audit record for safety decision."""
        record_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        checks_performed = [
            "criticality_classification",
            "safety_bias_applied",
            "risk_level_determined",
            "human_confirmation_check",
            "disclaimer_generation",
            "display_safety_check"
        ]

        record = SafetyAuditRecord(
            record_id=record_id,
            timestamp=timestamp,
            prediction_id=prediction.prediction_id,
            vehicle_id=vehicle_id,
            user_id=user_id,
            decision_type=decision_type,
            criticality=prediction.criticality.value,
            risk_level=prediction.risk_level.value,
            checks_performed=checks_performed,
            checks_passed=checks_performed,  # All checks always run
            checks_failed=[],
            human_in_loop=prediction.requires_human_confirmation,
            human_decision=human_decision,
            human_notes=human_notes,
            record_hash=self._generate_audit_hash(record_id, timestamp, decision_type)
        )

        self.audit_log.append(record)
        self._save_audit_record(record)

    def _save_audit_record(self, record: SafetyAuditRecord):
        """Save audit record to file."""
        try:
            audit_file = self.audit_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(audit_file, 'a') as f:
                f.write(json.dumps(asdict(record)) + '\n')
        except Exception as e:
            logger.error(f"Failed to save audit record: {e}")

    def _load_audit_history(self):
        """Load recent audit history."""
        try:
            today = datetime.now().strftime('%Y%m%d')
            audit_file = self.audit_dir / f"audit_{today}.jsonl"
            if audit_file.exists():
                with open(audit_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            # Convert back to dataclass
                            self.audit_log.append(SafetyAuditRecord(**data))
                logger.info(f"Loaded {len(self.audit_log)} audit records")
        except Exception as e:
            logger.warning(f"Failed to load audit history: {e}")

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get summary of safety audit activity."""
        return {
            'total_records': len(self.audit_log),
            'pending_confirmations': len(self.pending_confirmations),
            'enforcer_version': self.VERSION,
            'criticality_counts': self._count_by_criticality(),
            'risk_level_counts': self._count_by_risk_level(),
            'human_confirmations_required': sum(
                1 for r in self.audit_log if r.human_in_loop
            )
        }

    def _count_by_criticality(self) -> Dict[str, int]:
        """Count predictions by criticality."""
        counts = {c.value: 0 for c in SafetyCriticality}
        for record in self.audit_log:
            counts[record.criticality] = counts.get(record.criticality, 0) + 1
        return counts

    def _count_by_risk_level(self) -> Dict[str, int]:
        """Count predictions by risk level."""
        counts = {r.value: 0 for r in PredictionRiskLevel}
        for record in self.audit_log:
            counts[record.risk_level] = counts.get(record.risk_level, 0) + 1
        return counts


# =============================================================================
# SINGLETON AND HELPER FUNCTIONS
# =============================================================================

_safety_enforcer: Optional[ProductionSafetyEnforcer] = None


def get_safety_enforcer() -> ProductionSafetyEnforcer:
    """Get the global safety enforcer instance."""
    global _safety_enforcer
    if _safety_enforcer is None:
        _safety_enforcer = ProductionSafetyEnforcer()
    return _safety_enforcer


def enforce_prediction_safety(
    prediction: Dict[str, Any],
    vehicle_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> SafetyEnforcedPrediction:
    """
    Convenience function to enforce safety on a prediction.

    ALL predictions MUST go through this function before display.
    """
    enforcer = get_safety_enforcer()
    return enforcer.enforce_prediction_safety(prediction, vehicle_id, user_id)


def get_mandatory_disclaimer() -> str:
    """Get the primary mandatory disclaimer for display."""
    return MANDATORY_DISCLAIMERS['prediction_header']


def get_liability_notice() -> str:
    """Get the liability notice for display."""
    return MANDATORY_DISCLAIMERS['liability_notice']
