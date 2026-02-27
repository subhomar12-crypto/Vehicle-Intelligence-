"""
Authentication endpoints.

Handles:
- User registration (from old /api/register)
- Email verification (from old /api/verify, /api/verify-email)
- Login (from old /api/auth/device-login, /api/auth/verify-code)
- Password reset
- API key management
- Token refresh

Ported from: C:/OBDserver/Previlium_OBD_Server/main.py
"""

import asyncio
import hashlib
import logging
import secrets
import time
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Request, Response, BackgroundTasks, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.user import User, ApiKey
from predict.core.db.models.vehicle import VehicleProfile
from predict.core.db.models.audit import VerificationCode
from predict.core.db.repositories.user_repo import UserRepository, ApiKeyRepository
from predict.core.security.hashing import hash_password, verify_password, generate_api_key, hash_api_key
from predict.core.security.jwt_handler import create_token, verify_token, refresh_token
from predict.core.middleware.error_handler import APIError, ErrorCode
from predict.core.middleware.rate_limiter import get_rate_limiter
from predict.core.services.email_service import EmailService
from predict.core.services.websocket_service import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()
legacy_router = APIRouter()  # For legacy Android routes

# ---- Rate-limiting dependencies (per-IP sliding window) ----
_rl = get_rate_limiter()

async def _rate_limit_register(request: Request):
    allowed, meta = await _rl.is_allowed(
        f"{_rl._get_client_ip(request)}:/auth/register", limit=5, window_seconds=3600
    )
    if not allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many registration attempts. Try again later.")

async def _rate_limit_login(request: Request):
    allowed, meta = await _rl.is_allowed(
        f"{_rl._get_client_ip(request)}:/auth/login", limit=10, window_seconds=3600
    )
    if not allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts. Try again later.")

async def _rate_limit_code(request: Request):
    allowed, meta = await _rl.is_allowed(
        f"{_rl._get_client_ip(request)}:/auth/code", limit=5, window_seconds=3600
    )
    if not allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many code requests. Try again later.")

# =============================================================================
# COOKIE HELPERS
# =============================================================================

def _make_api_key_cookie(api_key: str) -> str:
    """Build a Set-Cookie header value for the API key (HttpOnly, Secure)."""
    return (
        f"api_key={api_key}; "
        "HttpOnly; "
        "Secure; "
        "SameSite=Lax; "
        "Path=/; "
        "Max-Age=2592000"  # 30 days
    )


def _make_clear_cookie() -> str:
    """Build a Set-Cookie header value that clears the API key cookie."""
    return "api_key=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0"


# =============================================================================
# REQUEST/RESPONSE MODELS (Exact same schema as old code)
# =============================================================================

