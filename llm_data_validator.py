"""
LLM Data Validator
Ensures all data referenced by the LLM is real, valid, and vehicle/driver-specific.

This module provides:
1. Pre-response validation - Check if LLM can answer with real data
2. Post-response validation - Verify LLM response contains only real data
3. Entity verification - Confirm vehicles, drivers, predictions exist
4. Anti-hallucination safeguards

Part of the PREDICT Vehicle Intelligence Platform.
"""

import re
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Set
from dataclasses import dataclass
from enum import Enum


class ValidationResult(Enum):
    """Result of data validation"""
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"  # Some data valid, some not
    UNKNOWN = "unknown"  # Cannot determine validity


class ValidationErrorType(Enum):
    """Types of validation errors"""
    ENTITY_NOT_FOUND = "entity_not_found"
    DATA_MISMATCH = "data_mismatch"
    STALE_DATA = "stale_data"
    FABRICATED_DATA = "fabricated_data"
    MISSING_CONTEXT = "missing_context"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


@dataclass
class ValidationError:
    """A single validation error"""
    error_type: ValidationErrorType
    entity_type: str
    entity_id: str
    field: Optional[str]
    expected_value: Optional[Any]
    actual_value: Optional[Any]
    message: str


@dataclass
class ValidationReport:
    """Complete validation report"""
    result: ValidationResult
    errors: List[ValidationError]
    warnings: List[str]
    validated_entities: Dict[str, bool]
    confidence_score: float  # 0-1, how confident we are in the validation
    timestamp: datetime


