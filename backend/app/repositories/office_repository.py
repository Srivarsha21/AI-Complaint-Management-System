"""Database access for verified offices and complaint channels."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.department import Category
from app.models.office import ALL_CATEGORIES, Office


def list_active(db: Session, category_slug: str | None = None) -> list[Office]:
    """Active records serving `category_slug` (plus those marked for all categories)."""
    query = select(Office).where(Office.is_active.is_(True))
    if category_slug:
        query = query.where(
            or_(Office.category_slugs.contains([category_slug]), Office.category_slugs.contains([ALL_CATEGORIES]))
        )
    return list(db.scalars(query.order_by(Office.organisation, Office.name)))


def get_by_identity(db: Session, name: str, organisation: str) -> Office | None:
    return db.scalar(select(Office).where(Office.name == name, Office.organisation == organisation))


def add(db: Session, office: Office) -> Office:
    db.add(office)
    return office


def active_category_by_slug(db: Session, slug: str) -> Category | None:
    return db.scalar(select(Category).where(Category.slug == slug, Category.is_active.is_(True)))


def active_category_slugs(db: Session) -> dict[str, Category]:
    return {c.slug: c for c in db.scalars(select(Category).where(Category.is_active.is_(True))).unique()}
