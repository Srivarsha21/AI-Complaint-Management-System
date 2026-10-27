"""Database access for revoked JWTs and password-reset tokens."""

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.auth_token import PasswordResetToken, RevokedToken


def revoke(db: Session, jti: str, expires_at: datetime) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(pg_insert(RevokedToken).values(jti=jti, expires_at=expires_at).on_conflict_do_nothing())
    elif db.get(RevokedToken, jti) is None:
        db.add(RevokedToken(jti=jti, expires_at=expires_at))


def is_revoked(db: Session, jti: str) -> bool:
    return db.get(RevokedToken, jti) is not None


def purge_expired_revocations(db: Session) -> None:
    """Expired tokens are rejected anyway, so their revocation rows can go."""
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(UTC)))


def create_reset_token(db: Session, *, user_id: int, token_hash: str, expires_at: datetime) -> PasswordResetToken:
    token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(token)
    db.flush()
    return token


def get_reset_token_by_hash(db: Session, token_hash: str) -> PasswordResetToken | None:
    return db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))


def invalidate_reset_tokens_for_user(db: Session, user_id: int) -> None:
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
