"""Registration, login, token lifecycle and password recovery."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.core.errors import AuthenticationError, BadRequestError, ConflictError, PermissionDeniedError
from app.models.user import User
from app.repositories import audit_repository, token_repository, user_repository
from app.schemas.auth import AuthResponse, TokenPair
from app.schemas.user import UserOut
from app.services import email_service, google_auth

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Incorrect email or password."
INVALID_SESSION = "Your session is no longer valid. Please sign in again."


def _token_pair(user: User) -> TokenPair:
    settings = get_settings()
    access = security.create_token(user.id, "access")
    refresh = security.create_token(user.id, "refresh")
    return TokenPair(
        access_token=access.token,
        refresh_token=refresh.token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


def _issued_before_password_change(user: User, issued_at: float) -> bool:
    return user.password_changed_at is not None and issued_at < user.password_changed_at.timestamp()


def resolve_token_user(db: Session, token: str, token_type: security.TokenType) -> tuple[User, security.TokenPayload]:
    """Validate a token against signature, expiry, revocation and account state."""
    try:
        payload = security.decode_token(token, token_type)
    except security.InvalidTokenError as exc:
        raise AuthenticationError(INVALID_SESSION) from exc

    if token_repository.is_revoked(db, payload.jti):
        raise AuthenticationError(INVALID_SESSION)
    user = user_repository.get_by_id(db, payload.user_id)
    if user is None or _issued_before_password_change(user, payload.issued_at):
        raise AuthenticationError(INVALID_SESSION)
    if not user.is_active:
        raise PermissionDeniedError("This account has been disabled.")
    return user, payload


def register(db: Session, *, full_name: str, email: str, password: str) -> User:
    if user_repository.get_by_email(db, email):
        raise ConflictError("An account with this email already exists.")
    user = user_repository.create(
        db, full_name=full_name, email=email, hashed_password=security.hash_password(password)
    )
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent registration with the same email
        db.rollback()
        raise ConflictError("An account with this email already exists.") from exc
    db.refresh(user)
    return user


def login(db: Session, *, email: str, password: str) -> AuthResponse:
    user = user_repository.get_by_email(db, email)
    if user is None:
        security.burn_password_check(password)
        raise AuthenticationError(INVALID_CREDENTIALS)
    if not security.verify_password(password, user.hashed_password):
        raise AuthenticationError(INVALID_CREDENTIALS)
    if not user.is_active:
        raise PermissionDeniedError("This account has been disabled.")

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    pair = _token_pair(user)
    return AuthResponse(**pair.model_dump(), user=UserOut.model_validate(user))


def login_with_google(db: Session, *, credential: str, ip_address: str | None) -> AuthResponse:
    """Sign in (or sign up) with a verified Google ID token.

    - Known Google account -> that user.
    - Same verified email as an existing account -> link Google to it.
    - Otherwise -> create a new citizen account (no password; can set one via reset).
    """
    identity = google_auth.verify_credential(credential)
    if not identity.email_verified:
        raise AuthenticationError("Your Google email address is not verified.")

    user = db.scalar(select(User).where(User.google_sub == identity.sub))
    action = "auth.google_login"
    if user is None:
        user = user_repository.get_by_email(db, identity.email)
        if user is not None:
            user.google_sub = identity.sub
            action = "auth.google_linked"
        else:
            full_name = " ".join((identity.name or identity.email.split("@")[0]).split())[:120] or "Google user"
            user = user_repository.create(
                db,
                full_name=full_name,
                email=identity.email,
                # Random, never shown: the account has no usable password until the user sets one.
                hashed_password=security.hash_password(secrets.token_urlsafe(32)),
            )
            user.google_sub = identity.sub
            action = "auth.google_signup"
    if not user.is_active:
        raise PermissionDeniedError("This account has been disabled.")

    user.last_login_at = datetime.now(UTC)
    if action != "auth.google_login":
        audit_repository.record(db, actor_id=user.id, action=action, target_type="user", target_id=user.id, ip_address=ip_address)
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent first sign-in with the same Google account
        db.rollback()
        raise ConflictError("Please try signing in again.") from exc
    db.refresh(user)
    pair = _token_pair(user)
    return AuthResponse(**pair.model_dump(), user=UserOut.model_validate(user))


def refresh(db: Session, *, refresh_token: str) -> TokenPair:
    user, payload = resolve_token_user(db, refresh_token, "refresh")
    # Rotation: each refresh token works once.
    token_repository.revoke(db, payload.jti, payload.expires_at)
    db.commit()
    return _token_pair(user)


def logout(db: Session, *, user: User, access: security.TokenPayload, refresh_token: str | None) -> None:
    token_repository.revoke(db, access.jti, access.expires_at)
    if refresh_token:
        try:
            refresh_payload = security.decode_token(refresh_token, "refresh")
        except security.InvalidTokenError:
            refresh_payload = None
        if refresh_payload and refresh_payload.user_id == user.id:
            token_repository.revoke(db, refresh_payload.jti, refresh_payload.expires_at)
    token_repository.purge_expired_revocations(db)
    db.commit()


def request_password_reset(db: Session, *, email: str, ip_address: str | None) -> None:
    """Always behaves the same from the caller's view to avoid revealing accounts."""
    settings = get_settings()
    user = user_repository.get_by_email(db, email)
    if user is None or not user.is_active:
        return

    raw, token_hash = security.generate_reset_token()
    token_repository.invalidate_reset_tokens_for_user(db, user.id)
    token_repository.create_reset_token(
        db,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_expire_minutes),
    )
    audit_repository.record(
        db, actor_id=user.id, action="auth.password_reset_requested", target_type="user",
        target_id=user.id, ip_address=ip_address,
    )
    db.commit()

    # Token goes in the URL fragment so it is never sent to servers or logged in access logs.
    link = f"{settings.frontend_url.rstrip('/')}/reset-password#token={raw}"
    email_service.send_password_reset_email(user.email, user.full_name, link, settings.password_reset_expire_minutes)


def reset_password(db: Session, *, token: str, new_password: str, ip_address: str | None) -> None:
    record = token_repository.get_reset_token_by_hash(db, security.hash_reset_token(token))
    now = datetime.now(UTC)
    if record is None or record.used_at is not None or record.expires_at <= now:
        raise BadRequestError("This reset link is invalid or has expired. Please request a new one.")
    user = user_repository.get_by_id(db, record.user_id)
    if user is None or not user.is_active:
        raise BadRequestError("This reset link is invalid or has expired. Please request a new one.")

    user.hashed_password = security.hash_password(new_password)
    user.password_changed_at = now
    token_repository.invalidate_reset_tokens_for_user(db, user.id)
    audit_repository.record(
        db, actor_id=user.id, action="auth.password_reset", target_type="user", target_id=user.id, ip_address=ip_address
    )
    db.commit()


def change_password(
    db: Session, *, user: User, current_password: str, new_password: str, ip_address: str | None
) -> TokenPair:
    if not security.verify_password(current_password, user.hashed_password):
        raise BadRequestError("Current password is incorrect.")
    if current_password == new_password:
        raise BadRequestError("New password must be different from the current password.")

    user.hashed_password = security.hash_password(new_password)
    # Every token issued before now (other devices, this session) stops working.
    user.password_changed_at = datetime.now(UTC)
    audit_repository.record(
        db, actor_id=user.id, action="auth.password_changed", target_type="user", target_id=user.id, ip_address=ip_address
    )
    db.commit()
    db.refresh(user)
    return _token_pair(user)
