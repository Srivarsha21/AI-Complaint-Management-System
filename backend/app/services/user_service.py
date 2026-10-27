"""Profile management and administrator user management."""

from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, NotFoundError
from app.models.user import User, UserRole
from app.repositories import audit_repository, category_repository, user_repository
from app.schemas.user import AdminUserUpdate


def update_profile(db: Session, *, user: User, full_name: str) -> User:
    user.full_name = full_name
    db.commit()
    db.refresh(user)
    return user


def admin_update_user(
    db: Session, *, actor: User, user_id: int, changes: AdminUserUpdate, ip_address: str | None
) -> User:
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        raise NotFoundError("User not found.")
    if target.id == actor.id:
        # Prevents an admin from locking themselves out. Because the acting admin
        # can never demote or disable themselves, at least one active admin always remains.
        raise BadRequestError("You cannot change your own role or status.")

    before = {"role": target.role.value, "is_active": target.is_active, "department_id": target.department_id}
    new_role = changes.role if changes.role is not None else target.role
    if new_role == UserRole.STAFF:
        # Staff must belong to a department; keep the current one unless a new one is given.
        department_id = changes.department_id if changes.department_id is not None else target.department_id
        if department_id is None:
            raise BadRequestError("Staff members must be assigned to a department.")
        if department_id != target.department_id:
            department = category_repository.get_department(db, department_id)
            if department is None or not department.is_active:
                raise BadRequestError("Please choose an active department.")
    else:
        department_id = None  # only staff belong to a department

    target.role = new_role
    target.department_id = department_id
    if changes.is_active is not None:
        target.is_active = changes.is_active
    after = {"role": target.role.value, "is_active": target.is_active, "department_id": target.department_id}

    if before == after:
        return target

    audit_repository.record(
        db,
        actor_id=actor.id,
        action="admin.user_updated",
        target_type="user",
        target_id=target.id,
        details={"before": before, "after": after},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(target)
    return target


def ensure_admin(db: Session, *, email: str, full_name: str, hashed_password: str) -> tuple[User, bool]:
    """Create an admin, or promote an existing account. Returns (user, created)."""
    existing = user_repository.get_by_email(db, email)
    if existing:
        existing.role = UserRole.ADMIN
        existing.department_id = None
        existing.is_active = True
        db.commit()
        return existing, False
    user = user_repository.create(
        db, full_name=full_name, email=email, hashed_password=hashed_password, role=UserRole.ADMIN
    )
    db.commit()
    return user, True
