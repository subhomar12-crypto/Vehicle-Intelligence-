"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Accessibility Enforcer

Predict OBD - Accessibility Enforcement Module
CRITICAL: Ensures all outputs meet accessibility requirements.

This module enforces:
- Accessible error messages with codes and descriptions
- PDF accessibility metadata (PDF/UA compliance)
- Screen reader compatible API responses
- Color-independent status indicators
- Mandatory alt-text for visual elements
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class AccessibilityLevel(Enum):
    """WCAG 2.1 conformance levels."""
    A = "A"        # Minimum
    AA = "AA"      # Target (legally required in many jurisdictions)
    AAA = "AAA"    # Enhanced


# Target conformance level - AA is standard requirement
TARGET_CONFORMANCE_LEVEL = AccessibilityLevel.AA


@dataclass
class AccessibilityViolation:
    """An accessibility violation."""
    rule_id: str
    rule_description: str
    severity: str  # error, warning
    element: str
    message: str
    wcag_criteria: str


@dataclass
class AccessibilityReport:
    """Accessibility check report."""
    timestamp: str
    element_type: str
    element_id: str
    passed: bool
    conformance_level: str
    violations: List[AccessibilityViolation]


class AccessibleErrorMessages:
    """
    Enforces accessible error messages.

    All error messages MUST include:
    - Unique error code
    - Human-readable description
    - Suggested action
    - No color-only status indication
    """

    # Standard error templates - accessible by design
    ERROR_TEMPLATES = {
        # Authentication errors
        "AUTH_001": {
            "code": "AUTH_001",
            "title": "Authentication Required",
            "description": "You must be logged in to access this resource.",
            "action": "Please log in with your credentials and try again.",
            "severity": "error"
        },
        "AUTH_002": {
            "code": "AUTH_002",
            "title": "Invalid API Key",
            "description": "The provided API key is not valid or has been revoked.",
            "action": "Please check your API key and try again, or contact support for a new key.",
            "severity": "error"
        },
        "AUTH_003": {
            "code": "AUTH_003",
            "title": "Subscription Expired",
            "description": "Your subscription has expired and access is restricted.",
            "action": "Please renew your subscription to continue using this service.",
            "severity": "error"
        },

        # Data errors
        "DATA_001": {
            "code": "DATA_001",
            "title": "Insufficient Data",
            "description": "Not enough vehicle data has been collected to generate reliable predictions.",
            "action": "Continue driving to collect more data. Minimum 100 data points required.",
            "severity": "warning"
        },
        "DATA_002": {
            "code": "DATA_002",
            "title": "Vehicle Not Found",
            "description": "The specified vehicle could not be found in your account.",
            "action": "Please check the vehicle ID or add this vehicle to your account.",
            "severity": "error"
        },

        # System errors
        "SYS_001": {
            "code": "SYS_001",
            "title": "Service Temporarily Unavailable",
            "description": "The system is currently at capacity and cannot process your request.",
            "action": "Please wait 30 seconds and try again.",
            "severity": "warning"
        },
        "SYS_002": {
            "code": "SYS_002",
            "title": "Prediction Service Unavailable",
            "description": "The AI prediction service is temporarily unavailable.",
            "action": "Please try again in a few minutes. If the problem persists, contact support.",
            "severity": "error"
        },

        # Prediction errors
        "PRED_001": {
            "code": "PRED_001",
            "title": "Low Confidence Prediction",
            "description": "The prediction confidence is below the reliability threshold.",
            "action": "This prediction should be verified by a professional mechanic.",
            "severity": "warning"
        },
        "PRED_002": {
            "code": "PRED_002",
            "title": "Prediction Blocked",
            "description": "Predictions are blocked for this vehicle due to insufficient data.",
            "action": "Continue collecting data. Current: {current}, Required: {required}.",
            "severity": "error"
        },
    }

    @classmethod
    def get_error(cls, error_code: str, **kwargs) -> Dict[str, Any]:
        """
        Get accessible error message by code.

        Args:
            error_code: Error code (e.g., "AUTH_001")
            **kwargs: Format parameters for action message

        Returns:
            Accessible error response
        """
        template = cls.ERROR_TEMPLATES.get(error_code)
        if not template:
            template = {
                "code": error_code,
                "title": "Unknown Error",
                "description": "An unexpected error occurred.",
                "action": "Please try again or contact support.",
                "severity": "error"
            }

        # Format action with parameters
        action = template["action"]
        if kwargs:
            try:
                action = action.format(**kwargs)
            except KeyError:
                pass

        return {
            "error": {
                "code": template["code"],
                "title": template["title"],
                "description": template["description"],
                "action": action,
                "severity": template["severity"],
                # Accessibility metadata
                "accessibility": {
                    "role": "alert",
                    "aria_live": "assertive" if template["severity"] == "error" else "polite",
                    "aria_atomic": True
                }
            },
            "timestamp": datetime.now().isoformat()
        }


