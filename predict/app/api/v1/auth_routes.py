"""
PREDICT - Authentication Routes Extension
Copyright © 2026 PREDICT
All rights reserved.

New Authentication Endpoints:
- POST /api/auth/resend-code
- POST /api/auth/forgot-password
- POST /api/auth/reset-password
- GET /api/auth/check-email
- GET /api/validate/password
- POST /api/user/profile-picture
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from pydantic import BaseModel, EmailStr
from typing import Optional
import re
from datetime import datetime, timedelta
import secrets
import hashlib

router = APIRouter(prefix="/api", tags=["auth_extended"])

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ResendCodeRequest(BaseModel):
    email: EmailStr

class ResendCodeResponse(BaseModel):
    success: bool
    cooldown_seconds: int
    message: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ResetPasswordResponse(BaseModel):
    success: bool
    message: str

class CheckEmailResponse(BaseModel):
    exists: bool
    available: bool
    message: str

class PasswordStrengthResponse(BaseModel):
    strength: str  # "weak", "medium", "strong"
    requirements_met: list[str]
    score: int  # 0-5

class ProfilePictureResponse(BaseModel):
    success: bool
    url: str
    thumbnail_url: str
    dimensions: dict


# ============================================================================
# IN-MEMORY STORAGE (Replace with Redis/DB in production)
# ============================================================================

# Store for verification code cooldowns: {email: last_request_timestamp}
verification_cooldowns = {}

# Store for password reset tokens: {token: {email, expires}}
password_reset_tokens = {}

# Store for user data (mock - replace with actual DB)
users_db = {}

VERIFICATION_COOLDOWN_SECONDS = 45
RESET_TOKEN_EXPIRY_HOURS = 1


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_password_strength(password: str) -> tuple[int, list[str]]:
    """
    Calculate password strength score (0-5) and list of met requirements.
    Returns: (score, requirements_met)
    """
    requirements = []
    
    if len(password) >= 8:
        requirements.append("length")
    if re.search(r'\d', password):
        requirements.append("number")
    if re.search(r'[A-Z]', password):
        requirements.append("uppercase")
    if re.search(r'[a-z]', password):
        requirements.append("lowercase")
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        requirements.append("special")
    
    score = len(requirements)
    return score, requirements


def get_strength_label(score: int) -> str:
    """Convert score to strength label."""
    if score <= 2:
        return "weak"
    elif score <= 3:
        return "medium"
    elif score <= 4:
        return "strong"
    else:
        return "very_strong"


def check_cooldown(email: str) -> tuple[bool, int]:
    """
    Check if email is in cooldown period.
    Returns: (can_resend, seconds_remaining)
    """
    last_request = verification_cooldowns.get(email)
    if last_request is None:
        return True, 0
    
    elapsed = (datetime.utcnow() - last_request).total_seconds()
    if elapsed >= VERIFICATION_COOLDOWN_SECONDS:
        return True, 0
    
    return False, int(VERIFICATION_COOLDOWN_SECONDS - elapsed)


def generate_reset_token() -> str:
    """Generate secure random token for password reset."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/auth/resend-code", response_model=ResendCodeResponse)
async def resend_verification_code(request: ResendCodeRequest):
    """
    Resend verification code to user's email.
    Enforces 45-second cooldown between requests.
    """
    email = request.email.lower()
    
    # Check cooldown
    can_resend, seconds_remaining = check_cooldown(email)
    
    if not can_resend:
        raise HTTPException(
            status_code=429,
            detail={
                "success": False,
                "error": f"Please wait {seconds_remaining} seconds before requesting another code",
                "retry_after": seconds_remaining
            }
        )
    
    # TODO: Check if user exists in database
    # TODO: Generate new verification code
    # TODO: Send email with verification code
    
    # Record this request time
    verification_cooldowns[email] = datetime.utcnow()
    
    return ResendCodeResponse(
        success=True,
        cooldown_seconds=VERIFICATION_COOLDOWN_SECONDS,
        message="Verification code resent to your email"
    )


@router.post("/auth/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(request: ForgotPasswordRequest):
    """
    Request password reset link.
    Sends email with secure reset token.
    """
    email = request.email.lower()
    
    # TODO: Check if user exists in database
    # For security, return success even if email doesn't exist
    # This prevents email enumeration attacks
    
    # Generate reset token
    token = generate_reset_token()
    token_hash = hash_token(token)
    
    # Store token with expiry
    password_reset_tokens[token_hash] = {
        "email": email,
        "expires": datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS),
        "used": False
    }
    
    # TODO: Send email with reset link
    # reset_link = f"https://predict.previlium.com/reset-password?token={token}"
    
    # Log for development (remove in production)
    print(f"[DEV] Password reset token for {email}: {token}")
    
    return ForgotPasswordResponse(
        success=True,
        message="Password reset instructions sent to your email"
    )


