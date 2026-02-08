"""
Authentication endpoints.

Handles:
- User registration
- Email verification
- Login
- Password reset
- API key management
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.services.auth_service import AuthService
from predict.core.services.email_service import EmailService
from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter()
legacy_router = APIRouter()  # For legacy Android routes


# ========================
# Request/Response Models
# ========================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None
    phone: Optional[str] = None


class RegisterResponse(BaseModel):
    success: bool
    user_id: int
    message: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    success: bool
    api_key: str
    tier: str
    permissions: list


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(..., min_length=8)


class CreateApiKeyRequest(BaseModel):
    name: str
    tier: Optional[str] = "free"
    expires_days: Optional[int] = None


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    tier: str
    permissions: list
    created_at: str
    expires_at: Optional[str]
    last_used_at: Optional[str]


# ========================
# Registration
# ========================

@router.post("/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    auth_service = AuthService(db)
    email_service = EmailService()
    
    # Create user
    user = await auth_service.register_user(
        email=request.email,
        password=request.password,
        name=request.name,
        phone=request.phone,
    )
    
    # Create and send verification code
    code = await auth_service.create_verification_code(user.id, purpose='email')
    
    bg_tasks.add_task(
        email_service.send_verification_email,
        to_email=user.email,
        name=user.name,
        code=code,
    )
    
    return RegisterResponse(
        success=True,
        user_id=user.id,
        message="Registration successful. Please check your email for verification code.",
    )


@legacy_router.post("/register")  # Legacy route for Android
async def register_legacy(
    request: RegisterRequest,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Legacy registration endpoint for Android compatibility."""
    return await register(request, bg_tasks, db)


# ========================
# Email Verification
# ========================

@router.post("/verify-email")
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify email with code."""
    auth_service = AuthService(db)
    
    # Find user by email
    from sqlalchemy import select
    from predict.core.db.models.user import User
    
    result = await db.execute(
        select(User).where(User.email == request.email.lower().strip())
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid email or code",
        )
    
    # Verify code
    if await auth_service.verify_code(user.id, request.code, purpose='email'):
        return {"success": True, "message": "Email verified successfully"}
    else:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid or expired verification code",
        )


@legacy_router.post("/verify-email")
async def verify_email_legacy(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Legacy verify endpoint for Android compatibility."""
    return await verify_email(request, db)


# ========================
# Login
# ========================

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login and get API key."""
    auth_service = AuthService(db)
    
    # Authenticate
    user = await auth_service.authenticate_user(request.email, request.password)
    
    if not user:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid email or password",
        )
    
    if not user.is_verified:
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Email not verified. Please verify your email first.",
        )
    
    # Get or create API key
    from sqlalchemy import select
    from predict.core.db.models.user import ApiKey
    
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.is_active == True,
        )
    )
    api_key = result.scalars().first()
    
    if not api_key:
        # Create new key
        plain_key, api_key = await auth_service.create_api_key(
            user_id=user.id,
            name="Auto-generated",
            tier=user.tier,
        )
    else:
        # For existing keys, we can't return the plain key
        # Client should use their stored key
        plain_key = None
    
    return LoginResponse(
        success=True,
        api_key=plain_key or "use_existing_key",
        tier=user.tier,
        permissions=api_key.permissions if api_key else [],
    )


@legacy_router.post("/login")
async def login_legacy(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Legacy login endpoint for Android compatibility."""
    return await login(request, db)


# ========================
# Password Reset
# ========================

@router.post("/password-reset-request")
async def request_password_reset(
    request: PasswordResetRequest,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Request password reset code."""
    auth_service = AuthService(db)
    email_service = EmailService()
    
    code = await auth_service.initiate_password_reset(request.email)
    
    if code:
        # Find user name
        from sqlalchemy import select
        from predict.core.db.models.user import User
        
        result = await db.execute(
            select(User).where(User.email == request.email.lower().strip())
        )
        user = result.scalar_one()
        
        bg_tasks.add_task(
            email_service.send_password_reset_email,
            to_email=user.email,
            name=user.name,
            code=code,
        )
    
    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": "If an account exists, a reset code has been sent.",
    }


@router.post("/password-reset")
async def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password with code."""
    auth_service = AuthService(db)
    
    success = await auth_service.reset_password(
        email=request.email,
        code=request.code,
        new_password=request.new_password,
    )
    
    if success:
        return {"success": True, "message": "Password reset successful"}
    else:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid email or reset code",
        )


# ========================
# API Key Management
# ========================

@router.post("/api-keys")
async def create_api_key(
    request: CreateApiKeyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key."""
    auth_service = AuthService(db)
    
    plain_key, api_key = await auth_service.create_api_key(
        user_id=current_user['user_id'],
        name=request.name,
        tier=request.tier or current_user['tier'],
        expires_days=request.expires_days,
    )
    
    return {
        "success": True,
        "api_key": plain_key,  # Only returned once!
        "key_id": api_key.id,
        "message": "Store this key safely - it will not be shown again",
    }


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List API keys (without the actual key values)."""
    from sqlalchemy import select
    from predict.core.db.models.user import ApiKey
    
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == current_user['user_id'],
            ApiKey.is_active == True,
        )
    )
    keys = result.scalars().all()
    
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            tier=k.tier,
            permissions=k.permissions,
            created_at=k.created_at.isoformat() if k.created_at else None,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key."""
    auth_service = AuthService(db)
    
    if await auth_service.revoke_api_key(key_id, current_user['user_id']):
        return {"success": True, "message": "API key revoked"}
    else:
        raise APIError(
            status_code=404,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="API key not found",
        )
