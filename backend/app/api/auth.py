"""Authentication endpoints."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_auth_context
from app.core.config import get_settings
from app.core.rate_limit import client_ip, rate_limit
from app.db.session import get_db
from app.schemas.auth import (
    AuthConfig,
    AuthResponse,
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
)
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register"))],
)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> UserOut:
    user = auth_service.register(db, full_name=body.full_name, email=body.email, password=body.password)
    return UserOut.model_validate(user)


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(rate_limit("login"))])
def login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    return auth_service.login(db, email=body.email, password=body.password)


@router.get("/config", response_model=AuthConfig)
def auth_config() -> AuthConfig:
    """Public sign-in options for the frontend (the Google client ID is public by design)."""
    return AuthConfig(google_client_id=get_settings().google_client_id or None)


@router.post("/google", response_model=AuthResponse, dependencies=[Depends(rate_limit("google"))])
def login_with_google(body: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    """Sign in or sign up with a Google ID token from Google Identity Services."""
    return auth_service.login_with_google(db, credential=body.credential, ip_address=client_ip(request))


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(rate_limit("refresh"))])
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    return auth_service.refresh(db, refresh_token=body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: LogoutRequest,
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Response:
    auth_service.logout(db, user=context.user, access=context.token, refresh_token=body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot-password"))],
)
def forgot_password(body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)) -> MessageResponse:
    auth_service.request_password_reset(db, email=body.email, ip_address=client_ip(request))
    return MessageResponse(
        message="If an account exists for that email, a password reset link has been sent."
    )


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("reset-password"))],
)
def reset_password(body: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)) -> Response:
    auth_service.reset_password(db, token=body.token, new_password=body.new_password, ip_address=client_ip(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
