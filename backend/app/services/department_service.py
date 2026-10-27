"""Administrator management of departments and the category -> department mapping.

Complaints store their department at submission, so changing a category's
department only affects complaints filed afterwards.
"""

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.models.department import Category, Department
from app.models.user import User, UserRole
from app.repositories import audit_repository, category_repository, user_repository
from app.schemas.department import CategoryCreate, CategoryUpdate, DepartmentCreate, DepartmentUpdate

_DEPARTMENT_FIELDS = ("name", "description", "contact_email", "is_active")
_CATEGORY_FIELDS = ("name", "slug", "description", "department_id", "is_active")


def _snapshot(obj: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(obj, field) for field in fields}


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changed = [k for k in before if before[k] != after[k]]
    return {"before": {k: before[k] for k in changed}, "after": {k: after[k] for k in changed}}


def _commit(db: Session, conflict_message: str) -> None:
    # Safety net for races between the uniqueness check and the insert.
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(conflict_message) from exc


# --- Departments -----------------------------------------------------------------

def _get_department(db: Session, department_id: int) -> Department:
    department = category_repository.get_department(db, department_id)
    if department is None:
        raise NotFoundError("Department not found.")
    return department


def _ensure_unique_department_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    existing = category_repository.get_department_by_name(db, name)
    if existing is not None and existing.id != exclude_id:
        raise ConflictError(f"A department named '{name}' already exists.")


def create_department(db: Session, *, actor: User, data: DepartmentCreate, ip_address: str | None) -> Department:
    _ensure_unique_department_name(db, data.name)
    department = category_repository.add_department(db, Department(**data.model_dump()))
    audit_repository.record(
        db, actor_id=actor.id, action="admin.department_created", target_type="department",
        target_id=department.id, details={"after": _snapshot(department, _DEPARTMENT_FIELDS)}, ip_address=ip_address,
    )
    _commit(db, f"A department named '{data.name}' already exists.")
    db.refresh(department)
    return department


def update_department(
    db: Session, *, actor: User, department_id: int, changes: DepartmentUpdate, ip_address: str | None
) -> Department:
    department = _get_department(db, department_id)
    provided = changes.model_dump(exclude_unset=True)
    if provided.get("name") is None:
        provided.pop("name", None)
    if provided.get("is_active") is None:
        provided.pop("is_active", None)

    if "name" in provided:
        _ensure_unique_department_name(db, provided["name"], exclude_id=department.id)
    if provided.get("is_active") is False and department.is_active:
        active = category_repository.count_active_categories(db, department.id)
        if active:
            raise ConflictError(
                f"Cannot deactivate '{department.name}': {active} active "
                f"{'category is' if active == 1 else 'categories are'} still mapped to it. "
                "Move or deactivate those categories first."
            )

    before = _snapshot(department, _DEPARTMENT_FIELDS)
    for field, value in provided.items():
        setattr(department, field, value)
    after = _snapshot(department, _DEPARTMENT_FIELDS)
    if before == after:
        return department

    audit_repository.record(
        db, actor_id=actor.id, action="admin.department_updated", target_type="department",
        target_id=department.id, details=_diff(before, after), ip_address=ip_address,
    )
    _commit(db, "A department with this name already exists.")
    db.refresh(department)
    return department


def list_department_staff(db: Session, *, viewer: User, department_id: int) -> list[User]:
    """Assignment candidates. Admins may list any department, staff only their own."""
    if viewer.role == UserRole.STAFF:
        if viewer.department_id != department_id:
            raise PermissionDeniedError("You can only view staff of your own department.")
    elif viewer.role != UserRole.ADMIN:
        raise PermissionDeniedError("Staff access required.")
    _get_department(db, department_id)
    return user_repository.list_active_staff(db, department_id)


# --- Categories --------------------------------------------------------------------

def _get_category(db: Session, category_id: int) -> Category:
    category = category_repository.get(db, category_id)
    if category is None:
        raise NotFoundError("Category not found.")
    return category


def _ensure_unique_category(db: Session, *, name: str | None, slug: str | None, exclude_id: int | None = None) -> None:
    if name is not None:
        existing = category_repository.get_by_name(db, name)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError(f"A category named '{name}' already exists.")
    if slug is not None:
        existing = category_repository.get_by_slug(db, slug)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError(f"The slug '{slug}' is already in use.")


def _active_department(db: Session, department_id: int) -> Department:
    department = category_repository.get_department(db, department_id)
    if department is None:
        raise BadRequestError("Please choose a valid department.")
    if not department.is_active:
        raise BadRequestError(f"Department '{department.name}' is inactive. Activate it first.")
    return department


def create_category(db: Session, *, actor: User, data: CategoryCreate, ip_address: str | None) -> Category:
    _ensure_unique_category(db, name=data.name, slug=data.slug)
    _active_department(db, data.department_id)
    category = category_repository.add(db, Category(**data.model_dump()))
    audit_repository.record(
        db, actor_id=actor.id, action="admin.category_created", target_type="category",
        target_id=category.id, details={"after": _snapshot(category, _CATEGORY_FIELDS)}, ip_address=ip_address,
    )
    _commit(db, "A category with this name or slug already exists.")
    db.refresh(category)
    return category


def update_category(
    db: Session, *, actor: User, category_id: int, changes: CategoryUpdate, ip_address: str | None
) -> Category:
    category = _get_category(db, category_id)
    provided = changes.model_dump(exclude_unset=True)
    # Required columns cannot be cleared; an explicit null means "no change".
    for field in ("name", "slug", "department_id", "is_active"):
        if provided.get(field) is None:
            provided.pop(field, None)

    _ensure_unique_category(db, name=provided.get("name"), slug=provided.get("slug"), exclude_id=category.id)
    target_department_id = provided.get("department_id", category.department_id)
    will_be_active = provided.get("is_active", category.is_active)
    if will_be_active and (target_department_id != category.department_id or not category.is_active):
        # Active categories must route to an active department.
        _active_department(db, target_department_id)

    before = _snapshot(category, _CATEGORY_FIELDS)
    for field, value in provided.items():
        setattr(category, field, value)
    after = _snapshot(category, _CATEGORY_FIELDS)
    if before == after:
        return category

    audit_repository.record(
        db, actor_id=actor.id, action="admin.category_updated", target_type="category",
        target_id=category.id, details=_diff(before, after), ip_address=ip_address,
    )
    _commit(db, "A category with this name or slug already exists.")
    db.expire(category)  # reload the department relationship after a re-mapping
    db.refresh(category)
    return category
