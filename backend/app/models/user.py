"""User accounts and roles."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.department import Department


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    # Department officer: manages complaints routed to their own department only.
    STAFF = "staff"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=UserRole.USER,
        nullable=False,
    )
    # Set only for staff; every other role has no department.
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Google account ID ("sub" claim) for users who sign in with Google.
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Tokens issued before this moment are rejected (password change/reset signs out everywhere).
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    department: Mapped["Department | None"] = relationship(lazy="joined")
