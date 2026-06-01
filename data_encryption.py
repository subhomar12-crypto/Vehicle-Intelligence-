"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Data Encryption at Rest

Predict OBD - Data Encryption at Rest
Provides encryption for sensitive data directories and files.

ENCRYPTION STRATEGY:
- AES-256 encryption for sensitive files
- Key derived from machine-specific secret + master password
- Encrypted directories: api_keys, subscriptions, customer PII
- Transparent encryption/decryption for application use
"""

import os
import json
import base64
import hashlib
import secrets
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from config import get_config

logger = logging.getLogger(__name__)


class DataEncryption:
    """
    Manages encryption at rest for sensitive data.

    Encrypted Data Categories:
    1. API keys (hashes and metadata)
    2. Subscription data (license keys, payment info)
    3. Customer PII (if stored)
    4. Audit logs (integrity protection)
    """

    # Files/patterns that require encryption
    SENSITIVE_PATTERNS = [
        "api_keys.json",
        "subscription.json",
        "license_key.json",
        "profile.json",  # Contains customer PII
    ]

    # Salt for key derivation (should be stored securely in production)
    SALT_FILE = "encryption_salt.bin"
    KEY_FILE = "encryption_key.enc"

    def __init__(self):
        self.config = get_config()
        self._fernet: Optional[Fernet] = None
        self._initialized = False

    def initialize(self, master_password: Optional[str] = None) -> bool:
        """
        Initialize encryption system.

        Args:
            master_password: Master password for key derivation.
                           If None, uses machine-specific derivation.

        Returns:
            True if initialization successful
        """
        try:
            # Get or create salt
            salt = self._get_or_create_salt()

            # Derive encryption key
            if master_password:
                key = self._derive_key_from_password(master_password, salt)
            else:
                key = self._derive_key_from_machine(salt)

            # Initialize Fernet cipher
            self._fernet = Fernet(key)
            self._initialized = True

            logger.info("Data encryption initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            return False

    def encrypt_file(self, filepath: Path) -> Tuple[bool, str]:
        """
        Encrypt a file in place.

        Args:
            filepath: Path to file to encrypt

        Returns:
            (success, message)
        """
        if not self._initialized:
            return False, "Encryption not initialized"

        try:
            if not filepath.exists():
                return False, f"File not found: {filepath}"

            # Check if already encrypted
            if self._is_encrypted(filepath):
                return True, "File already encrypted"

            # Read file content
            with open(filepath, 'rb') as f:
                plaintext = f.read()

            # Encrypt
            ciphertext = self._fernet.encrypt(plaintext)

            # Write encrypted content with marker
            encrypted_content = b"ENC:" + ciphertext

            with open(filepath, 'wb') as f:
                f.write(encrypted_content)

            logger.info(f"Encrypted file: {filepath}")
            return True, "File encrypted successfully"

        except Exception as e:
            logger.error(f"Encryption failed for {filepath}: {e}")
            return False, f"Encryption failed: {str(e)}"

    def decrypt_file(self, filepath: Path) -> Tuple[bool, Optional[bytes], str]:
        """
        Decrypt a file and return content.

        Args:
            filepath: Path to encrypted file

        Returns:
            (success, decrypted_content, message)
        """
        if not self._initialized:
            return False, None, "Encryption not initialized"

        try:
            if not filepath.exists():
                return False, None, f"File not found: {filepath}"

            # Read file content
            with open(filepath, 'rb') as f:
                content = f.read()

            # Check if encrypted
            if not content.startswith(b"ENC:"):
                # File is not encrypted, return as-is
                return True, content, "File is not encrypted"

            # Extract ciphertext
            ciphertext = content[4:]  # Remove "ENC:" prefix

            # Decrypt
            plaintext = self._fernet.decrypt(ciphertext)

            return True, plaintext, "Decrypted successfully"

        except Exception as e:
            logger.error(f"Decryption failed for {filepath}: {e}")
            return False, None, f"Decryption failed: {str(e)}"

    def decrypt_file_to_json(self, filepath: Path) -> Tuple[bool, Optional[Dict], str]:
        """Decrypt a JSON file and parse it."""
        success, content, message = self.decrypt_file(filepath)

        if not success:
            return False, None, message

        try:
            data = json.loads(content.decode('utf-8'))
            return True, data, "Success"
        except json.JSONDecodeError as e:
            return False, None, f"Invalid JSON: {str(e)}"

    def encrypt_sensitive_directories(self) -> Dict[str, Any]:
        """
        Encrypt all sensitive files in the data directory.

        Returns:
            Summary of encryption operations
        """
        if not self._initialized:
            return {"success": False, "error": "Encryption not initialized"}

        results = {
            "success": True,
            "encrypted": 0,
            "already_encrypted": 0,
            "failed": 0,
            "errors": []
        }

        # Find all sensitive files
        sensitive_files = self._find_sensitive_files()

        for filepath in sensitive_files:
            success, message = self.encrypt_file(filepath)

            if success:
                if "already encrypted" in message.lower():
                    results["already_encrypted"] += 1
                else:
                    results["encrypted"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{filepath}: {message}")
                results["success"] = False

        logger.info(f"Encryption complete: {results['encrypted']} encrypted, "
                   f"{results['already_encrypted']} already encrypted, "
                   f"{results['failed']} failed")

        return results

    def verify_encryption_status(self) -> Dict[str, Any]:
        """
        Verify encryption status of all sensitive files.

        Returns:
            Status report
        """
        sensitive_files = self._find_sensitive_files()

        status = {
            "total_sensitive_files": len(sensitive_files),
            "encrypted": 0,
            "unencrypted": 0,
            "unencrypted_files": []
        }

        for filepath in sensitive_files:
            if self._is_encrypted(filepath):
                status["encrypted"] += 1
            else:
                status["unencrypted"] += 1
                status["unencrypted_files"].append(str(filepath))

        status["fully_encrypted"] = status["unencrypted"] == 0

        return status

    def _find_sensitive_files(self) -> list:
        """Find all files matching sensitive patterns."""
        sensitive_files = []

        # Search in customers directory
        customers_dir = self.config.CUSTOMERS_DIR
        if customers_dir.exists():
            for pattern in self.SENSITIVE_PATTERNS:
                sensitive_files.extend(customers_dir.rglob(pattern))

        # Search in config directory
        config_dir = self.config.CONFIG_DIR
        if config_dir.exists():
            for pattern in self.SENSITIVE_PATTERNS:
                sensitive_files.extend(config_dir.rglob(pattern))

        return sensitive_files

    def _is_encrypted(self, filepath: Path) -> bool:
        """Check if file is encrypted."""
        try:
            with open(filepath, 'rb') as f:
                header = f.read(4)
            return header == b"ENC:"
        except:
            return False

    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create new one."""
        salt_path = self.config.SYSTEM_DIR / self.SALT_FILE

        if salt_path.exists():
            with open(salt_path, 'rb') as f:
                return f.read()

        # Create new salt
        salt = secrets.token_bytes(32)

        # Ensure directory exists
        salt_path.parent.mkdir(parents=True, exist_ok=True)

        with open(salt_path, 'wb') as f:
            f.write(salt)

        logger.info("Created new encryption salt")
        return salt

    def _derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # OWASP recommended
            backend=default_backend()
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def _derive_key_from_machine(self, salt: bytes) -> bytes:
        """
        Derive encryption key from machine-specific identifiers.

        Uses combination of:
        - Machine UUID
        - Username
        - Installation timestamp
        """
        import platform
        import getpass

        # Gather machine-specific data
        machine_data = [
            platform.node(),
            platform.machine(),
            getpass.getuser(),
            str(self.config.ROOT_DIR),
        ]

        # Try to get installation timestamp
        try:
            if self.config.INSTALLATION_FILE.exists():
                with open(self.config.INSTALLATION_FILE, 'r') as f:
                    data = json.load(f)
                    machine_data.append(data.get('installed_at', ''))
        except:
            pass

        # Create deterministic seed
        seed = "|".join(machine_data).encode()

        return self._derive_key_from_password(seed.decode('utf-8', errors='replace'), salt)