class RegisterRequest(BaseModel):
    """Request model for customer registration (from old CustomerRegisterRequest)."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default="", max_length=20)
    car_plate: str = Field(..., min_length=2, max_length=20)
    car_make: str = Field(default="", max_length=50)
    car_model: str = Field(default="", max_length=50)
    car_year: int = Field(default=0, ge=0, le=2100)
    password: str = Field(..., min_length=8)
    engine_type: Optional[str] = Field(default=None, max_length=50)
    fuel_type: Optional[str] = Field(default=None, max_length=50)
    displacement: Optional[str] = Field(default=None, max_length=10)
    transmission: Optional[str] = Field(default=None, max_length=50)
    vin: Optional[str] = Field(default=None, max_length=17)
    drivetrain: Optional[str] = Field(default=None, max_length=20)
    category: Optional[str] = Field(default=None, max_length=20)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator('car_plate')
    @classmethod
    def validate_car_plate(cls, v: str) -> str:
        return v.upper().strip()


class RegisterResponse(BaseModel):
    """Response model for registration."""
    success: bool
    message: str
    customer_id: int
    email_sent: bool


class VerifyEmailRequest(BaseModel):
    """Request model for email verification (from old CustomerVerifyRequest)."""
    email: EmailStr
    verification_code: str = Field(..., min_length=6, max_length=6)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower().strip()


class VerifyEmailResponse(BaseModel):
    """Response model for email verification."""
    success: bool
    message: str
    verified: bool
    api_key: Optional[str] = None
    user_id: Optional[int] = None
    name: Optional[str] = None
    tier: Optional[str] = None
    phone: Optional[str] = None
    car_plate: Optional[str] = None


class LoginRequest(BaseModel):
    """Request model for login with email/password."""
    email: EmailStr
    password: str
    device_id: Optional[str] = None  # Per-device key scoping (e.g. "web", "android_xxx")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginResponse(BaseModel):
    """Response model for login."""
    success: bool
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    email: str
    name: str
    tier: str


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh."""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Response model for token refresh."""
    success: bool
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class DeviceLoginRequest(BaseModel):
    """Request model for device-bound login (from old main.py)."""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    device_id: str = Field(..., min_length=8)
    device_name: Optional[str] = None
    device_type: str = "phone"  # phone, tablet, desktop
    device_model: Optional[str] = None
    device_os: Optional[str] = None
    device_os_version: Optional[str] = None
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower().strip()
    
    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        return v.strip().replace(" ", "")


class DeviceLoginResponse(BaseModel):
    """Response model for device login."""
    success: bool
    is_new_user: bool
    is_new_device: bool
    user_id: int
    name: str
    email: str
    tier: str
    key_id: Optional[str] = None
    device_id: str
    api_key: Optional[str] = None  # Only for new devices


class RequestCodeRequest(BaseModel):
    """Request model for login code request."""
    email: EmailStr
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower().strip()


class RequestCodeResponse(BaseModel):
    """Response model for code request."""
    success: bool
    message: str


class ForgotPasswordRequest(BaseModel):
    """Request model for password reset request."""
    email: EmailStr
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower().strip()


class ResetPasswordRequest(BaseModel):
    """Request model for password reset."""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower().strip()


class LogoutRequest(BaseModel):
    """Request model for logout."""
    device_id: Optional[str] = None


class UserMeResponse(BaseModel):
    """Response model for current user info."""
    success: bool
    user_id: int
    email: str
    name: str
    phone: Optional[str]
    tier: str
    verified: bool
    car_plate: Optional[str]
    car_make: Optional[str]
    car_model: Optional[str]
    car_year: Optional[int]


class CreateApiKeyRequest(BaseModel):
    """Request model for API key creation."""
    name: str
    tier: Optional[str] = "free"
    expires_days: Optional[int] = None


class ApiKeyResponse(BaseModel):
    """Response model for API key."""
    id: int
    name: str
    tier: str
    permissions: list
    created_at: str
    expires_at: Optional[str]
    last_used_at: Optional[str]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return ''.join(secrets.choice('0123456789') for _ in range(6))


def _hash_code(code: str) -> str:
    """Hash a verification code for storage using bcrypt."""
    try:
        import bcrypt
        return bcrypt.hashpw(code.encode(), bcrypt.gensalt(rounds=10)).decode()
    except ImportError:
        # Fallback to SHA-256 only if bcrypt is unavailable
        return hashlib.sha256(code.encode()).hexdigest()


def _verify_code_hash(code: str, stored_hash: str) -> bool:
    """Verify a verification code against its stored hash."""
    try:
        import bcrypt
        if stored_hash.startswith("$2"):
            return bcrypt.checkpw(code.encode(), stored_hash.encode())
    except ImportError:
        pass
    # Fallback: SHA-256 comparison for legacy codes
    return hashlib.sha256(code.encode()).hexdigest() == stored_hash


async def _get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email (case-insensitive)."""
    result = await session.execute(
        select(User).where(User.email == email.lower().strip())
    )
    return result.scalar_one_or_none()


async def _create_verification_code(
    session: AsyncSession,
    user_id: int,
    purpose: str = 'email'
) -> str:
    """Create a verification code and store it."""
    code = _generate_verification_code()
    code_hash = _hash_code(code)
    now = time.time()
    
    verification = VerificationCode(
        user_id=user_id,
        code=code_hash,
        type=purpose,
        created_at=now,
        expires_at=now + (24 * 3600),  # 24 hours
        used=False,
    )
    session.add(verification)
    await session.flush()
    
    return code


async def _verify_code(
    session: AsyncSession,
    user_id: int,
    code: str,
    purpose: str = 'email'
) -> bool:
    """Verify a verification code.

    Uses bcrypt comparison (with SHA-256 fallback for legacy codes).
    Enforces a max of 5 attempts per code before invalidation.
    """
    now = time.time()

    # Fetch all unused, non-expired codes for this user+purpose
    result = await session.execute(
        select(VerificationCode).where(
            VerificationCode.user_id == user_id,
            VerificationCode.type == purpose,
            VerificationCode.used == False,
            VerificationCode.expires_at > now,
        )
    )
    candidates = result.scalars().all()

    if not candidates:
        return False

    for verification in candidates:
        # Check attempt count (stored in nonce field as "attempts:N" prefix or absent)
        attempt_count = _get_attempt_count(verification)

        if attempt_count >= 5:
            # Code exhausted — mark as used (invalidated)
            verification.used = True
            await session.flush()
            continue

        # Increment attempt counter
        _increment_attempt_count(verification)

        if _verify_code_hash(code, verification.code):
            # Correct code — mark as used
            verification.used = True

            # Mark user as verified if email verification
            if purpose == 'email':
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one()
                user.verified = True

            await session.flush()
            return True
        else:
            # Wrong code — persist the incremented attempt count
            await session.flush()

    return False