class LLMDataValidator:
    """
    Validates data to prevent LLM hallucinations.

    Key responsibilities:
    1. Verify entities exist before LLM references them
    2. Check that numerical values match real data
    3. Ensure vehicle-specific data is actually for that vehicle
    4. Flag any potentially fabricated information
    """

    # Patterns that might indicate hallucinated data
    SUSPICIOUS_PATTERNS = [
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',  # Dates that might be made up
        r'\b\d+%\b',  # Percentages
        r'\bVIN[:\s]*[A-HJ-NPR-Z0-9]{17}\b',  # VIN numbers
        r'\b[A-Z]{1,2}\d{4,5}\b',  # License plates
        r'\bP\d{4}\b',  # DTC codes
    ]

    def __init__(self, db_path: str = None):
        if db_path is None:
            app_data = os.path.join(os.path.expanduser("~"), ".predict")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "llm_validation.db")

        self.db_path = db_path
        self._known_entities_cache: Dict[str, Set[str]] = {}
        self._init_database()

    def _init_database(self):
        """Initialize validation database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Log of validation attempts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS validation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    validation_type TEXT NOT NULL,
                    result TEXT NOT NULL,
                    errors_count INTEGER DEFAULT 0,
                    warnings_count INTEGER DEFAULT 0,
                    confidence_score REAL,
                    context TEXT,
                    validated_at TEXT NOT NULL
                )
            """)

            # Cache of known valid entities
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS known_entities (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_name TEXT,
                    last_verified TEXT NOT NULL,
                    PRIMARY KEY (entity_type, entity_id)
                )
            """)

            conn.commit()

    def validate_pre_response(
        self,
        query: str,
        available_context: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate before generating a response.

        Checks if we have enough real data to answer the query.

        Returns:
            (can_respond, warnings): Whether we can respond and any warnings
        """
        warnings = []
        can_respond = True

        # Check if query references specific entities
        entity_refs = self._extract_entity_references(query)

        for entity_type, entity_id in entity_refs:
            if not self._verify_entity_exists(entity_type, entity_id, available_context):
                warnings.append(f"Referenced {entity_type} '{entity_id}' not found in context")
                can_respond = False

        # Check if we have minimal required context
        if not available_context.get("entities") and not available_context.get("notifications"):
            warnings.append("No entity or notification data available")

        # Check for stale data
        if available_context.get("ai_status", {}).get("last_training"):
            try:
                last_training = datetime.fromisoformat(
                    available_context["ai_status"]["last_training"]
                )
                if datetime.now() - last_training > timedelta(days=30):
                    warnings.append("AI model data is over 30 days old - predictions may be outdated")
            except:
                pass

        return can_respond, warnings

    def validate_response(
        self,
        response: str,
        context: Dict[str, Any],
        strict_mode: bool = True
    ) -> ValidationReport:
        """
        Validate an LLM response for hallucinations.

        Args:
            response: The LLM's generated response
            context: The context that was provided to the LLM
            strict_mode: If True, flag any unverifiable data

        Returns:
            ValidationReport with detailed results
        """
        errors = []
        warnings = []
        validated_entities = {}
        confidence = 1.0

        # Extract data points from response
        extracted_data = self._extract_data_points(response)

        # Validate each extracted data point
        for data_type, data_values in extracted_data.items():
            for value in data_values:
                is_valid, error = self._validate_data_point(
                    data_type, value, context, strict_mode
                )
                if not is_valid and error:
                    errors.append(error)
                    confidence -= 0.1
                validated_entities[f"{data_type}:{value}"] = is_valid

        # Check for suspicious patterns
        suspicious = self._check_suspicious_patterns(response, context)
        for pattern_type, matches in suspicious.items():
            for match in matches:
                if not self._verify_in_context(match, context):
                    warnings.append(f"Unverified {pattern_type}: {match}")
                    confidence -= 0.05

        # Determine overall result
        if errors:
            result = ValidationResult.INVALID if len(errors) > 2 else ValidationResult.PARTIAL
        elif warnings:
            result = ValidationResult.PARTIAL
        else:
            result = ValidationResult.VALID

        confidence = max(0.0, min(1.0, confidence))

        report = ValidationReport(
            result=result,
            errors=errors,
            warnings=warnings,
            validated_entities=validated_entities,
            confidence_score=confidence,
            timestamp=datetime.now()
        )

        # Log validation
        self._log_validation(report)

        return report

    def validate_vehicle_data(
        self,
        vehicle_id: str,
        claimed_data: Dict[str, Any]
    ) -> ValidationReport:
        """
        Validate that claimed vehicle data matches actual records.

        Use this when the LLM makes specific claims about a vehicle.
        """
        errors = []
        warnings = []

        try:
            from profiles_manager import get_profiles_manager
            pm = get_profiles_manager()

            actual_vehicle = pm.get_vehicle_by_id(vehicle_id)

            if not actual_vehicle:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.ENTITY_NOT_FOUND,
                    entity_type="vehicle",
                    entity_id=vehicle_id,
                    field=None,
                    expected_value=None,
                    actual_value=None,
                    message=f"Vehicle {vehicle_id} not found in database"
                ))
            else:
                # Validate each claimed field
                for field, claimed_value in claimed_data.items():
                    actual_value = actual_vehicle.get(field)

                    if actual_value is None:
                        warnings.append(f"Field '{field}' not found in vehicle record")
                        continue

                    if not self._values_match(claimed_value, actual_value):
                        errors.append(ValidationError(
                            error_type=ValidationErrorType.DATA_MISMATCH,
                            entity_type="vehicle",
                            entity_id=vehicle_id,
                            field=field,
                            expected_value=actual_value,
                            actual_value=claimed_value,
                            message=f"Vehicle {field}: claimed '{claimed_value}' but actual is '{actual_value}'"
                        ))

        except ImportError:
            warnings.append("Profile manager not available for validation")

        result = ValidationResult.VALID if not errors else ValidationResult.INVALID
        confidence = 1.0 - (len(errors) * 0.2)

        return ValidationReport(
            result=result,
            errors=errors,
            warnings=warnings,
            validated_entities={"vehicle": not errors},
            confidence_score=max(0.0, confidence),
            timestamp=datetime.now()
        )

    def validate_driver_data(
        self,
        driver_id: str,
        claimed_data: Dict[str, Any]
    ) -> ValidationReport:
        """
        Validate that claimed driver data matches actual records.
        """
        errors = []
        warnings = []

        try:
            from profiles_manager import get_profiles_manager
            pm = get_profiles_manager()

            actual_driver = pm.get_driver_by_id(driver_id)

            if not actual_driver:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.ENTITY_NOT_FOUND,
                    entity_type="driver",
                    entity_id=driver_id,
                    field=None,
                    expected_value=None,
                    actual_value=None,
                    message=f"Driver {driver_id} not found in database"
                ))
            else:
                for field, claimed_value in claimed_data.items():
                    actual_value = actual_driver.get(field)

                    if actual_value is None:
                        continue

                    if not self._values_match(claimed_value, actual_value):
                        errors.append(ValidationError(
                            error_type=ValidationErrorType.DATA_MISMATCH,
                            entity_type="driver",
                            entity_id=driver_id,
                            field=field,
                            expected_value=actual_value,
                            actual_value=claimed_value,
                            message=f"Driver {field}: claimed '{claimed_value}' but actual is '{actual_value}'"
                        ))

        except ImportError:
            warnings.append("Profile manager not available for validation")

        result = ValidationResult.VALID if not errors else ValidationResult.INVALID
        confidence = 1.0 - (len(errors) * 0.2)

        return ValidationReport(
            result=result,
            errors=errors,
            warnings=warnings,
            validated_entities={"driver": not errors},
            confidence_score=max(0.0, confidence),
            timestamp=datetime.now()
        )

    def validate_prediction_reference(
        self,
        prediction_id: str,
        claimed_values: Dict[str, Any]
    ) -> ValidationReport:
        """
        Validate that a referenced prediction exists and data matches.
        """
        errors = []
        warnings = []

        try:
            from ai_prediction_engine import get_prediction_engine
            engine = get_prediction_engine()

            actual_prediction = engine.get_prediction_by_id(prediction_id)

            if not actual_prediction:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.ENTITY_NOT_FOUND,
                    entity_type="prediction",
                    entity_id=prediction_id,
                    field=None,
                    expected_value=None,
                    actual_value=None,
                    message=f"Prediction {prediction_id} not found"
                ))
            else:
                # Validate risk level if claimed
                if "risk_level" in claimed_values:
                    actual_risk = actual_prediction.get("risk_level", 0)
                    claimed_risk = claimed_values["risk_level"]

                    # Allow 5% tolerance for risk values
                    if abs(actual_risk - claimed_risk) > 0.05:
                        errors.append(ValidationError(
                            error_type=ValidationErrorType.DATA_MISMATCH,
                            entity_type="prediction",
                            entity_id=prediction_id,
                            field="risk_level",
                            expected_value=actual_risk,
                            actual_value=claimed_risk,
                            message=f"Risk level mismatch: {claimed_risk:.0%} vs actual {actual_risk:.0%}"
                        ))

        except ImportError:
            warnings.append("Prediction engine not available for validation")

        result = ValidationResult.VALID if not errors else ValidationResult.INVALID

        return ValidationReport(
            result=result,
            errors=errors,
            warnings=warnings,
            validated_entities={"prediction": not errors},
            confidence_score=1.0 if not errors else 0.5,
            timestamp=datetime.now()
        )

    def _extract_entity_references(self, text: str) -> List[Tuple[str, str]]:
        """Extract entity references from text"""
        references = []

        # Look for vehicle references
        vehicle_patterns = [
            r'vehicle[:\s]+([A-Za-z0-9_-]+)',
            r'vehicle_id[:\s]+([A-Za-z0-9_-]+)',
            r'VIN[:\s]+([A-HJ-NPR-Z0-9]{17})',
        ]

        for pattern in vehicle_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                references.append(("vehicle", match))

        # Look for driver references
        driver_patterns = [
            r'driver[:\s]+([A-Za-z0-9_-]+)',
            r'driver_id[:\s]+([A-Za-z0-9_-]+)',
        ]

        for pattern in driver_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                references.append(("driver", match))

        return references

    def _extract_data_points(self, text: str) -> Dict[str, List[str]]:
        """Extract specific data points from text for validation"""
        data_points = {
            "percentages": [],
            "dates": [],
            "dtc_codes": [],
            "mileage": [],
            "vin": [],
        }

        # Extract percentages
        percentages = re.findall(r'(\d{1,3})%', text)
        data_points["percentages"] = percentages

        # Extract dates
        dates = re.findall(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', text)
        data_points["dates"] = dates

        # Extract DTC codes
        dtc_codes = re.findall(r'\b(P\d{4})\b', text)
        data_points["dtc_codes"] = dtc_codes

        # Extract mileage
        mileage = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*(?:km|miles|mi)', text, re.IGNORECASE)
        data_points["mileage"] = mileage

        # Extract VINs
        vins = re.findall(r'\b([A-HJ-NPR-Z0-9]{17})\b', text)
        data_points["vin"] = vins

        return data_points

    def _validate_data_point(
        self,
        data_type: str,
        value: str,
        context: Dict[str, Any],
        strict_mode: bool
    ) -> Tuple[bool, Optional[ValidationError]]:
        """Validate a single extracted data point"""

        # Check if value exists in context
        if self._verify_in_context(value, context):
            return True, None

        # In strict mode, unverified data is invalid
        if strict_mode:
            return False, ValidationError(
                error_type=ValidationErrorType.FABRICATED_DATA,
                entity_type=data_type,
                entity_id=value,
                field=None,
                expected_value=None,
                actual_value=value,
                message=f"Unverified {data_type} value: {value}"
            )

        return True, None

    def _check_suspicious_patterns(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Check for suspicious patterns that might indicate hallucination"""
        suspicious = {}

        for i, pattern in enumerate(self.SUSPICIOUS_PATTERNS):
            matches = re.findall(pattern, text)
            if matches:
                pattern_type = f"pattern_{i}"
                suspicious[pattern_type] = matches

        return suspicious

    def _verify_in_context(self, value: str, context: Dict[str, Any]) -> bool:
        """Check if a value exists anywhere in the provided context"""
        context_str = json.dumps(context, default=str)
        return value in context_str

    def _verify_entity_exists(
        self,
        entity_type: str,
        entity_id: str,
        context: Dict[str, Any]
    ) -> bool:
        """Verify an entity exists in the database or context"""

        # Check context first
        entities = context.get("entities", {})
        if entity_type in entities:
            entity_data = entities[entity_type]
            if isinstance(entity_data, dict) and entity_data.get(f"{entity_type}_id") == entity_id:
                return True

        # Check database
        try:
            if entity_type == "vehicle":
                from profiles_manager import get_profiles_manager
                pm = get_profiles_manager()
                return pm.get_vehicle_by_id(entity_id) is not None

            elif entity_type == "driver":
                from profiles_manager import get_profiles_manager
                pm = get_profiles_manager()
                return pm.get_driver_by_id(entity_id) is not None

        except ImportError:
            pass

        return False

    def _values_match(self, claimed: Any, actual: Any) -> bool:
        """Check if two values match (with tolerance for numbers)"""
        if claimed == actual:
            return True

        # Try numeric comparison with tolerance
        try:
            claimed_num = float(str(claimed).replace(",", "").replace("%", ""))
            actual_num = float(str(actual).replace(",", "").replace("%", ""))

            # 5% tolerance
            tolerance = max(abs(actual_num) * 0.05, 1)
            return abs(claimed_num - actual_num) <= tolerance
        except (ValueError, TypeError):
            pass

        # String comparison (case insensitive)
        if str(claimed).lower() == str(actual).lower():
            return True

        return False

    def _log_validation(self, report: ValidationReport):
        """Log validation result"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO validation_log
                    (validation_type, result, errors_count, warnings_count, confidence_score, validated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    "response_validation",
                    report.result.value,
                    len(report.errors),
                    len(report.warnings),
                    report.confidence_score,
                    report.timestamp.isoformat()
                ))
                conn.commit()
        except Exception:
            pass

    def get_validation_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get validation statistics"""
        since = datetime.now() - timedelta(days=days)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN result = 'valid' THEN 1 ELSE 0 END) as valid_count,
                        SUM(CASE WHEN result = 'invalid' THEN 1 ELSE 0 END) as invalid_count,
                        AVG(confidence_score) as avg_confidence,
                        AVG(errors_count) as avg_errors
                    FROM validation_log
                    WHERE validated_at >= ?
                """, (since.isoformat(),))

                row = cursor.fetchone()

                return {
                    "period_days": days,
                    "total_validations": row[0] or 0,
                    "valid_count": row[1] or 0,
                    "invalid_count": row[2] or 0,
                    "avg_confidence": row[3] or 0,
                    "avg_errors": row[4] or 0,
                    "validity_rate": (row[1] or 0) / max(1, row[0] or 1)
                }

        except Exception as e:
            return {"error": str(e)}


# Singleton instance
_validator: Optional[LLMDataValidator] = None


def get_data_validator() -> LLMDataValidator:
    """Get the singleton LLMDataValidator instance"""
    global _validator
    if _validator is None:
        _validator = LLMDataValidator()
    return _validator


def validate_llm_response(
    response: str,
    context: Dict[str, Any],
    strict: bool = True
) -> ValidationReport:
    """
    Convenience function to validate an LLM response.

    Args:
        response: The LLM's response text
        context: The context that was provided to the LLM
        strict: If True, flag any unverifiable data

    Returns:
        ValidationReport with results
    """
    validator = get_data_validator()
    return validator.validate_response(response, context, strict)


def can_respond_to_query(
    query: str,
    context: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Check if we have enough real data to respond to a query.

    Returns:
        (can_respond, warnings)
    """
    validator = get_data_validator()
    return validator.validate_pre_response(query, context)
