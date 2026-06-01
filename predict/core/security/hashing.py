"""
Centralized hashing utilities for passwords and API keys.

Uses bcrypt as primary with SHA-256 fallback for legacy compatibility.
"""

import logging
import hashlib
import secrets
from typing import Optional

try:
    import bcrypt
    _has_bcrypt = True
except ImportError:
    _has_bcrypt = False

logger = logging.getLogger(__name__)


def _fallback_pbkdf2(value: str, salt: Optional[bytes] = None) -> str:
    """
    PBKDF2 fallback when bcrypt is unavailable.
    
    Args:
        value: Value to hash
        salt: Optional salt (generated if not provided)
    
    Returns:
        Hashed value string
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    
    key = hashlib.pbkdf2_hmac('sha256', value.encode(), salt, 100000)
    return f"pbkdf2${salt.hex()}${key.hex()}"


def _verify_pbkdf2(value: str, hashed: str) -> bool:
    """Verify a value against a PBKDF2 hash."""
    try:
        parts = hashed.split('$')
        if len(parts) != 3 or parts[0] != 'pbkdf2':
            return False
        
        salt = bytes.fromhex(parts[1])
        expected = _fallback_pbkdf2(value, salt)
        return secrets.compare_digest(expected, hashed)
    except Exception:
        return False


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt (rounds=12).
    
    Args:
        password: Plain text password
    
    Returns:
        Bcrypt hash string
    """
    if _has_bcrypt:
        # bcrypt with 12 rounds
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    else:
        # Fallback to PBKDF2
        logger.warning("bcrypt not available, using PBKDF2 fallback for password")
        return _fallback_pbkdf2(password)


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: Plain text password
        hashed: Stored hash
    
    Returns:
        True if password matches
    """
    if hashed.startswith('pbkdf2$'):
        return _verify_pbkdf2(password, hashed)
    
    if _has_bcrypt:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    else:
        return _verify_pbkdf2(password, hashed)


def hash_api_key(key: str) -> str:
    """
    Hash an API key using bcrypt (rounds=10).
    
    Uses fewer rounds than passwords since API keys are randomly generated
    and high entropy.
    
    Args:
        key: API key string
    
    Returns:
        Bcrypt hash string
    """
    if _has_bcrypt:
        salt = bcrypt.gensalt(rounds=10)
        hashed = bcrypt.hashpw(key.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    else:
        return _fallback_pbkdf2(key)


def verify_api_key(key: str, hashed: str) -> bool:
    """
    Verify an API key against its hash.
    
    Args:
        key: API key string
        hashed: Stored hash
    
    Returns:
        True if key matches
    """
    if hashed.startswith('pbkdf2$'):
        return _verify_pbkdf2(key, hashed)
    
    if _has_bcrypt:
        try:
            return bcrypt.checkpw(key.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    else:
        return _verify_pbkdf2(key, hashed)


def hash_sha256(value: str) -> str:
    """
    Simple SHA-256 hash for non-security checksums.
    
    NOT for passwords - use hash_password() for passwords.
    This is for data integrity checks only.
    
    Args:
        value: String to hash
    
    Returns:
        Hex digest string
    """
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def generate_random_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: Length in bytes (result will be hex, so 2x length)
    
    Returns:
        Hex string token
    """
    return secrets.token_hex(length)


def generate_api_key(prefix: str = "pred") -> str:
    """
    Generate a new API key with prefix.
    
    Args:
        prefix: Key prefix for identification
    
    Returns:
        API key string
    """
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.
    
    Args:
        a: First string
        b: Second string
    
    Returns:
        True if strings are equal
    """
    return secrets.compare_digest(a, b)
