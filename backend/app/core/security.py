"""Password hashing, JWT creation/validation and reset-token helpers."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

TokenType = Literal["access", "refresh"]

# Argon2id with pwdlib's recommended parameters.
_password_hash = PasswordHash.recommended()
# Used to keep login timing similar whether or not the email exists.
_DUMMY_HASH = _password_hash.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


def burn_password_check(password: str) -> None:
    """Spend the same work as a real check when the user does not exist."""
    _password_hash.verify(password, _DUMMY_HASH)


@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: str
    expires_at: datetime


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    token_type: TokenType
    jti: str
    issued_at: float
    expires_at: datetime


class InvalidTokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


def create_token(user_id: int, token_type: TokenType) -> IssuedToken:
    settings = get_settings()
    now = datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_expire_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_expire_days)
    )
    expires_at = now + lifetime
    jti = uuid.uuid4().hex
    claims = {
        "sub": str(user_id),
        "type": token_type,
        "jti": jti,
        # Sub-second precision so "issued before password change" checks are exact.
        "iat": now.timestamp(),
        "exp": expires_at,
    }
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return IssuedToken(token=token, jti=jti, expires_at=expires_at)


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "jti", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if claims.get("type") != expected_type:
        raise InvalidTokenError("wrong token type")
    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("invalid subject") from exc

    return TokenPayload(
        user_id=user_id,
        token_type=expected_type,
        jti=str(claims["jti"]),
        issued_at=float(claims["iat"]),
        expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )


def generate_reset_token() -> tuple[str, str]:
    """Return (raw token for the email link, SHA-256 hash to store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_reset_token(raw)


def hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
