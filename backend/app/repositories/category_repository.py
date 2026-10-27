"""Database access for categories and departments."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Category, Department


def list_active(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)).unique())


def get(db: Session, category_id: int) -> Category | None:
    return db.get(Category, category_id)


def list_all(db: Session) -> list[Category]:
    """Every category, including inactive ones (admin view)."""
    return list(db.scalars(select(Category).order_by(Category.name)).unique())


def get_by_name(db: Session, name: str) -> Category | None:
    return db.scalars(select(Category).where(func.lower(Category.name) == name.lower())).unique().first()


def get_by_slug(db: Session, slug: str) -> Category | None:
    return db.scalars(select(Category).where(Category.slug == slug)).unique().first()


def add(db: Session, category: Category) -> Category:
    db.add(category)
    db.flush()
    return category


# --- Departments ---------------------------------------------------------------

def list_departments(db: Session) -> list[Department]:
    return list(db.scalars(select(Department).order_by(Department.name)))


def get_department(db: Session, department_id: int) -> Department | None:
    return db.get(Department, department_id)


def get_department_by_name(db: Session, name: str) -> Department | None:
    return db.scalar(select(Department).where(func.lower(Department.name) == name.lower()))


def add_department(db: Session, department: Department) -> Department:
    db.add(department)
    db.flush()
    return department


def count_active_categories(db: Session, department_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Category).where(
            Category.department_id == department_id, Category.is_active.is_(True)
        )
    ) or 0
