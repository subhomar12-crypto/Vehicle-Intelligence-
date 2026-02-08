"""
Request validation middleware.
Preserves exact OBD_RANGES from original validation_middleware.py.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import Request

from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)


# OBD parameter validation ranges - preserved exactly from original server
OBD_RANGES: Dict[str, Dict[str, Any]] = {
    "RPM": {"min": 0, "max": 16383, "unit": "rpm"},
    "SPEED": {"min": 0, "max": 255, "unit": "km/h"},
    "ENGINE_COOLANT_TEMP": {"min": -40, "max": 215, "unit": "°C"},
    "INTAKE_AIR_TEMP": {"min": -40, "max": 215, "unit": "°C"},
    "MAF": {"min": 0, "max": 655.35, "unit": "g/s"},
    "THROTTLE_POS": {"min": 0, "max": 100, "unit": "%"},
    "ENGINE_LOAD": {"min": 0, "max": 100, "unit": "%"},
    "FUEL_LEVEL": {"min": 0, "max": 100, "unit": "%"},
    "BATTERY_VOLTAGE": {"min": 6.0, "max": 18.0, "unit": "V"},
    "OIL_TEMP": {"min": -40, "max": 210, "unit": "°C"},
    "OIL_PRESSURE": {"min": 0, "max": 1000, "unit": "kPa"},
    "BAROMETRIC_PRESSURE": {"min": 0, "max": 255, "unit": "kPa"},
    "TIMING_ADVANCE": {"min": -64, "max": 63.5, "unit": "°"},
}


def validate_obd_value(pid: str, value: float) -> tuple[bool, Optional[str]]:
    """
    Validate an OBD value against known ranges.
    
    Returns:
        (is_valid, error_message)
    """
    pid_upper = pid.upper()
    if pid_upper not in OBD_RANGES:
        # Unknown PID - allow it with a warning
        logger.debug(f"Unknown OBD PID: {pid}, skipping validation")
        return True, None
    
    ranges = OBD_RANGES[pid_upper]
    min_val = ranges["min"]
    max_val = ranges["max"]
    unit = ranges.get("unit", "")
    
    if value < min_val or value > max_val:
        return False, f"Value {value} {unit} is outside valid range [{min_val}, {max_val}]"
    
    return True, None


def validate_obd_payload(payload: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate a complete OBD data payload.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Required fields check
    if "profile_id" not in payload and "vin" not in payload:
        errors.append("Either 'profile_id' or 'vin' is required")
    
    if "data" not in payload and "readings" not in payload:
        errors.append("OBD data is required (use 'data' or 'readings' field)")
    
    # Validate individual readings
    readings = payload.get("data", payload.get("readings", {}))
    for pid, value in readings.items():
        if isinstance(value, (int, float)):
            is_valid, error = validate_obd_value(pid, float(value))
            if not is_valid:
                errors.append(f"PID {pid}: {error}")
    
    return len(errors) == 0, errors


async def validate_json_size(request: Request, max_size_bytes: int = 10 * 1024 * 1024) -> None:
    """Validate that JSON body doesn't exceed max size."""
    content_length = request.headers.get("content-length")
    if content_length:
        size = int(content_length)
        if size > max_size_bytes:
            raise APIError(
                status_code=413,
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Request body too large (max {max_size_bytes // 1024 // 1024}MB)",
            )


def validate_timestamp(timestamp: Any) -> datetime:
    """Validate and parse a timestamp value."""
    if isinstance(timestamp, datetime):
        return timestamp
    
    if isinstance(timestamp, str):
        # Try ISO format
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            pass
        
        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(timestamp, fmt)
            except ValueError:
                continue
    
    if isinstance(timestamp, (int, float)):
        # Unix timestamp
        return datetime.utcfromtimestamp(timestamp)
    
    raise ValueError(f"Cannot parse timestamp: {timestamp}")


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Sanitize a string input."""
    if not isinstance(value, str):
        return str(value)[:max_length]
    return value.strip()[:max_length]


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_vin(vin: str) -> tuple[bool, Optional[str]]:
    """Validate VIN format."""
    if not vin:
        return False, "VIN cannot be empty"
    
    vin = vin.upper().strip()
    
    if len(vin) != 17:
        return False, f"VIN must be 17 characters (got {len(vin)})"
    
    # Check for invalid characters (I, O, Q not allowed)
    invalid_chars = set('IOQ')
    if any(c in invalid_chars for c in vin):
        return False, "VIN contains invalid characters (I, O, Q not allowed)"
    
    # Basic alphanumeric check
    if not vin.isalnum():
        return False, "VIN must contain only letters and numbers"
    
    return True, None


def validate_phone(phone: str) -> tuple[bool, Optional[str]]:
    """Basic phone number validation."""
    if not phone:
        return False, "Phone number cannot be empty"
    
    # Remove common separators
    cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace("+", "")
    
    if not cleaned.isdigit():
        return False, "Phone number must contain only digits"
    
    if len(cleaned) < 8 or len(cleaned) > 15:
        return False, "Phone number must be between 8 and 15 digits"
    
    return True, None
