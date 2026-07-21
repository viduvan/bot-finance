"""Security utilities: JWT, password hashing, TOTP 2FA, encryption.

Critical: Secrets are never logged. Approval tokens are one-time use.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pyotp
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.exceptions import AuthenticationError, TokenExpiredError

# ── Password Hashing ─────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Tokens ───────────────────────────────────────────────────


def create_access_token(
    user_id: str,
    role: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "jti": str(uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token (longer-lived)."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Raises:
        AuthenticationError: If token is invalid.
        TokenExpiredError: If token has expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        error_str = str(e).lower()
        if "expired" in error_str:
            raise TokenExpiredError("JWT token has expired") from e
        raise AuthenticationError(f"Invalid token: {e}") from e


# ── TOTP 2FA ─────────────────────────────────────────────────────


def generate_totp_secret() -> str:
    """Generate a new TOTP secret for 2FA setup."""
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    """Generate the provisioning URI for QR code scanning."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.mfa_issuer_name)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against the secret.

    Allows a window of ±1 time step (±30 seconds) for clock drift.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ── Approval Token ───────────────────────────────────────────────


def generate_approval_token() -> str:
    """Generate a cryptographically secure approval token."""
    return secrets.token_urlsafe(48)


def hash_approval_token(token: str) -> str:
    """Hash an approval token for storage (we never store raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Compute a deterministic hash of the proposal payload.

    Used to detect if a proposal was modified after approval.
    Changes to the proposal invalidate existing approval tokens.
    """
    # Sort keys for deterministic serialization
    import json

    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def sign_approval_context(
    proposal_id: str,
    token_id: str,
    payload_hash: str,
) -> str:
    """Create an HMAC signature for the approval context.

    This proves the approval is genuine and hasn't been tampered with.
    """
    message = f"{proposal_id}:{token_id}:{payload_hash}"
    return hmac.new(
        settings.approval_token_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_approval_signature(
    proposal_id: str,
    token_id: str,
    payload_hash: str,
    signature: str,
) -> bool:
    """Verify the HMAC signature of an approval context."""
    expected = sign_approval_context(proposal_id, token_id, payload_hash)
    return hmac.compare_digest(expected, signature)


# ── Encryption (for API keys at rest) ────────────────────────────

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create Fernet encryption instance."""
    global _fernet
    if _fernet is None:
        # Derive a valid Fernet key from the configured encryption key
        key_bytes = hashlib.sha256(settings.encryption_key.encode()).digest()
        import base64

        fernet_key = base64.urlsafe_b64encode(key_bytes)
        _fernet = Fernet(fernet_key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a sensitive value (e.g., API key) for database storage."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a stored sensitive value."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