@router.post("/auth/reset-password", response_model=ResetPasswordResponse)
async def reset_password(request: ResetPasswordRequest):
    """
    Reset password using token from email.
    Validates token and password strength.
    """
    token = request.token
    new_password = request.new_password
    token_hash = hash_token(token)
    
    # Validate token exists
    if token_hash not in password_reset_tokens:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Invalid or expired reset token"
            }
        )
    
    token_data = password_reset_tokens[token_hash]
    
    # Check if token is expired
    if datetime.utcnow() > token_data["expires"]:
        del password_reset_tokens[token_hash]
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Reset token has expired. Please request a new one."
            }
        )
    
    # Check if token was already used
    if token_data["used"]:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "This reset link has already been used. Please request a new one."
            }
        )
    
    # Validate password strength
    score, requirements = calculate_password_strength(new_password)
    if score < 3:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Password does not meet requirements",
                "requirements": ["8+ chars", "number", "uppercase", "lowercase", "special"],
                "score": score
            }
        )
    
    # TODO: Update password in database
    # TODO: Invalidate all existing sessions for this user
    
    # Mark token as used
    token_data["used"] = True
    
    return ResetPasswordResponse(
        success=True,
        message="Password reset successful. Please log in with your new password."
    )


@router.get("/auth/check-email", response_model=CheckEmailResponse)
async def check_email(email: str = Query(..., description="Email address to check")):
    """
    Check if email exists (for login) or is available (for registration).
    """
    # TODO: Query actual database
    # Mock implementation
    email_exists = email in users_db
    
    if email_exists:
        return CheckEmailResponse(
            exists=True,
            available=False,
            message="Email is already registered"
        )
    else:
        return CheckEmailResponse(
            exists=False,
            available=True,
            message="Email is available"
        )


@router.get("/validate/password", response_model=PasswordStrengthResponse)
async def validate_password(password: str = Query(..., description="Password to validate")):
    """
    Check password strength and return requirements checklist.
    """
    score, requirements = calculate_password_strength(password)
    strength = get_strength_label(score)
    
    return PasswordStrengthResponse(
        strength=strength,
        requirements_met=requirements,
        score=score
    )


@router.post("/user/profile-picture", response_model=ProfilePictureResponse)
async def upload_profile_picture(file: UploadFile = File(...)):
    """
    Upload user profile picture.
    Validates: file size (<2MB), format (JPG/PNG), dimensions.
    """
    import io
    from PIL import Image
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Invalid file type. Only JPG and PNG are allowed."
            }
        )
    
    # Read file content
    contents = await file.read()
    
    # Validate file size (2MB max)
    max_size = 2 * 1024 * 1024  # 2MB
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "File too large. Maximum size is 2MB."
            }
        )
    
    try:
        # Open image to validate and get dimensions
        image = Image.open(io.BytesIO(contents))
        width, height = image.size
        
        # Validate minimum dimensions
        min_dimension = 128
        if width < min_dimension or height < min_dimension:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": f"Image too small. Minimum dimensions are {min_dimension}x{min_dimension}px."
                }
            )
        
        # Validate maximum dimensions
        max_dimension = 2048
        if width > max_dimension or height > max_dimension:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": f"Image too large. Maximum dimensions are {max_dimension}x{max_dimension}px."
                }
            )
        
        # TODO: Save to cloud storage (S3, Cloudflare R2, etc.)
        # TODO: Generate thumbnail
        # TODO: Update user record in database
        
        # Mock response
        return ProfilePictureResponse(
            success=True,
            url=f"https://cdn.predict.com/avatars/user_{hash(file.filename)}.jpg",
            thumbnail_url=f"https://cdn.predict.com/avatars/user_{hash(file.filename)}_thumb.jpg",
            dimensions={"width": width, "height": height}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": f"Invalid image file: {str(e)}"
            }
        )


@router.delete("/user/profile-picture")
async def delete_profile_picture():
    """
    Delete user profile picture.
    """
    # TODO: Delete from cloud storage
    # TODO: Update user record in database
    
    return {"success": True, "message": "Profile picture removed"}


# ============================================================================
# INTEGRATION WITH EXISTING AUTH ROUTER
# ============================================================================

"""
Add to your main auth.py or routes file:

from app.api.v1.auth_routes import router as auth_extension_router

# In your main router setup:
router.include_router(auth_extension_router)

Or merge these endpoints into your existing auth router.
"""