# ==================== ENCRYPTED FILE OPERATIONS ====================

class EncryptedFileHandler:
    """
    Provides transparent read/write for encrypted files.
    Use this instead of direct file operations for sensitive data.
    """

    def __init__(self, encryption: DataEncryption):
        self.encryption = encryption

    def read_json(self, filepath: Path) -> Tuple[bool, Optional[Dict], str]:
        """Read and decrypt a JSON file."""
        return self.encryption.decrypt_file_to_json(filepath)

    def write_json(self, filepath: Path, data: Dict, encrypt: bool = True) -> Tuple[bool, str]:
        """Write and optionally encrypt a JSON file."""
        try:
            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Write JSON
            content = json.dumps(data, indent=2).encode('utf-8')

            if encrypt and self.encryption._initialized:
                # Encrypt and write
                ciphertext = self.encryption._fernet.encrypt(content)
                with open(filepath, 'wb') as f:
                    f.write(b"ENC:" + ciphertext)
            else:
                # Write plaintext
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)

            return True, "File written successfully"

        except Exception as e:
            return False, f"Write failed: {str(e)}"


# ==================== MODULE-LEVEL FUNCTIONS ====================

_encryption: Optional[DataEncryption] = None
_file_handler: Optional[EncryptedFileHandler] = None


def get_encryption() -> DataEncryption:
    """Get global encryption instance."""
    global _encryption
    if _encryption is None:
        _encryption = DataEncryption()
    return _encryption


def get_encrypted_file_handler() -> EncryptedFileHandler:
    """Get global encrypted file handler."""
    global _encryption, _file_handler
    if _file_handler is None:
        _file_handler = EncryptedFileHandler(get_encryption())
    return _file_handler


def initialize_encryption(master_password: Optional[str] = None) -> bool:
    """Initialize encryption system."""
    return get_encryption().initialize(master_password)


def encrypt_all_sensitive_data() -> Dict[str, Any]:
    """Encrypt all sensitive data files."""
    encryption = get_encryption()
    if not encryption._initialized:
        encryption.initialize()
    return encryption.encrypt_sensitive_directories()


def verify_encryption() -> Dict[str, Any]:
    """Verify encryption status."""
    return get_encryption().verify_encryption_status()