def _get_attempt_count(verification: VerificationCode) -> int:
    """Read the attempt counter stored in the submitted_nonce field."""
    raw = verification.submitted_nonce or ""
    if raw.startswith("attempts:"):
        try:
            return int(raw.split(":")[1])
        except (ValueError, IndexError):
            return 0
    return 0


def _increment_attempt_count(verification: VerificationCode) -> None:
    """Increment the attempt counter stored in the submitted_nonce field."""
    count = _get_attempt_count(verification) + 1
    verification.submitted_nonce = f"attempts:{count}"


# =============================================================================
# REGISTRATION ENDPOINTS
# =============================================================================

@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    request: RegisterRequest,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _rl_guard: None = Depends(_rate_limit_register),
):
    """
    Register a new user.
    
    Ported from: /api/register in old main.py (line 5664)
    """
    user_repo = UserRepository(db)
    email_service = EmailService()
    
    # Check if email already registered
    existing = await user_repo.get_by_email(request.email)
    if existing:
        if existing.verified:
            raise APIError(
                status_code=409,
                code=ErrorCode.VALIDATION_ERROR,
                message="This email is already registered. Please login instead.",
                details={"error": "email_exists"}
            )
        else:
            # Resend verification code for unverified user
            code = await _create_verification_code(db, existing.id, 'email')
            bg_tasks.add_task(
                email_service.send_verification_email,
                to_email=existing.email,
                name=existing.name,
                code=code,
            )
            return RegisterResponse(
                success=True,
                message="Verification code resent to your email.",
                customer_id=existing.id,
                email_sent=True,
            )
    
    # Create user
    user = User(
        email=request.email.lower().strip(),
        name=request.name,
        phone=request.phone,
        password_hash=hash_password(request.password),
        car_plate=request.car_plate.upper().strip(),
        tier='free',
        verified=False,
        status='active',
        registered_via='android',
    )
    db.add(user)
    await db.flush()  # Get user.id
    
    # Create default API key — store bcrypt hash + prefix only (raw key returned once)
    plain_key = generate_api_key("pred")
    now = time.time()
    api_key = ApiKey(
        key_prefix=plain_key[:8],
        user_id=user.id,
        key_hash=hash_api_key(plain_key),
        name="Default Key",
        status="active",
        created_at=now,
        tier='free',
        permissions=['vehicle_data', 'diagnostic', 'predict'],
        apps=['obd', 'guardian'],
    )
    db.add(api_key)

    # Create vehicle profile from registration data
    vehicle = VehicleProfile(
        owner_user_id=user.id,
        name=f"{request.car_make} {request.car_model}".strip() or request.car_plate,
        make=request.car_make or None,
        model=request.car_model or None,
        year=request.car_year or None,
        license_plate=request.car_plate.upper().strip(),
        engine_type=request.engine_type or None,
        fuel_type=request.fuel_type or None,
        displacement=request.displacement or None,
        transmission=request.transmission or None,
        vin=request.vin or None,
        drivetrain=request.drivetrain or None,
        category=request.category or None,
        created_at=now,
    )
    db.add(vehicle)
    await db.flush()  # Get vehicle.profile_id

    # Link API key to the vehicle profile
    api_key.profile_id = vehicle.profile_id

    # Create and send verification code
    code = await _create_verification_code(db, user.id, 'email')

    bg_tasks.add_task(
        email_service.send_verification_email,
        to_email=user.email,
        name=user.name,
        code=code,
    )

    await db.commit()

    # Trigger background vehicle research if we have enough info
    if vehicle.make and vehicle.model and vehicle.year:
        try:
            from predict.core.services.vehicle_research_service import get_research_service
            service = get_research_service()
            asyncio.create_task(service.research_vehicle(vehicle.profile_id))
        except Exception as e:
            logger.debug(f"Research trigger failed (non-critical): {e}")
    
    # Broadcast new user registration via WebSocket
    try:
        await ws_manager.broadcast({
            "type": "USER_CHANGE",
            "event": "user_registered",
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "tier": "free",
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.debug(f"WebSocket broadcast failed (non-critical): {e}")
    
    logger.info(f"User registered: {user.email}, customer_id={user.id}")
    
    return RegisterResponse(
        success=True,
        message="Registration successful. Please check your email for verification code.",
        customer_id=user.id,
        email_sent=True,
    )


@legacy_router.post("/register", response_model=RegisterResponse)
async def register_legacy(
    request: RegisterRequest,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Legacy registration endpoint for Android compatibility."""
    return await register(request, bg_tasks, db)


# =============================================================================
# EMAIL VERIFICATION ENDPOINTS
# =============================================================================

@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    request: VerifyEmailRequest,
    bg_tasks: BackgroundTasks,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify email with code.
    
    Ported from: /api/verify-email in old main.py (line 3913)
    """
    user = await _get_user_by_email(db, request.email)
    
    if not user:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid email or code",
        )
    
    # Verify code
    if await _verify_code(db, user.id, request.verification_code, 'email'):
        # Generate a fresh API key for the verified user (raw key can't be recovered from DB)
        plain_key = generate_api_key("pred")
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.user_id == user.id,
                ApiKey.status == "active",
            ).order_by(ApiKey.created_at.desc()).limit(1)
        )
        existing_key = result.scalars().first()

        if existing_key:
            # Rotate the existing key — update hash and prefix
            existing_key.key_prefix = plain_key[:8]
            existing_key.key_hash = hash_api_key(plain_key)
            existing_key.created_at = time.time()
        else:
            # Create new key
            new_key = ApiKey(
                key_prefix=plain_key[:8],
                user_id=user.id,
                key_hash=hash_api_key(plain_key),
                name="Default Key",
                status="active",
                created_at=time.time(),
                tier=user.tier,
                permissions=['vehicle_data', 'diagnostic', 'predict'],
                apps=['obd', 'guardian'],
            )
            db.add(new_key)

        await db.commit()

        # Set HttpOnly cookie for web clients
        response.headers["Set-Cookie"] = _make_api_key_cookie(plain_key)

        return VerifyEmailResponse(
            success=True,
            message="Email verified successfully!",
            verified=True,
            api_key=plain_key,
            user_id=user.id,
            name=user.name,
            tier=user.tier,
            phone=user.phone,
            car_plate=user.car_plate,
        )
    else:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid or expired verification code",
        )


