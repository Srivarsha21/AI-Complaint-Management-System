"""User-facing request/response schemas."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole
from app.schemas.complaint import DepartmentBrief

PASSWORD_MIN_LENGTH = 8


def _check_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one number")
    return value


def _clean_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) < 2:
        raise ValueError("Full name must be at least 2 characters")
    return cleaned


# Max length guards against oversized inputs before hashing.
Password = Annotated[str, Field(max_length=128), AfterValidator(_check_password)]
FullName = Annotated[str, Field(max_length=120), AfterValidator(_clean_name)]
NormalisedEmail = Annotated[EmailStr, AfterValidator(lambda v: v.lower())]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    # Only staff belong to a department.
    department: DepartmentBrief | None = None


class ProfileUpdate(BaseModel):
    full_name: FullName


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: Password


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    # Required when the resulting role is staff; cleared for every other role.
    department_id: int | None = Field(default=None, gt=0)


class UserList(BaseModel):
    items: list[UserOut]
    total: int
