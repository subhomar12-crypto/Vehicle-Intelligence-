"""
AES-256-GCM field-level encryption utility.

Provides symmetric encryption for sensitive database fields (VIN, phone number, etc.)
using the ``cryptography`` library's AES-256-GCM implementation.

Usage
-----
    from predict.core.security.encryption import encrypt_field, decrypt_field

    # Encrypt before storing
    stored = encrypt_field("VF1RFB00648591234")

    # Decrypt after reading
    plain = decrypt_field(stored)

Configuration
-------------
Set ``FIELD_ENCRYPTION_KEY`` in the .env file to a URL-safe base64-encoded 32-byte key.

Generate a new key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # or for a raw 32-byte key:
    python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

If the key is absent at startup, ``RuntimeError`` is raised immediately — no silent fallbacks.
"""

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key loading — fail fast at import time if key is misconfigured
# ---------------------------------------------------------------------------

_ENCRYPTION_KEY: Optional[bytes] = None


def _load_key() -> bytes:
    """Load and validate the encryption key from the environment.

    Returns a 32-byte key suitable for AES-256.

    Raises
    ------
    RuntimeError
        If the key is not set or cannot be decoded.
    """
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is not None:
        return _ENCRYPTION_KEY

    raw = os.environ.get("FIELD_ENCRYPTION_KEY", "")
    if not raw:
        # Try loading from the Secrets/pydantic-settings .env loader
        try:
            from predict.core.security.secrets_loader import get_secrets
            secrets = get_secrets()
            raw = getattr(secrets, "FIELD_ENCRYPTION_KEY", "")
        except Exception:
            pass

    if not raw:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not configured. "
            "Generate one with: python -c \"import secrets, base64; "
            "print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\" "
            "and add it to your .env file."
        )

    try:
        key_bytes = base64.urlsafe_b64decode(raw + "==")  # tolerate missing padding
    except Exception as exc:
        raise RuntimeError(
            f"FIELD_ENCRYPTION_KEY is not valid base64: {exc}"
        ) from exc

    if len(key_bytes) != 32:
        raise RuntimeError(
            f"FIELD_ENCRYPTION_KEY must decode to exactly 32 bytes for AES-256 "
            f"(got {len(key_bytes)} bytes). Re-generate the key."
        )

    _ENCRYPTION_KEY = key_bytes
    logger.debug("Field encryption key loaded successfully.")
    return _ENCRYPTION_KEY


# ---------------------------------------------------------------------------
# Core encrypt / decrypt
# ---------------------------------------------------------------------------

def encrypt_field(plaintext: str) -> str:
    """Encrypt a plaintext string using AES-256-GCM.

    A fresh 12-byte nonce is generated for every call (GCM recommendation).
    The output is ``base64url(nonce || ciphertext || tag)`` — a single opaque
    string suitable for storing in a TEXT database column.

    Args:
        plaintext: The sensitive value to protect.

    Returns:
        A base64url-encoded string containing the nonce, ciphertext, and
        authentication tag.

    Raises:
        RuntimeError: If the encryption key is not configured.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os

    key = _load_key()
    nonce = os.urandom(12)          # 96-bit nonce — GCM recommendation
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Layout: nonce (12 bytes) | ciphertext | 16-byte GCM tag (appended by library)
    blob = nonce + ciphertext_with_tag
    return base64.urlsafe_b64encode(blob).decode("ascii")


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a value produced by :func:`encrypt_field`.

    Args:
        ciphertext: The base64url-encoded blob returned by :func:`encrypt_field`.

    Returns:
        The original plaintext string.

    Raises:
        RuntimeError: If the key is not configured or decryption fails (wrong key,
            tampered data, etc.).
        ValueError: If the ciphertext is malformed.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag

    key = _load_key()

    try:
        blob = base64.urlsafe_b64decode(ciphertext + "==")
    except Exception as exc:
        raise ValueError(f"Ciphertext is not valid base64: {exc}") from exc

    if len(blob) < 12 + 16:  # nonce (12) + minimum 0-byte plaintext + tag (16)
        raise ValueError("Ciphertext blob is too short to be valid.")

    nonce = blob[:12]
    ciphertext_with_tag = blob[12:]

    aesgcm = AESGCM(key)
    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except InvalidTag as exc:
        raise RuntimeError(
            "Decryption failed — data may be corrupt or encrypted with a different key."
        ) from exc

    return plaintext_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
# Searchable hash (for indexed lookups)
# ---------------------------------------------------------------------------

def hash_field(value: str) -> str:
    """Produce a stable HMAC-SHA256 hash of a value for indexed equality searches.

    Because AES-GCM ciphertext is non-deterministic (fresh nonce each time),
    you cannot query ``WHERE vin_encrypted = ?``. Store this hash alongside the
    encrypted value to enable exact-match lookups without exposing the plaintext.

    Args:
        value: The plaintext value to hash (normalised to uppercase before hashing).

    Returns:
        A hex-encoded HMAC-SHA256 digest (64 characters).
    """
    import hmac
    import hashlib

    key = _load_key()
    normalised = value.strip().upper()
    digest = hmac.new(key, normalised.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest
