"""
Global error handler middleware with float timestamps.
"""

import logging
import time
import traceback
import uuid
from typing import Any, Optional, Dict

from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# =============================================================================
# ERROR CODES - Standardized error code registry (from old error_responses.py)
# =============================================================================

class ErrorCode:
    """Standardized error codes for API responses."""

    # Authentication errors (401)
    AUTH_MISSING_HEADER = "AUTH_MISSING_HEADER"
    AUTH_INVALID_FORMAT = "AUTH_INVALID_FORMAT"
    AUTH_EMPTY_KEY = "AUTH_EMPTY_KEY"
    AUTH_INVALID_KEY = "AUTH_INVALID_KEY"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
    AUTH_USER_NOT_FOUND = "AUTH_USER_NOT_FOUND"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_INSUFFICIENT_PERMISSIONS"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # Subscription errors (402/403)
    SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED"
    SUBSCRIPTION_LIMIT_EXCEEDED = "SUBSCRIPTION_LIMIT_EXCEEDED"
    SUBSCRIPTION_INVALID = "SUBSCRIPTION_INVALID"
    FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"

    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_JSON = "INVALID_JSON"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"
    INVALID_PARAMETER = "INVALID_PARAMETER"

    # Resource errors (404)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    PROFILE_NOT_FOUND = "PROFILE_NOT_FOUND"
    VEHICLE_NOT_FOUND = "VEHICLE_NOT_FOUND"
    VEHICLE_NOT_LINKED = "VEHICLE_NOT_LINKED"
    VEHICLE_ALREADY_LINKED = "VEHICLE_ALREADY_LINKED"
    DATA_NOT_FOUND = "DATA_NOT_FOUND"

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    AI_MODEL_ERROR = "AI_MODEL_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"

    # Service availability (501/503)
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"


# =============================================================================
# API ERROR EXCEPTION
# =============================================================================

class APIError(HTTPException):
    """
    Custom exception class that creates standardized error responses.
    
    Usage:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="The provided API key is invalid",
            details={"key_prefix": "pk_..."}
        )
    """
    
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        self.code = code
        self.message = message
        self.details = details
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Create the standardized response body
        error_body = {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "timestamp": self.timestamp,
                "request_id": self.request_id
            }
        }
        
        if self.details:
            error_body["error"]["details"] = self.details
        
        super().__init__(status_code=status_code, detail=error_body)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail} - {request.method} {request.url.path}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": timestamp_iso,
            "timestamp_unix": time.time(),
            "path": str(request.url.path),
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors."""
    timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    logger.warning(
        f"Validation error: {exc.errors()} - {request.method} {request.url.path}"
    )
    
    # Sanitize errors — Pydantic ctx may contain non-serializable objects (ValueError)
    sanitized_errors = []
    for err in exc.errors():
        clean = {k: v for k, v in err.items() if k != "ctx"}
        if "ctx" in err:
            clean["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        sanitized_errors.append(clean)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "details": sanitized_errors,
            "timestamp": timestamp_iso,
            "timestamp_unix": time.time(),
            "path": str(request.url.path),
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    error_id = f"ERR-{int(time.time())}-{id(exc) % 10000:04d}"
    
    logger.error(
        f"Unhandled exception {error_id}: {exc}\n{traceback.format_exc()}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "error_id": error_id,
            "timestamp": timestamp_iso,
            "timestamp_unix": time.time(),
            "path": str(request.url.path),
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


def setup_error_handlers(app: Any) -> None:
    """Register all error handlers with the FastAPI app."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    logger.debug("Error handlers registered")