@legacy_router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email_legacy(
    request: VerifyEmailRequest,
    bg_tasks: BackgroundTasks,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Legacy verify endpoint for Android compatibility."""
    return await verify_email(request, bg_tasks, response, db)


@legacy_router.post("/verify", response_model=VerifyEmailResponse)
async def verify_legacy_alias(
    request: VerifyEmailRequest,
    bg_tasks: BackgroundTasks,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Legacy alias: Android calls /api/verify instead of /api/verify-email."""
    return await verify_email(request, bg_tasks, response, db)


# =============================================================================
# LOGIN ENDPOINTS
# =============================================================================

@router.post("/login")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _rl_guard: None = Depends(_rate_limit_login),
):
    """
    Login with email and password.

    Returns API key + user info in the format Android expects.
    """
    user = await _get_user_by_email(db, request.email)

    if not user or not user.password_hash:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid email or password",
        )

    # Users registered via Google can't use password login
    if user.password_hash == "GOOGLE_AUTH":
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="This account uses Google Sign-In. Please use 'Continue with Google' instead.",
        )

    if not verify_password(request.password, user.password_hash):
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid email or password",
        )

    if not user.verified:
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Email not verified. Please verify your email first.",
        )

    # Update last login
    user.last_login = time.time()
    await db.flush()

    # Generate/rotate API key — per-device so logging in from website
    # doesn't invalidate the Android app's key (and vice versa)
    device_tag = f"device_{request.device_id}" if request.device_id else "password_login"
    key_result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.name == device_tag,
            ApiKey.status == "active",
        )
    )
    api_key = key_result.scalar_one_or_none()

    plain_key = generate_api_key("pred")
    if api_key:
        api_key.key_prefix = plain_key[:8]
        api_key.key_hash = hash_api_key(plain_key)
        api_key.created_at = time.time()
    else:
        api_key = ApiKey(
            key_prefix=plain_key[:8],
            user_id=user.id,
            key_hash=hash_api_key(plain_key),
            name=device_tag,
            status="active",
            created_at=time.time(),
            tier=user.tier,
            permissions=['vehicle_data', 'diagnostic', 'predict'],
            apps=['obd', 'guardian'],
        )
        db.add(api_key)
        await db.flush()

    await db.commit()

    logger.info(f"Password login: {user.email} (user_id={user.id}, device={device_tag})")

    # Return format matching Android AuthResponse: { token, user { id, email, name, subscription_tier } }
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={
        "token": plain_key,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name or "",
            "subscription_tier": user.tier or "free",
        },
    })
    # Set HttpOnly cookie for web clients
    response.headers["Set-Cookie"] = _make_api_key_cookie(plain_key)
    return response


