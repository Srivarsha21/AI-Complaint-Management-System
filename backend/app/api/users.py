"""Endpoints for the signed-in user's own account."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import client_ip, rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenPair
from app.schemas.user import PasswordChange, ProfileUpdate, UserOut
from app.services import auth_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return UserOut.model_validate(user_service.update_profile(db, user=user, full_name=body.full_name))


@router.post("/me/change-password", response_model=TokenPair, dependencies=[Depends(rate_limit("change-password"))])
def change_password(
    body: PasswordChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenPair:
    """Changes the password and returns fresh tokens; all older sessions are signed out."""
    return auth_service.change_password(
        db,
        user=user,
        current_password=body.current_password,
        new_password=body.new_password,
        ip_address=client_ip(request),
    )
