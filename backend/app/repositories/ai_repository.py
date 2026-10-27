"""Database access for AI predictions and duplicate-candidate lookups (module 5)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_prediction import ComplaintAIPrediction
from app.models.complaint import Complaint, ComplaintStatus
from app.models.department import Category


def get_active_category_by_slug(db: Session, slug: str) -> Category | None:
    return db.scalar(select(Category).where(Category.slug == slug, Category.is_active.is_(True)))


def get_prediction(db: Session, complaint_id: int) -> ComplaintAIPrediction | None:
    return db.scalar(select(ComplaintAIPrediction).where(ComplaintAIPrediction.complaint_id == complaint_id))


def add_prediction(db: Session, prediction: ComplaintAIPrediction) -> ComplaintAIPrediction:
    db.add(prediction)
    db.flush()
    return prediction


def find_duplicate_candidates(
    db: Session, *, category_id: int, since: datetime, exclude_id: int | None = None, limit: int = 300
) -> list[Complaint]:
    """Not-closed complaints in one category filed since `since`, newest first."""
    query = select(Complaint).where(
        Complaint.category_id == category_id,
        Complaint.status != ComplaintStatus.CLOSED,
        Complaint.created_at >= since,
    )
    if exclude_id is not None:
        query = query.where(Complaint.id != exclude_id)
    return list(db.scalars(query.order_by(Complaint.created_at.desc()).limit(limit)).unique())