@router.post("/device-login", response_model=DeviceLoginResponse)
async def device_login(
    request: DeviceLoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Login from device with device binding.
    
    Ported from: /api/auth/device-login in old main.py (line 7386)
    
    This endpoint:
    1. Verifies the login code
    2. Creates/retrieves a device-bound API key
    3. Returns the API key only once (for new devices)
    """
    email = request.email
    code = request.code
    device_id = request.device_id
    
    # Validate inputs
    if not device_id or len(device_id) < 8:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid device_id",
        )
    
    # Validate code format
    if not code or len(code) != 6 or not code.isdigit():
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid verification code format",
        )
    
    # Find user
    user = await _get_user_by_email(db, email)
    
    # Verify code (for existing users)
    if user:
        code_valid = await _verify_code(db, user.id, code, 'login')
        if not code_valid:
            raise APIError(
                status_code=401,
                code=ErrorCode.AUTH_INVALID_KEY,
                message="Invalid or expired verification code",
            )
        is_new_user = False
    else:
        # Create new user for code-based login
        user = User(
            email=email,
            name=email.split('@')[0],
            verified=True,
            status='active',
            tier='free',
            registered_via='android',
        )
        db.add(user)
        await db.flush()
        is_new_user = True
    
    # Mark user verified
    user.verified = True
    user.last_login = time.time()
    await db.flush()
    
    # Get or create device-bound API key
    # Look for existing key for this device
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.name == f"device_{device_id}",
            ApiKey.status == "active",
        )
    )
    existing_key = result.scalar_one_or_none()
    
    # Always generate a fresh API key (bcrypt hashed — can't be recovered)
    plain_key = generate_api_key("pred")
    if existing_key:
        # Rotate existing device key — update prefix and hash
        is_new_device = False
        existing_key.key_prefix = plain_key[:8]
        existing_key.key_hash = hash_api_key(plain_key)
        existing_key.created_at = time.time()
    else:
        # New device — store bcrypt hash + prefix only
        is_new_device = True
        now = time.time()

        new_key = ApiKey(
            key_prefix=plain_key[:8],
            user_id=user.id,
            key_hash=hash_api_key(plain_key),
            name=f"device_{device_id}",
            status="active",
            created_at=now,
            tier=user.tier,
            permissions=['vehicle_data', 'diagnostic', 'predict'],
            apps=['obd', 'guardian'],
        )
        db.add(new_key)
        await db.flush()

    await db.commit()

    logger.info(f"Device login: {email} on device {device_id[:8]}... (new_user={is_new_user}, new_device={is_new_device})")

    return DeviceLoginResponse(
        success=True,
        is_new_user=is_new_user,
        is_new_device=is_new_device,
        user_id=user.id,
        name=user.name,
        email=user.email,
        tier=user.tier,
        key_id=plain_key[:8],
        device_id=device_id,
        api_key=plain_key,
    )


@router.post("/request-code", response_model=RequestCodeResponse)
async def request_login_code(
    request: RequestCodeRequest,
    req: Request,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _rl_guard: None = Depends(_rate_limit_code),
):
    """
    Request a login verification code.
    
    Ported from: /api/auth/request-code in old main.py (line 6973)
    
    Sends a 6-digit code to the user's email.
    The code expires after 24 hours.
    """
    email = request.email
    
    # Basic validation
    if not email or '@' not in email or '.' not in email:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid email address",
        )
    
    # Find or create user
    user = await _get_user_by_email(db, email)
    if not user:
        # Create new user for code-based login
        user = User(
            email=email,
            name=email.split('@')[0],
            verified=False,
            status='active',
            tier='free',
            registered_via='android',
        )
        db.add(user)
        await db.flush()
    
    # Create verification code
    code = await _create_verification_code(db, user.id, 'login')
    
    # Send email
    email_service = EmailService()
    bg_tasks.add_task(
        email_service.send_verification_email,
        to_email=email,
        name=user.name,
        code=code,
    )
    
    await db.commit()
    
    logger.info(f"Login code requested for: {email}")
    
    return RequestCodeResponse(
        success=True,
        message="Verification code sent to your email.",
    )


class VerifyCodeRequest(BaseModel):
    """Request model for verifying login code."""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    device_id: Optional[str] = None  # Per-device key scoping (e.g. "web", "android_xxx")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        return v.strip().replace(" ", "")


class VerifyCodeResponse(BaseModel):
    """Response model for code verification."""
    success: bool
    verified: bool
    api_key: Optional[str] = None
    user_id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    tier: Optional[str] = None
    message: Optional[str] = None


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_login_code(
    request: VerifyCodeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a 6-digit login code.
    
    This is used when a user requests a login code via POST /auth/request-code
    instead of using their password.
    
    Returns the user's API key on success.
    """
    # Find user by email
    user = await _get_user_by_email(db, request.email)
    
    if not user:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid email or code",
        )
    
    # Verify the code (uses bcrypt comparison + attempt counting)
    code_valid = await _verify_code(db, user.id, request.code, 'login')

    if not code_valid:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid or expired verification code",
        )

    # Mark user as verified
    user.verified = True
    user.last_login = time.time()
    await db.flush()
    
    # Get or create API key — per-device so logging in from website
    # doesn't invalidate the Android app's key (and vice versa)
    device_tag = f"device_{request.device_id}" if request.device_id else "code_login"
    key_result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.name == device_tag,
            ApiKey.status == "active",
        )
    )
    api_key = key_result.scalar_one_or_none()

    # Always generate a fresh API key on login (bcrypt hashed — can't be recovered)
    plain_key = generate_api_key("pred")
    if api_key:
        # Rotate existing device key — update prefix and hash
        api_key.key_prefix = plain_key[:8]
        api_key.key_hash = hash_api_key(plain_key)
        api_key.created_at = time.time()
    else:
        # Create new device key
        api_key = ApiKey(
            key_prefix=plain_key[:8],
            user_id=user.id,
            key_hash=hash_api_key(plain_key),
            name=device_tag,
            status="active",
            created_at=time.time(),
            tier=user.tier,
            permissions=['vehicle_data', 'diagnostic', 'predict'],
            apps=['obd', 'guardian'],
        )
        db.add(api_key)
        await db.flush()
    api_key_value = plain_key

    await db.commit()

    logger.info(f"Login code verified for: {request.email} (device={device_tag})")

    # Set HttpOnly cookie for web clients
    response.headers["Set-Cookie"] = _make_api_key_cookie(api_key_value)

    return VerifyCodeResponse(
        success=True,
        verified=True,
        api_key=api_key_value,
        user_id=user.id,
        name=user.name,
        email=user.email,
        tier=user.tier or "free",
        message="Login successful",
    )


