"""
JWT token creation and verification for Guardian authentication.
"""

import logging
import time
import base64
import hashlib
import hmac
from typing import Optional, Dict, Any

try:
    import jwt
    _has_jwt = True
except ImportError:
    _has_jwt = False

from predict.core.security.secrets_loader import Secrets

logger = logging.getLogger(__name__)


def _get_secret() -> str:
    """Get JWT secret from secrets.

    Raises RuntimeError if SECRET_KEY is not configured — never uses a hardcoded fallback.
    """
    try:
        secrets = Secrets()
        secret = secrets.SECRET_KEY
        if not secret or secret == "CHANGE_ME_GENERATE_A_RANDOM_KEY":
            raise RuntimeError(
                "SECRET_KEY is not configured. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return secret
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load SECRET_KEY from environment: {exc}. "
            "Ensure SECRET_KEY is set in your .env file."
        ) from exc


def _create_jwt_manual(
    payload: Dict[str, Any],
    secret: str,
) -> str:
    """
    Create JWT token manually without PyJWT library.
    
    This is a fallback implementation using HMAC-SHA256.
    """
    # Header
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(
        __import__('json').dumps(header).encode()
    ).decode().rstrip('=')
    
    # Payload
    payload_b64 = base64.urlsafe_b64encode(
        __import__('json').dumps(payload).encode()
    ).decode().rstrip('=')
    
    # Signature
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _verify_jwt_manual(
    token: str,
    secret: str,
) -> Optional[Dict[str, Any]]:
    """
    Verify JWT token manually without PyJWT library.
    
    Returns decoded payload or None if invalid.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature
        message = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip('=')
        
        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            return None
        
        # Decode payload
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        
        payload_json = base64.urlsafe_b64decode(payload_b64).decode()
        payload = __import__('json').loads(payload_json)
        
        # Check expiration
        if payload.get('exp', 0) < time.time():
            return None
        
        return payload
    
    except Exception as e:
        logger.debug(f"JWT verification failed: {e}")
        return None


def create_token(
    guardian_id: str,
    expires_hours: int = 1,
) -> str:
    """
    Create a JWT token for Guardian authentication.

    Default expiry is 1 hour (access token). Pass expires_hours=168 for a 7-day refresh token.

    Args:
        guardian_id: Guardian identifier
        expires_hours: Token expiration time in hours (default: 1 hour for access tokens)

    Returns:
        JWT token string
    """
    now = time.time()
    payload = {
        "sub": guardian_id,
        "iat": now,
        "exp": now + (expires_hours * 3600),
        "type": "guardian_auth",
    }
    
    secret = _get_secret()
    
    if _has_jwt:
        return jwt.encode(payload, secret, algorithm="HS256")
    else:
        return _create_jwt_manual(payload, secret)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload dict or None if invalid/expired
    """
    secret = _get_secret()
    
    if _has_jwt:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
    else:
        return _verify_jwt_manual(token, secret)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode a JWT token (raises on invalid).
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload dict
    
    Raises:
        ValueError: If token is invalid or expired
    """
    payload = verify_token(token)
    if payload is None:
        raise ValueError("Invalid or expired token")
    return payload


def get_token_expiry(token: str) -> Optional[float]:
    """
    Get token expiration timestamp.
    
    Args:
        token: JWT token string
    
    Returns:
        Expiration timestamp or None
    """
    try:
        payload = verify_token(token)
        if payload:
            return payload.get('exp')
    except Exception:
        pass
    return None


def is_token_expired(token: str) -> bool:
    """
    Check if a token is expired.
    
    Args:
        token: JWT token string
    
    Returns:
        True if expired or invalid
    """
    exp = get_token_expiry(token)
    if exp is None:
        return True
    return exp < time.time()


def refresh_token(
    token: str,
    expires_hours: int = 168,
) -> Optional[str]:
    """
    Refresh a valid token with new expiration.

    Default is 7 days (168 hours) for refresh tokens.

    Args:
        token: Existing valid token
        expires_hours: New expiration time in hours (default: 168 hours / 7 days)

    Returns:
        New token string or None if original invalid
    """
    payload = verify_token(token)
    if payload is None:
        return None
    
    # Get guardian_id from payload
    guardian_id = payload.get('sub')
    if not guardian_id:
        return None
    
    return create_token(guardian_id, expires_hours)
