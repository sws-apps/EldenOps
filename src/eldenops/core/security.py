"""Security utilities for encryption and JWT handling."""

from __future__ import annotations

import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional,  Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from jose import JWTError, jwt

from eldenops.config.settings import settings
from eldenops.core.exceptions import AuthenticationError


def derive_key(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """Derive an encryption key from a password."""
    if salt is None:
        salt = secrets.token_bytes(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


class Encryptor:
    """Handles encryption/decryption of sensitive data like API keys."""

    def __init__(self, key: Optional[str] = None) -> None:
        """Initialize with encryption key."""
        encryption_key = key or settings.encryption_key.get_secret_value()
        # Derive a proper Fernet key from the provided key
        derived_key, _ = derive_key(encryption_key, salt=b"eldenops-salt-v1")
        self._fernet = Fernet(derived_key)

    def encrypt(self, data: str) -> str:
        """Encrypt a string and return base64 encoded result."""
        encrypted = self._fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded encrypted data."""
        decoded = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted = self._fernet.decrypt(decoded)
        return decrypted.decode()


# Global encryptor instance
_encryptor: Optional[Encryptor] = None


def get_encryptor() -> Encryptor:
    """Get or create the global encryptor."""
    global _encryptor
    if _encryptor is None:
        _encryptor = Encryptor()
    return _encryptor


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    return get_encryptor().encrypt(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt a stored API key."""
    return get_encryptor().decrypt(encrypted_key)


# JWT Token handling
def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(days=settings.jwt_refresh_token_expire_days)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {e}") from e


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify an access token and return payload."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    """Verify a refresh token and return payload."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")
    return payload


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix) - only store the prefix for identification
    """
    key = secrets.token_urlsafe(32)
    prefix = key[:8]
    return key, prefix