# =============================================================================
# TOKEN REFRESH
# =============================================================================

@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest,
):
    """
    Refresh access token using refresh token.
    
    Returns new access token and refresh token.
    """
    # Verify refresh token
    payload = verify_token(request.refresh_token)
    
    if not payload:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_EXPIRED_TOKEN,
            message="Invalid or expired refresh token",
        )
    
    # Check it's a refresh token
    guardian_id = payload.get('sub', '')
    if not guardian_id.startswith('refresh_'):
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid refresh token",
        )
    
    # Create new tokens
    user_id = guardian_id.replace('refresh_', '')
    access_token = create_token(
        guardian_id=f"user_{user_id}",
        expires_hours=24,
    )
    new_refresh_token = create_token(
        guardian_id=f"refresh_{user_id}",
        expires_hours=168,
    )
    
    return RefreshTokenResponse(
        success=True,
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=86400,
    )


# =============================================================================
# PASSWORD RESET
# =============================================================================

@router.post("/forgot-password", response_model=RequestCodeResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _rl_guard: None = Depends(_rate_limit_code),
):
    """
    Request password reset code.
    
    Always returns success to prevent email enumeration.
    """
    user = await _get_user_by_email(db, request.email)
    
    if user:
        # Create reset code
        code = await _create_verification_code(db, user.id, 'password_reset')
        
        # Send email
        email_service = EmailService()
        bg_tasks.add_task(
            email_service.send_password_reset_email,
            to_email=user.email,
            name=user.name,
            code=code,
        )
        
        await db.commit()
    
    # Always return success
    return RequestCodeResponse(
        success=True,
        message="If an account exists with this email, a reset code has been sent.",
    )


