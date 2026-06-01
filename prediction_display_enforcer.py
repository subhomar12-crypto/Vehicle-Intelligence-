"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Prediction Display Enforcer

Prediction Display Enforcer
============================
Enforces safe display of predictions to users.
Ensures all predictions are shown with appropriate context, warnings, and disclaimers.

CRITICAL: This module acts as the final gate before predictions are shown to users.
It ensures compliance with safety requirements regardless of how predictions are accessed.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from safety_disclaimer_manager import (
    get_disclaimer_manager, Disclaimer, DisclaimerType, DisclaimerSeverity
)
from vehicle_coverage_tracker import get_coverage_tracker, CoverageLevel

logger = logging.getLogger(__name__)


# =============================================================================
# DISPLAY CONFIGURATION
# =============================================================================

class DisplayMode(Enum):
    """How prediction should be displayed."""
    FULL = "full"              # Full details with all warnings
    SUMMARY = "summary"        # Summary view
    MINIMAL = "minimal"        # Minimal info (for dashboards)
    API = "api"                # API response format


class ConfidenceDisplay(Enum):
    """How to display confidence levels."""
    PERCENTAGE = "percentage"  # 75%
    LEVEL = "level"            # High/Medium/Low
    BOTH = "both"              # High (75%)
    NONE = "none"              # Don't show (dangerous, requires override)


# =============================================================================
# DISPLAY RULES
# =============================================================================

