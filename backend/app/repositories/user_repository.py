"""Database access for users."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def create(db: Session, *, full_name: str, email: str, hashed_password: str, role: UserRole = UserRole.USER) -> User:
    user = User(full_name=full_name, email=email.lower(), hashed_password=hashed_password, role=role)
    db.add(user)
    db.flush()
    return user


def list_users(
    db: Session, *, search: str | None, role: UserRole | None, limit: int, offset: int
) -> tuple[list[User], int]:
    query = select(User)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    if role:
        query = query.where(User.role == role)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(User.created_at.desc(), User.id.desc()).limit(limit).offset(offset)).all()
    return list(items), total


def list_active_staff(db: Session, department_id: int) -> list[User]:
    """Active staff members of a department, e.g. candidates for assignment."""
    return list(
        db.scalars(
            select(User)
            .where(User.role == UserRole.STAFF, User.department_id == department_id, User.is_active.is_(True))
            .order_by(User.full_name)
        ).unique()
    )