@router.post("/reset-password", response_model=VerifyEmailResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password with verification code.
    """
    user = await _get_user_by_email(db, request.email)
    
    if not user:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid email or reset code",
        )
    
    # Verify code
    if await _verify_code(db, user.id, request.code, 'password_reset'):
        # Update password
        user.password_hash = hash_password(request.new_password)
        await db.commit()
        
        return VerifyEmailResponse(
            success=True,
            message="Password reset successful. Please login with your new password.",
            verified=True,
        )
    else:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid or expired reset code",
        )


# =============================================================================
# GOOGLE OAUTH
# =============================================================================

class GoogleSignInRequest(BaseModel):
    """Request model for Google Sign-In."""
    id_token: str
    device_id: Optional[str] = None  # Per-device key scoping (e.g. "web", "android_xxx")


class GoogleSignInResponse(BaseModel):
    """Response model for Google Sign-In."""
    success: bool
    api_key: Optional[str] = None
    user_id: int
    name: str
    email: str
    tier: str
    is_new_user: bool


@router.post("/google", response_model=GoogleSignInResponse)
async def google_sign_in(
    request: GoogleSignInRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with Google ID token.
    Auto-registers if user doesn't exist.
    """
    import os
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except ImportError:
        raise APIError(
            status_code=500,
            code=ErrorCode.INTERNAL_ERROR,
            message="Google Sign-In not configured. Please install google-auth.",
        )
    
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    if not GOOGLE_CLIENT_ID:
        raise APIError(
            status_code=500,
            code=ErrorCode.INTERNAL_ERROR,
            message="Google Sign-In not configured. GOOGLE_CLIENT_ID missing.",
        )
    
    try:
        # Verify the Google ID token
        idinfo = google_id_token.verify_oauth2_token(
            request.id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        
        email = idinfo["email"]
        name = idinfo.get("name", email.split('@')[0])
        
    except ValueError as e:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message=f"Invalid Google token: {e}",
        )
    
    # Check if user already exists
    user = await _get_user_by_email(db, email)
    is_new_user = False
    
    if not user:
        # Auto-register
        is_new_user = True
        user = User(
            email=email,
            name=name,
            password_hash="GOOGLE_AUTH",  # No password for Google users
            verified=True,  # Google emails are pre-verified
            tier="free",
            registered_via="android",
            status="active",
        )
        db.add(user)
        await db.flush()
    
    # Update last login
    user.last_login = time.time()
    await db.flush()
    
    # Get or create API key — per-device so logging in from website
    # doesn't invalidate the Android app's key (and vice versa)
    device_tag = f"device_{request.device_id}" if request.device_id else "google_login"
    key_result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.name == device_tag,
            ApiKey.status == "active",
        )
    )
    api_key = key_result.scalar_one_or_none()

    # Always generate a fresh API key on Google sign-in (bcrypt hashed — can't be recovered)
    plain_key = generate_api_key("pred")
    if api_key:
        # Rotate existing device key — update prefix and hash
        api_key.key_prefix = plain_key[:8]
        api_key.key_hash = hash_api_key(plain_key)
        api_key.created_at = time.time()
    else:
        # Create new device key
        api_key = ApiKey(
            key_prefix=plain_key[:8],
            user_id=user.id,
            key_hash=hash_api_key(plain_key),
            name=device_tag,
            status="active",
            created_at=time.time(),
            tier=user.tier,
            permissions=['vehicle_data', 'diagnostic', 'predict'],
            apps=['obd', 'guardian'],
        )
        db.add(api_key)
        await db.flush()
    api_key_value = plain_key

    await db.commit()

    # Check if user has any vehicle profiles — treat users without vehicles
    # as "new" so Android routes them to the AddVehicle screen
    vehicle_result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.owner_user_id == user.id
        ).limit(1)
    )
    has_vehicle = vehicle_result.scalar_one_or_none() is not None
    needs_vehicle_setup = is_new_user or not has_vehicle

    logger.info(f"Google Sign-In: {email} (new_user={is_new_user}, has_vehicle={has_vehicle}, device={device_tag})")

    # Set HttpOnly cookie for web clients
    response.headers["Set-Cookie"] = _make_api_key_cookie(api_key_value)

    return GoogleSignInResponse(
        success=True,
        api_key=api_key_value,
        user_id=user.id,
        name=user.name or name,
        email=user.email,
        tier=user.tier or "free",
        is_new_user=needs_vehicle_setup,
    )


# =============================================================================
# LOGOUT
# =============================================================================

