"""Shared FastAPI dependencies: current user and role checks."""

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import TokenPayload
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services import auth_service

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    token: TokenPayload


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Not authenticated.")
    user, payload = auth_service.resolve_token_user(db, credentials.credentials, "access")
    return AuthContext(user=user, token=payload)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise PermissionDeniedError("Administrator access required.")
    return user