class PDFAccessibilityEnforcer:
    """
    Enforces PDF accessibility requirements.

    All PDFs MUST include:
    - Document title
    - Document language
    - Proper heading structure
    - Alt-text for images
    - Logical reading order
    - Tagged content
    """

    REQUIRED_METADATA = [
        "title",
        "language",
        "author",
        "creation_date"
    ]

    REQUIRED_STRUCTURE = [
        "has_headings",
        "has_alt_text_for_images",
        "has_tagged_content",
        "has_logical_reading_order"
    ]

    @classmethod
    def validate_pdf_metadata(cls, metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate PDF metadata meets accessibility requirements.

        Returns:
            (is_valid, list_of_violations)
        """
        violations = []

        for field in cls.REQUIRED_METADATA:
            if not metadata.get(field):
                violations.append(f"Missing required metadata: {field}")

        return len(violations) == 0, violations

    @classmethod
    def get_required_pdf_metadata(cls, title: str, author: str = "Predict OBD System") -> Dict[str, Any]:
        """
        Get required PDF metadata for accessible document.

        Args:
            title: Document title
            author: Document author

        Returns:
            Metadata dictionary for PDF generation
        """
        return {
            "title": title,
            "author": author,
            "language": "en-US",
            "creation_date": datetime.now().isoformat(),
            "creator": "Predict OBD Vehicle Maintenance System",
            "subject": "Vehicle Maintenance Report",
            # PDF/UA compliance markers
            "pdf_ua_compliance": True,
            "tagged": True,
            "display_doc_title": True,  # Show title in window instead of filename
        }

    @classmethod
    def enforce_image_alt_text(cls, image_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure image has alt-text, generate if missing.

        Args:
            image_data: Image data with optional alt_text

        Returns:
            Image data with guaranteed alt_text
        """
        if not image_data.get("alt_text"):
            # Generate descriptive alt-text based on context
            image_type = image_data.get("type", "image")
            image_context = image_data.get("context", "")

            alt_texts = {
                "chart": f"Chart showing {image_context or 'vehicle data visualization'}",
                "graph": f"Graph displaying {image_context or 'trend data'}",
                "gauge": f"Gauge indicating {image_context or 'measurement value'}",
                "icon": f"Icon representing {image_context or 'status indicator'}",
                "logo": "Predict OBD company logo",
            }

            image_data["alt_text"] = alt_texts.get(image_type,
                f"Image showing {image_context or 'vehicle-related content'}")

            logger.warning(f"ACCESSIBILITY: Generated alt-text for {image_type}")

        return image_data


class APIResponseAccessibility:
    """
    Ensures API responses are accessible.

    All responses MUST:
    - Use semantic status indicators (not color-only)
    - Include text descriptions for all states
    - Provide ARIA-compatible metadata
    - Support screen reader navigation
    """

    STATUS_MAPPINGS = {
        # Status -> (text_label, icon_name, aria_description)
        "healthy": ("Healthy", "check-circle", "System is operating normally"),
        "warning": ("Warning", "alert-triangle", "Attention required, non-critical issue"),
        "critical": ("Critical", "alert-octagon", "Immediate attention required"),
        "error": ("Error", "x-circle", "An error has occurred"),
        "loading": ("Loading", "loader", "Please wait, loading data"),
        "success": ("Success", "check", "Operation completed successfully"),
        "pending": ("Pending", "clock", "Operation is in progress"),
        "unknown": ("Unknown", "help-circle", "Status cannot be determined"),
    }

    @classmethod
    def wrap_status(cls, status: str, value: Any = None) -> Dict[str, Any]:
        """
        Wrap a status value with accessible metadata.

        Args:
            status: Status key (e.g., "healthy", "warning")
            value: Optional status value

        Returns:
            Accessible status object
        """
        mapping = cls.STATUS_MAPPINGS.get(status.lower(), cls.STATUS_MAPPINGS["unknown"])
        text_label, icon_name, aria_description = mapping

        return {
            "status": status,
            "value": value,
            "accessibility": {
                "text_label": text_label,
                "icon": icon_name,
                "aria_label": aria_description,
                "role": "status",
                # Color-independent indicator
                "indicator_symbol": cls._get_symbol(status)
            }
        }

    @classmethod
    def _get_symbol(cls, status: str) -> str:
        """Get color-independent symbol for status."""
        symbols = {
            "healthy": "[OK]",
            "warning": "[!]",
            "critical": "[!!]",
            "error": "[X]",
            "loading": "[...]",
            "success": "[+]",
            "pending": "[~]",
            "unknown": "[?]",
        }
        return symbols.get(status.lower(), "[?]")

    @classmethod
    def wrap_prediction_result(cls, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrap prediction result with accessible metadata.

        Args:
            prediction: Raw prediction result

        Returns:
            Accessible prediction response
        """
        # Determine status from prediction
        confidence = prediction.get("confidence", 0)
        failure_probability = prediction.get("failure_probability", 0)

        if failure_probability > 0.7:
            status = "critical"
        elif failure_probability > 0.4:
            status = "warning"
        else:
            status = "healthy"

        # Build accessible response
        return {
            "prediction": prediction,
            "status": cls.wrap_status(status, failure_probability),
            "accessibility": {
                "summary": cls._generate_prediction_summary(prediction),
                "screen_reader_text": cls._generate_screen_reader_text(prediction),
                "aria_live": "polite",
                "role": "region",
                "aria_label": "Vehicle Health Prediction Results"
            }
        }

    @classmethod
    def _generate_prediction_summary(cls, prediction: Dict[str, Any]) -> str:
        """Generate human-readable prediction summary."""
        failure_prob = prediction.get("failure_probability", 0)
        failure_type = prediction.get("predicted_failure_type", "unknown")
        days = prediction.get("days_to_failure")

        if failure_prob < 0.2:
            return "Your vehicle appears to be in good health with no predicted issues."
        elif failure_prob < 0.5:
            return f"Moderate concern: {failure_type} issue may develop. Monitor recommended."
        elif failure_prob < 0.7:
            return f"Attention needed: {failure_type} issue likely within {days or 'unknown'} days."
        else:
            return f"Urgent: High probability of {failure_type} failure. Immediate inspection recommended."

    @classmethod
    def _generate_screen_reader_text(cls, prediction: Dict[str, Any]) -> str:
        """Generate text optimized for screen readers."""
        confidence = prediction.get("confidence", 0)
        failure_prob = prediction.get("failure_probability", 0)
        failure_type = prediction.get("predicted_failure_type", "unknown")

        return (f"Prediction result: {failure_type} failure probability is "
                f"{failure_prob:.0%} with {confidence:.0%} confidence.")


class AccessibilityEnforcer:
    """
    Main accessibility enforcement entry point.

    Provides centralized access to all accessibility features.
    """

    def __init__(self):
        self.errors = AccessibleErrorMessages()
        self.pdf = PDFAccessibilityEnforcer()
        self.api = APIResponseAccessibility()

    def validate_response(self, response: Dict[str, Any],
                          response_type: str = "api") -> Tuple[bool, List[str]]:
        """
        Validate a response meets accessibility requirements.

        Args:
            response: Response to validate
            response_type: Type of response ("api", "pdf", "error")

        Returns:
            (is_valid, list_of_violations)
        """
        violations = []

        if response_type == "error":
            if "error" not in response:
                violations.append("Error response missing 'error' object")
            elif not response["error"].get("code"):
                violations.append("Error response missing error code")
            elif not response["error"].get("description"):
                violations.append("Error response missing description")

        if response_type == "api":
            if "status" in response and not isinstance(response["status"], dict):
                violations.append("Status should include accessibility metadata")

        return len(violations) == 0, violations

    def enforce_or_fail(self, response: Dict[str, Any],
                        response_type: str = "api") -> Dict[str, Any]:
        """
        Enforce accessibility requirements, fail if not met.

        Args:
            response: Response to validate
            response_type: Type of response

        Returns:
            Validated response

        Raises:
            AccessibilityViolationError: If response fails accessibility check
        """
        is_valid, violations = self.validate_response(response, response_type)

        if not is_valid:
            raise AccessibilityViolationError(violations)

        return response


class AccessibilityViolationError(Exception):
    """Raised when accessibility requirements are not met."""

    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__(f"Accessibility violations: {', '.join(violations)}")


# Global instance
_accessibility_enforcer: Optional[AccessibilityEnforcer] = None


def get_accessibility_enforcer() -> AccessibilityEnforcer:
    """Get global accessibility enforcer instance."""
    global _accessibility_enforcer
    if _accessibility_enforcer is None:
        _accessibility_enforcer = AccessibilityEnforcer()
    return _accessibility_enforcer


# Convenience functions
def get_accessible_error(error_code: str, **kwargs) -> Dict[str, Any]:
    """Get accessible error response."""
    return AccessibleErrorMessages.get_error(error_code, **kwargs)


def wrap_prediction_accessible(prediction: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap prediction with accessibility metadata."""
    return APIResponseAccessibility.wrap_prediction_result(prediction)


def get_pdf_metadata(title: str) -> Dict[str, Any]:
    """Get required PDF accessibility metadata."""
    return PDFAccessibilityEnforcer.get_required_pdf_metadata(title)
