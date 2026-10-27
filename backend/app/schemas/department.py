"""Department and category management schemas (admin)."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

from app.schemas.complaint import DepartmentBrief


def _clean_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) < 2:
        raise ValueError("Name must be at least 2 characters")
    return cleaned


def _check_slug(value: str) -> str:
    cleaned = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", cleaned):
        raise ValueError("Slug may contain only lowercase letters, digits and single hyphens")
    return cleaned


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value.strip() if isinstance(value, str) else value


Name = Annotated[str, Field(max_length=120), AfterValidator(_clean_name)]
Slug = Annotated[str, Field(max_length=80), AfterValidator(_check_slug)]
Description = Annotated[Annotated[str, Field(max_length=1000)] | None, BeforeValidator(_blank_to_none)]
ContactEmail = Annotated[
    EmailStr | None, BeforeValidator(_blank_to_none), AfterValidator(lambda v: v.lower() if v else v)
]


# --- Departments -----------------------------------------------------------------

class DepartmentCreate(BaseModel):
    name: Name
    description: Description = None
    contact_email: ContactEmail = None
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    name: Name | None = None
    description: Description = None
    contact_email: ContactEmail = None
    is_active: bool | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    contact_email: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Categories --------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: Name
    slug: Slug
    description: Description = None
    department_id: int = Field(gt=0)
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Name | None = None
    slug: Slug | None = None
    description: Description = None
    department_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class CategoryAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    is_active: bool
    department: DepartmentBrief
    created_at: datetime
    updated_at: datetime