# Minimum requirements for displaying predictions
DISPLAY_REQUIREMENTS = {
    # What must be shown with every prediction
    'always_show': [
        'failure_type',
        'confidence_indicator',
        'disclaimer_link',
        'professional_advice_note',
    ],

    # Additional items for critical predictions
    'critical_show': [
        'urgency_warning',
        'safety_implications',
        'immediate_action_required',
        'full_disclaimer',
    ],

    # Items that must NEVER be hidden
    'never_hide': [
        'disclaimer_link',
        'professional_advice_note',
    ],

    # Maximum confidence display (to prevent overconfidence)
    'max_displayed_confidence': 0.95,  # Never show > 95% confidence

    # Minimum display time for warnings (seconds)
    'min_warning_display_time': 3,
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DisplayElement:
    """An element to be displayed."""
    element_type: str
    content: str
    priority: int  # Lower = higher priority (shown first)
    required: bool
    style: str = "normal"  # "normal", "warning", "critical", "info"


@dataclass
class SafePredictionDisplay:
    """
    A safely formatted prediction for display.

    All predictions MUST be converted to this format before display.
    """
    display_id: str
    prediction_id: str
    timestamp: str

    # Core prediction info
    failure_type: str
    failure_probability: float
    displayed_confidence: float  # May be capped
    confidence_level: str
    days_to_failure: Optional[int]
    urgency: str

    # Safety elements
    warnings: List[DisplayElement]
    disclaimers: List[Disclaimer]
    safety_notes: List[str]

    # Display configuration
    requires_acknowledgment: bool
    blocks_until_acknowledged: bool
    minimum_display_time: int  # seconds

    # Context
    vehicle_coverage: str
    coverage_warning: Optional[str]

    # Formatted content
    formatted_summary: str
    formatted_details: str
    formatted_recommendations: List[str]

    # Audit
    display_constraints: Dict[str, Any]


# =============================================================================
# PREDICTION DISPLAY ENFORCER
# =============================================================================

class PredictionDisplayEnforcer:
    """
    Enforces safe display of predictions.

    This class ensures that:
    1. All predictions include required safety elements
    2. Confidence is not displayed in a misleading way
    3. Critical predictions have appropriate warnings
    4. Users cannot bypass safety information
    """

    def __init__(self):
        """Initialize the enforcer."""
        self.disclaimer_manager = get_disclaimer_manager()
        self.coverage_tracker = get_coverage_tracker()

        self.requirements = DISPLAY_REQUIREMENTS

        logger.info("Prediction Display Enforcer initialized")

    def prepare_for_display(
        self,
        prediction: Dict[str, Any],
        vehicle_info: Optional[Dict[str, str]] = None,
        display_mode: DisplayMode = DisplayMode.FULL,
        user_id: Optional[str] = None
    ) -> SafePredictionDisplay:
        """
        Prepare a prediction for safe display.

        Args:
            prediction: Raw prediction data
            vehicle_info: Vehicle make/model/year info
            display_mode: How to display the prediction
            user_id: User ID for personalization

        Returns:
            SafePredictionDisplay ready for rendering
        """
        # Extract core prediction data
        failure_type = prediction.get('failure_type', 'unknown')
        failure_prob = prediction.get('failure_probability', 0)
        confidence = prediction.get('confidence', 0)
        days = prediction.get('days_to_failure')
        criticality = prediction.get('criticality', 'medium')

        # Get vehicle coverage
        coverage_level = CoverageLevel.UNKNOWN
        coverage_warning = None

        if vehicle_info:
            coverage_data = self.coverage_tracker.check_prediction_coverage(
                vehicle_info.get('make', ''),
                vehicle_info.get('model', ''),
                int(vehicle_info.get('year', 0))
            )
            coverage_level = CoverageLevel(coverage_data.get('coverage_level', 'unknown'))

            if coverage_data.get('must_display_warning'):
                coverage_warning = coverage_data.get('disclaimer', '')

            # Apply coverage confidence modifier
            confidence = confidence * coverage_data.get('confidence_modifier', 1.0)

        # Cap displayed confidence
        displayed_confidence = min(
            confidence,
            self.requirements['max_displayed_confidence']
        )

        # Determine confidence level string
        confidence_level = self._get_confidence_level_string(displayed_confidence)

        # Determine urgency
        urgency = self._determine_urgency(failure_prob, days, criticality)

        # Get warnings
        warnings = self._generate_warnings(
            prediction, coverage_level, displayed_confidence, urgency
        )

        # Get disclaimers
        disclaimers = self.disclaimer_manager.get_disclaimers_for_prediction(
            prediction,
            {'coverage_level': coverage_level.value, **vehicle_info} if vehicle_info else None
        )

        # Generate safety notes
        safety_notes = self._generate_safety_notes(prediction, criticality)

        # Determine acknowledgment requirements
        requires_ack = criticality == 'critical' or coverage_level == CoverageLevel.UNSUPPORTED
        blocks_action = requires_ack and criticality == 'critical'

        # Format content
        formatted_summary = self._format_summary(
            failure_type, failure_prob, displayed_confidence, days, urgency
        )
        formatted_details = self._format_details(prediction, display_mode)
        formatted_recommendations = self._format_recommendations(prediction, criticality)

        # Create display ID
        display_id = f"disp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{prediction.get('prediction_id', 'unknown')[:8]}"

        return SafePredictionDisplay(
            display_id=display_id,
            prediction_id=prediction.get('prediction_id', 'unknown'),
            timestamp=datetime.now().isoformat(),
            failure_type=failure_type,
            failure_probability=failure_prob,
            displayed_confidence=displayed_confidence,
            confidence_level=confidence_level,
            days_to_failure=days,
            urgency=urgency,
            warnings=warnings,
            disclaimers=disclaimers,
            safety_notes=safety_notes,
            requires_acknowledgment=requires_ack,
            blocks_until_acknowledged=blocks_action,
            minimum_display_time=self.requirements['min_warning_display_time'] if warnings else 0,
            vehicle_coverage=coverage_level.value,
            coverage_warning=coverage_warning,
            formatted_summary=formatted_summary,
            formatted_details=formatted_details,
            formatted_recommendations=formatted_recommendations,
            display_constraints={
                'confidence_capped': confidence > displayed_confidence,
                'original_confidence': confidence,
                'coverage_modifier_applied': vehicle_info is not None
            }
        )

    def _get_confidence_level_string(self, confidence: float) -> str:
        """Convert numeric confidence to level string."""
        if confidence >= 0.85:
            return "High"
        elif confidence >= 0.70:
            return "Moderate"
        elif confidence >= 0.50:
            return "Low"
        else:
            return "Very Low"

    def _determine_urgency(
        self,
        failure_prob: float,
        days: Optional[int],
        criticality: str
    ) -> str:
        """Determine urgency level."""
        if criticality == 'critical':
            if failure_prob > 0.8 or (days is not None and days < 7):
                return "IMMEDIATE"
            elif failure_prob > 0.5 or (days is not None and days < 14):
                return "URGENT"
            else:
                return "HIGH"
        elif criticality == 'high':
            if failure_prob > 0.7 or (days is not None and days < 14):
                return "HIGH"
            else:
                return "MODERATE"
        else:
            if failure_prob > 0.6:
                return "MODERATE"
            else:
                return "LOW"

    def _generate_warnings(
        self,
        prediction: Dict[str, Any],
        coverage: CoverageLevel,
        confidence: float,
        urgency: str
    ) -> List[DisplayElement]:
        """Generate warning elements for display."""
        warnings = []
        priority = 0

        # Critical urgency warning
        if urgency == "IMMEDIATE":
            priority += 1
            warnings.append(DisplayElement(
                element_type="urgency_warning",
                content="⚠️ IMMEDIATE ATTENTION REQUIRED - Have vehicle inspected TODAY",
                priority=priority,
                required=True,
                style="critical"
            ))

        # Coverage warning
        if coverage in [CoverageLevel.UNSUPPORTED, CoverageLevel.MINIMAL]:
            priority += 1
            warnings.append(DisplayElement(
                element_type="coverage_warning",
                content=f"⚠️ Limited data for your vehicle - predictions may be less accurate",
                priority=priority,
                required=True,
                style="warning"
            ))

        # Low confidence warning
        if confidence < 0.5:
            priority += 1
            warnings.append(DisplayElement(
                element_type="confidence_warning",
                content=f"⚠️ Low confidence prediction ({confidence:.0%}) - verify with professional",
                priority=priority,
                required=True,
                style="warning"
            ))

        # Professional advice (always included)
        priority += 1
        warnings.append(DisplayElement(
            element_type="professional_advice",
            content="ℹ️ This AI prediction should be verified by a qualified mechanic",
            priority=priority,
            required=True,
            style="info"
        ))

        return sorted(warnings, key=lambda w: w.priority)

    def _generate_safety_notes(
        self,
        prediction: Dict[str, Any],
        criticality: str
    ) -> List[str]:
        """Generate safety notes."""
        notes = []

        failure_type = prediction.get('failure_type', '')

        # Type-specific safety notes
        safety_notes_by_type = {
            'fuel_pump': [
                "Fuel pump failure can cause sudden loss of engine power",
                "If you notice engine sputtering at high speeds, seek immediate inspection",
            ],
            'coolant_system': [
                "Coolant system failure can cause engine overheating",
                "If temperature gauge rises, stop driving immediately",
                "Never open radiator cap when engine is hot",
            ],
            'transmission': [
                "Transmission issues can affect vehicle control",
                "Unusual sounds or shifting problems require immediate attention",
            ],
            'battery': [
                "Battery failure may leave you stranded",
                "Check for slow cranking as an early warning sign",
            ],
            'alternator': [
                "Alternator failure will drain the battery",
                "Dimming lights while driving indicate potential alternator issues",
            ],
            'thermostat': [
                "Thermostat failure can cause overheating or poor heating",
                "Monitor temperature gauge for unusual readings",
            ],
        }

        if failure_type in safety_notes_by_type:
            notes.extend(safety_notes_by_type[failure_type])

        # Add general notes for critical predictions
        if criticality == 'critical':
            notes.append("Do not ignore this warning - safety systems require immediate attention")
            notes.append("Have vehicle towed if you notice any symptoms while driving")

        return notes

    def _format_summary(
        self,
        failure_type: str,
        probability: float,
        confidence: float,
        days: Optional[int],
        urgency: str
    ) -> str:
        """Format prediction summary."""
        type_display = failure_type.replace('_', ' ').title()

        if days and days > 0:
            timeframe = f"in approximately {days} days"
        else:
            timeframe = "timeline uncertain"

        return (
            f"{type_display} Issue Detected\n"
            f"Probability: {probability:.0%} | Confidence: {confidence:.0%}\n"
            f"Estimated timeframe: {timeframe}\n"
            f"Urgency: {urgency}"
        )

    def _format_details(
        self,
        prediction: Dict[str, Any],
        display_mode: DisplayMode
    ) -> str:
        """Format prediction details."""
        if display_mode == DisplayMode.MINIMAL:
            return ""

        details = []

        if 'contributing_factors' in prediction:
            details.append("Contributing Factors:")
            for factor, value in prediction['contributing_factors'].items():
                details.append(f"  - {factor}: {value}")

        if 'symptoms' in prediction:
            details.append("\nPossible Symptoms to Watch:")
            for symptom in prediction['symptoms']:
                details.append(f"  • {symptom}")

        if display_mode == DisplayMode.FULL and 'technical_details' in prediction:
            details.append("\nTechnical Details:")
            details.append(prediction['technical_details'])

        return "\n".join(details)

    def _format_recommendations(
        self,
        prediction: Dict[str, Any],
        criticality: str
    ) -> List[str]:
        """Format recommendations."""
        recommendations = []

        # Base recommendations by criticality
        if criticality == 'critical':
            recommendations.extend([
                "Schedule professional inspection within 24-48 hours",
                "Avoid long trips or highway driving until inspected",
                "Keep emergency roadside assistance number handy",
            ])
        elif criticality == 'high':
            recommendations.extend([
                "Schedule professional inspection within 1 week",
                "Monitor for any changes or symptoms",
            ])
        else:
            recommendations.extend([
                "Include in next scheduled maintenance visit",
                "Monitor for any changes",
            ])

        # Always include
        recommendations.append("Keep this prediction as reference for your mechanic")

        return recommendations

    def render_for_gui(
        self,
        display: SafePredictionDisplay,
        format_type: str = 'html'
    ) -> str:
        """
        Render display for GUI.

        Args:
            display: Safe prediction display
            format_type: 'html' or 'text'

        Returns:
            Formatted string for display
        """
        if format_type == 'html':
            return self._render_html(display)
        else:
            return self._render_text(display)

    def _render_html(self, display: SafePredictionDisplay) -> str:
        """Render as HTML."""
        warnings_html = ""
        for warning in display.warnings:
            warnings_html += f'<div class="warning {warning.style}">{warning.content}</div>\n'

        notes_html = ""
        for note in display.safety_notes:
            notes_html += f'<li>{note}</li>\n'

        recommendations_html = ""
        for rec in display.formatted_recommendations:
            recommendations_html += f'<li>{rec}</li>\n'

        return f"""
<div class="prediction-display" data-requires-ack="{display.requires_acknowledgment}">
    <div class="prediction-header {display.urgency.lower()}">
        <h2>{display.failure_type.replace('_', ' ').title()} Prediction</h2>
        <span class="urgency-badge">{display.urgency}</span>
    </div>

    <div class="warnings-section">
        {warnings_html}
    </div>

    <div class="prediction-summary">
        <pre>{display.formatted_summary}</pre>
    </div>

    <div class="prediction-details">
        {display.formatted_details}
    </div>

    <div class="safety-notes">
        <h3>Safety Notes</h3>
        <ul>{notes_html}</ul>
    </div>

    <div class="recommendations">
        <h3>Recommended Actions</h3>
        <ul>{recommendations_html}</ul>
    </div>

    <div class="disclaimer-footer">
        <p>This AI prediction is advisory only. Always verify with a qualified professional.</p>
        {'<button class="acknowledge-btn">I Understand</button>' if display.requires_acknowledgment else ''}
    </div>
</div>
"""

    def _render_text(self, display: SafePredictionDisplay) -> str:
        """Render as plain text."""
        lines = ["=" * 60]
        lines.append(f"PREDICTION: {display.failure_type.replace('_', ' ').upper()}")
        lines.append(f"Urgency: {display.urgency}")
        lines.append("=" * 60)

        lines.append("")
        for warning in display.warnings:
            lines.append(warning.content)

        lines.append("")
        lines.append(display.formatted_summary)

        if display.formatted_details:
            lines.append("")
            lines.append(display.formatted_details)

        lines.append("")
        lines.append("Safety Notes:")
        for note in display.safety_notes:
            lines.append(f"  • {note}")

        lines.append("")
        lines.append("Recommendations:")
        for rec in display.formatted_recommendations:
            lines.append(f"  → {rec}")

        lines.append("")
        lines.append("-" * 60)
        lines.append("DISCLAIMER: This AI prediction is advisory only.")
        lines.append("Always verify with a qualified automotive professional.")
        lines.append("-" * 60)

        return "\n".join(lines)

    def validate_display_compliance(
        self,
        display: SafePredictionDisplay
    ) -> Tuple[bool, List[str]]:
        """
        Validate that a display meets all safety requirements.

        Args:
            display: Display to validate

        Returns:
            Tuple of (is_compliant, violations)
        """
        violations = []

        # Check required elements
        has_warnings = len(display.warnings) > 0
        has_disclaimers = len(display.disclaimers) > 0

        if not has_warnings:
            violations.append("Missing warning elements")

        if not has_disclaimers:
            violations.append("Missing disclaimers")

        # Check professional advice is included
        has_professional_advice = any(
            w.element_type == 'professional_advice'
            for w in display.warnings
        )
        if not has_professional_advice:
            violations.append("Missing professional advice note")

        # Check confidence display
        if display.displayed_confidence > self.requirements['max_displayed_confidence']:
            violations.append(f"Confidence exceeds maximum display value")

        # Check acknowledgment for critical
        if display.urgency == 'IMMEDIATE' and not display.requires_acknowledgment:
            violations.append("Critical prediction must require acknowledgment")

        is_compliant = len(violations) == 0

        if not is_compliant:
            logger.warning(f"Display compliance violations: {violations}")

        return is_compliant, violations


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_enforcer_instance: Optional[PredictionDisplayEnforcer] = None


def get_display_enforcer() -> PredictionDisplayEnforcer:
    """Get or create singleton enforcer instance."""
    global _enforcer_instance
    if _enforcer_instance is None:
        _enforcer_instance = PredictionDisplayEnforcer()
    return _enforcer_instance


def prepare_prediction_for_display(
    prediction: Dict[str, Any],
    vehicle_info: Optional[Dict[str, str]] = None,
    display_mode: DisplayMode = DisplayMode.FULL
) -> SafePredictionDisplay:
    """Convenience function to prepare a prediction for display."""
    enforcer = get_display_enforcer()
    return enforcer.prepare_for_display(prediction, vehicle_info, display_mode)


def render_prediction(
    display: SafePredictionDisplay,
    format_type: str = 'text'
) -> str:
    """Convenience function to render a prediction."""
    enforcer = get_display_enforcer()
    return enforcer.render_for_gui(display, format_type)
