"""
Standardized API error response system.
Preserves exact ErrorCode values from original server for Android compatibility.
"""

import logging
import traceback
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ErrorCode:
    """Standardized error codes. Preserved exactly from original server."""

    # Authentication (401)
    AUTH_MISSING_HEADER = "AUTH_MISSING_HEADER"
    AUTH_INVALID_FORMAT = "AUTH_INVALID_FORMAT"
    AUTH_EMPTY_KEY = "AUTH_EMPTY_KEY"
    AUTH_INVALID_KEY = "AUTH_INVALID_KEY"
    AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_INSUFFICIENT_PERMISSIONS"

    # Subscription (402/403)
    SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED"
    SUBSCRIPTION_LIMIT_EXCEEDED = "SUBSCRIPTION_LIMIT_EXCEEDED"
    SUBSCRIPTION_INVALID = "SUBSCRIPTION_INVALID"
    FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"

    # Validation (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_JSON = "INVALID_JSON"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"
    INVALID_PARAMETER = "INVALID_PARAMETER"

    # Resource (404)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    PROFILE_NOT_FOUND = "PROFILE_NOT_FOUND"
    VEHICLE_NOT_FOUND = "VEHICLE_NOT_FOUND"
    DATA_NOT_FOUND = "DATA_NOT_FOUND"

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    AI_MODEL_ERROR = "AI_MODEL_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"

    # Service availability (503)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str
    request_id: Optional[str] = None
    path: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail


class APIError(HTTPException):
    """Custom exception with standardized error format."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.error_message = message
        self.details = details
        super().__init__(status_code=status_code, detail=message)


def _build_error_response(
    status_code: int,
    code: str,
    message: str,
    request: Optional[Request] = None,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Build standardized error JSON response."""
    request_id = getattr(request.state, "request_id", None) if request else None
    path = str(request.url.path) if request else None

    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=request_id,
            path=path,
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions."""
    return _build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.error_message,
        request=request,
        details=exc.details,
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle generic HTTPException."""
    return _build_error_response(
        status_code=exc.status_code,
        code=ErrorCode.INTERNAL_ERROR,
        message=str(exc.detail),
        request=request,
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        })
    return _build_error_response(
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed",
        request=request,
        details={"errors": errors},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions. Logs traceback, returns 500."""
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}",
        extra={"request_id": request_id},
        exc_info=True,
    )
    return _build_error_response(
        status_code=500,
        code=ErrorCode.INTERNAL_ERROR,
        message="An internal error occurred",
        request=request,
    )


def setup_error_handlers(app) -> None:
    """Register all error handlers on a FastAPI app."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
