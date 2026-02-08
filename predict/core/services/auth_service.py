"""
Authentication service with bcrypt primary + SHA-256 fallback.

This service handles:
- User registration and email verification
- Login with password or API key
- API key generation and validation
- Password reset flow
- 30-day migration from SHA-256 to bcrypt
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.user import User, ApiKey
from predict.core.db.models.audit import VerificationCode
from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)


# Configuration
VERIFICATION_CODE_EXPIRY_HOURS = 24
API_KEY_PREFIX = "pk_"


class AuthService:
    """Authentication and authorization service."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    # ========================
    # Password Hashing
    # ========================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against bcrypt hash."""
        password_bytes = password.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    
    @staticmethod
    def hash_api_key_sha256(api_key: str) -> str:
        """Legacy SHA-256 hash for API keys (fallback only)."""
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    
    @staticmethod
    def hash_api_key_bcrypt(api_key: str) -> str:
        """Primary bcrypt hash for API keys."""
        key_bytes = api_key.encode('utf-8')
        salt = bcrypt.gensalt(rounds=10)
        return bcrypt.hashpw(key_bytes, salt).decode('utf-8')
    
    @staticmethod
    def verify_api_key_bcrypt(api_key: str, key_hash: str) -> bool:
        """Verify API key against bcrypt hash."""
        key_bytes = api_key.encode('utf-8')
        hash_bytes = key_hash.encode('utf-8')
        return bcrypt.checkpw(key_bytes, hash_bytes)
    
    # ========================
    # User Registration
    # ========================
    
    async def register_user(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> User:
        """Register a new user."""
        # Check if email exists
        existing = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        if existing.scalar_one_or_none():
            raise APIError(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                message="Email already registered",
            )
        
        # Create user
        user = User(
            email=email.lower().strip(),
            password_hash=self.hash_password(password),
            name=name,
            phone=phone,
            is_active=True,
            is_verified=False,
            tier='free',
        )
        
        self.db.add(user)
        await self.db.flush()  # Get user.id
        
        # Create default API key
        await self.create_api_key(
            user_id=user.id,
            name="Default Key",
            tier='free',
        )
        
        await self.db.commit()
        logger.info(f"User registered: {user.email}")
        
        return user
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> Optional[User]:
        """Authenticate user with email and password."""
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower().strip(),
                User.is_active == True,
            )
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.password_hash:
            return None
        
        if self.verify_password(password, user.password_hash):
            # Update last login
            user.last_login = datetime.now(timezone.utc)
            await self.db.commit()
            return user
        
        return None
    
    # ========================
    # API Key Management
    # ========================
    
    async def create_api_key(
        self,
        user_id: int,
        name: str,
        tier: str = 'free',
        permissions: Optional[list] = None,
        apps: Optional[list] = None,
        expires_days: Optional[int] = None,
    ) -> Tuple[str, ApiKey]:
        """
        Create a new API key.
        
        Returns:
            (plain_api_key, api_key_object)
            
        Note: The plain API key is only returned once - store it securely!
        """
        # Generate random key
        random_part = secrets.token_urlsafe(32)
        plain_key = f"{API_KEY_PREFIX}{random_part}"
        
        # Calculate expiry
        expires_at = None
        if expires_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        
        # Create key record
        api_key = ApiKey(
            user_id=user_id,
            key_hash=self.hash_api_key_bcrypt(plain_key),
            name=name,
            tier=tier,
            permissions=permissions or ['vehicle_data', 'diagnostic'],
            apps=apps or ['obd'],
            is_active=True,
            expires_at=expires_at,
        )
        
        self.db.add(api_key)
        await self.db.commit()
        
        logger.info(f"API key created for user {user_id}: {name}")
        
        return plain_key, api_key
    
    async def validate_api_key(
        self,
        api_key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Validate an API key.
        
        Checks:
        1. bcrypt hash (primary)
        2. SHA-256 fallback (30-day migration)
        
        Returns:
            Key data dict or None if invalid
        """
        if not api_key or not api_key.startswith(API_KEY_PREFIX):
            return None
        
        # Look up by legacy hash first (for migration period)
        legacy_hash = self.hash_api_key_sha256(api_key)
        
        result = await self.db.execute(
            select(ApiKey).where(
                (ApiKey.legacy_sha256_hash == legacy_hash) |
                (ApiKey.key_hash == api_key[:50])  # Partial match for lookup
            )
        )
        
        # Get all potentially matching keys
        potential_keys = result.scalars().all()
        
        for key_record in potential_keys:
            # Skip inactive or expired keys
            if not key_record.is_active:
                continue
            
            if key_record.expires_at and key_record.expires_at < datetime.now(timezone.utc):
                continue
            
            # Try bcrypt verification
            if self.verify_api_key_bcrypt(api_key, key_record.key_hash):
                # Update last used
                key_record.last_used_at = datetime.now(timezone.utc)
                await self.db.commit()
                
                return {
                    'key_id': key_record.id,
                    'user_id': key_record.user_id,
                    'name': key_record.name,
                    'tier': key_record.tier,
                    'permissions': key_record.permissions,
                    'apps': key_record.apps,
                    'profile_id': key_record.profile_id,
                }
            
            # Fallback: Check legacy SHA-256 hash
            if key_record.legacy_sha256_hash == legacy_hash:
                # Auto-upgrade to bcrypt
                key_record.key_hash = self.hash_api_key_bcrypt(api_key)
                key_record.legacy_sha256_hash = None  # Clear legacy
                key_record.last_used_at = datetime.now(timezone.utc)
                await self.db.commit()
                
                logger.info(f"Auto-upgraded API key {key_record.id} from SHA-256 to bcrypt")
                
                return {
                    'key_id': key_record.id,
                    'user_id': key_record.user_id,
                    'name': key_record.name,
                    'tier': key_record.tier,
                    'permissions': key_record.permissions,
                    'apps': key_record.apps,
                    'profile_id': key_record.profile_id,
                }
        
        return None
    
    async def revoke_api_key(self, key_id: int, user_id: int) -> bool:
        """Revoke an API key."""
        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.user_id == user_id,
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return False
        
        api_key.is_active = False
        await self.db.commit()
        
        logger.info(f"API key {key_id} revoked by user {user_id}")
        return True
    
    # ========================
    # Verification Codes
    # ========================
    
    async def create_verification_code(
        self,
        user_id: int,
        purpose: str = 'email',
    ) -> str:
        """Create a verification code for email/phone verification."""
        # Generate 6-digit code
        code = ''.join(secrets.choice('0123456789') for _ in range(6))
        
        # Hash the code for storage
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # Create new code
        verification = VerificationCode(
            user_id=user_id,
            code_hash=code_hash,
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=VERIFICATION_CODE_EXPIRY_HOURS),
            attempts=0,
        )
        
        self.db.add(verification)
        await self.db.commit()
        
        logger.info(f"Verification code created for user {user_id}, purpose={purpose}")
        
        return code
    
    async def verify_code(
        self,
        user_id: int,
        code: str,
        purpose: str = 'email',
    ) -> bool:
        """Verify a verification code."""
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        result = await self.db.execute(
            select(VerificationCode).where(
                VerificationCode.user_id == user_id,
                VerificationCode.code_hash == code_hash,
                VerificationCode.purpose == purpose,
                VerificationCode.used_at.is_(None),
                VerificationCode.expires_at > datetime.now(timezone.utc),
            )
        )
        verification = result.scalar_one_or_none()
        
        if not verification:
            return False
        
        # Mark as used
        verification.used_at = datetime.now(timezone.utc)
        
        # Mark user as verified
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one()
        
        if purpose == 'email':
            user.is_verified = True
        
        await self.db.commit()
        
        logger.info(f"User {user_id} verified with code, purpose={purpose}")
        
        return True