@router.post("/logout")
async def logout(
    request: LogoutRequest,
    current_user: dict = Depends(get_current_user),
    x_device_id: Optional[str] = Header(None, alias="X-Device-Id"),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout - revoke device API key.
    """
    device_id = request.device_id or x_device_id
    
    if device_id:
        # Revoke device key
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.user_id == current_user['user_id'],
                ApiKey.name == f"device_{device_id}",
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key:
            api_key.status = "revoked"
            await db.commit()

    # Clear HttpOnly cookie for web clients
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={
        "success": True,
        "message": "Logged out successfully",
    })
    response.headers["Set-Cookie"] = _make_clear_cookie()
    return response


# =============================================================================
# CURRENT USER
# =============================================================================

@router.get("/me", response_model=UserMeResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user information.
    
    Ported from: /api/user/profile in old main.py (line 7260)
    """
    user_id = current_user.get('user_id')
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise APIError(
            status_code=404,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="User not found",
        )
    
    return UserMeResponse(
        success=True,
        user_id=user.id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        tier=user.tier,
        verified=user.verified,
        car_plate=user.car_plate,
        car_make=None,  # These would come from vehicle profile
        car_model=None,
        car_year=None,
    )


# =============================================================================
# API KEY MANAGEMENT
# =============================================================================

@router.post("/api-keys")
async def create_api_key(
    request: CreateApiKeyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new API key.
    """
    user_id = current_user['user_id']
    now = time.time()
    
    # Generate key
    plain_key = generate_api_key("pred")
    
    expires_at = None
    if request.expires_days:
        expires_at = now + (request.expires_days * 86400)
    
    api_key = ApiKey(
        key_prefix=plain_key[:8],
        user_id=user_id,
        key_hash=hash_api_key(plain_key),
        name=request.name,
        status="active",
        created_at=now,
        tier=request.tier or current_user.get('tier', 'free'),
        permissions=['vehicle_data', 'diagnostic', 'predict'],
        apps=['obd', 'guardian'],
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()

    return {
        "success": True,
        "api_key": plain_key,  # Only returned once!
        "key_prefix": api_key.key_prefix,
        "message": "Store this key safely - it will not be shown again",
    }


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List API keys (without the actual key values).
    """
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == current_user['user_id'],
            ApiKey.status == "active",
        )
    )
    keys = result.scalars().all()
    
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            tier=k.tier,
            permissions=k.permissions or [],
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(k.created_at)) if k.created_at else None,
            expires_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(k.expires_at)) if k.expires_at else None,
            last_used_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(k.last_used_at)) if k.last_used_at else None,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke an API key by its database ID.
    """
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user['user_id'],
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise APIError(
            status_code=404,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="API key not found",
        )

    api_key.status = "revoked"
    await db.commit()

    return {
        "success": True,
        "message": "API key revoked",
    }


# =============================================================================
# LEGACY LOGIN (Android compatibility)
# =============================================================================
# Android calls POST /auth/login (without /api/ prefix) and expects:
#   { token, user: { id, email, name, subscription_tier }, expires_at }
# The main login returns { access_token, user_id, name, tier, ... }
# This endpoint bridges the format gap.

app_legacy_router = APIRouter()  # Mounted at /auth prefix on the app (not under /api)


async def _legacy_login_handler(request: LoginRequest, db: AsyncSession):
    """Shared login logic for Android-compatible format."""
    user = await _get_user_by_email(db, request.email)

    if not user or not user.password_hash:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid email or password",
        )

    if not verify_password(request.password, user.password_hash):
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid email or password",
        )

    if not user.verified:
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Email not verified. Please verify your email first.",
        )

    # Generate a fresh API key (bcrypt hashed — can't recover old key from DB)
    plain_key = generate_api_key("pred")
    device_tag = f"device_{request.device_id}" if request.device_id else "legacy_login"

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.name == device_tag,
            ApiKey.status == "active",
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key:
        api_key.key_prefix = plain_key[:8]
        api_key.key_hash = hash_api_key(plain_key)
        api_key.created_at = time.time()
    else:
        api_key = ApiKey(
            key_prefix=plain_key[:8],
            user_id=user.id,
            key_hash=hash_api_key(plain_key),
            name=device_tag,
            status="active",
            created_at=time.time(),
            tier=user.tier,
            permissions=['vehicle_data', 'diagnostic', 'predict'],
            apps=['obd', 'guardian'],
        )
        db.add(api_key)

    # Update last login
    user.last_login = time.time()
    await db.commit()

    # Return Android-compatible format
    return {
        "token": plain_key,  # Android stores this as X-API-Key
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "subscription_tier": user.tier,
        },
        "expires_at": int(time.time()) + 86400 * 365,  # 1 year
    }


@app_legacy_router.post("/login")
async def legacy_login_app_level(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Legacy login at /auth/login (Android calls this without /api/ prefix)."""
    return await _legacy_login_handler(request, db)


# Also add to the main legacy_router so /api/auth/login works too
@legacy_router.post("/auth/login")
async def legacy_login_api_level(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Legacy login at /api/auth/login (Android-compatible format)."""
    return await _legacy_login_handler(request, db)
