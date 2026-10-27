"""Database access for complaint feedback and AI prediction reviews (module 11)."""

from sqlalchemy import Row, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.ai_prediction import ComplaintAIPrediction
from app.models.complaint import Complaint, PrioritySource
from app.models.feedback import ComplaintFeedback


def get_feedback(db: Session, complaint_id: int) -> ComplaintFeedback | None:
    return db.scalar(select(ComplaintFeedback).where(ComplaintFeedback.complaint_id == complaint_id))


def add_feedback(db: Session, feedback: ComplaintFeedback) -> ComplaintFeedback:
    db.add(feedback)
    db.flush()
    return feedback


def get_prediction(db: Session, prediction_id: int) -> ComplaintAIPrediction | None:
    return db.get(ComplaintAIPrediction, prediction_id)


def _flag_conditions():
    """A prediction needs human review when any disagreement signal is present."""
    return or_(
        and_(ComplaintAIPrediction.predicted_category_id.is_not(None),
             ComplaintAIPrediction.predicted_category_id != Complaint.category_id),
        ComplaintAIPrediction.user_accepted_category.is_(False),
        and_(Complaint.priority_source == PrioritySource.STAFF,
             ComplaintAIPrediction.predicted_priority.is_distinct_from(Complaint.priority)),
        ComplaintFeedback.ai_helpful.is_(False),
    )


def list_reviews(
    db: Session, *, review_status: str | None, flagged_only: bool, limit: int, offset: int
) -> tuple[list[Row], int]:
    query = (
        select(ComplaintAIPrediction, Complaint, ComplaintFeedback)
        .join(Complaint, Complaint.id == ComplaintAIPrediction.complaint_id)
        .outerjoin(ComplaintFeedback, ComplaintFeedback.complaint_id == Complaint.id)
    )
    if review_status:
        query = query.where(ComplaintAIPrediction.review_status == review_status)
    if flagged_only:
        query = query.where(_flag_conditions())
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(query.order_by(Complaint.created_at.desc()).limit(limit).offset(offset)).unique().all()
    return list(rows), total


def reviewed_incorrect(db: Session) -> list[Row]:
    return list(
        db.execute(
            select(ComplaintAIPrediction, Complaint)
            .join(Complaint, Complaint.id == ComplaintAIPrediction.complaint_id)
            .where(ComplaintAIPrediction.review_status == "incorrect")
            .order_by(ComplaintAIPrediction.reviewed_at)
        ).unique().all()
    )


def quality_counts(db: Session) -> dict:
    p, c = ComplaintAIPrediction, Complaint
    counts = db.execute(
        select(
            func.count(p.id),
            func.count(p.predicted_category_id),
            func.count().filter(p.predicted_category_id == c.category_id),
            func.count(p.user_accepted_category),
            func.count().filter(p.user_accepted_category.is_(True)),
            func.count().filter(and_(c.priority_source == PrioritySource.STAFF,
                                     p.predicted_priority.is_distinct_from(c.priority))),
            func.count().filter(p.review_status != "unreviewed"),
            func.count().filter(p.review_status == "incorrect"),
        ).join(c, c.id == p.complaint_id)
    ).one()
    f = ComplaintFeedback
    feedback = db.execute(
        select(
            func.count(f.id),
            func.avg(f.rating),
            func.count().filter(f.resolved_satisfactorily.is_(True)),
            func.count(f.ai_helpful),
            func.count().filter(f.ai_helpful.is_(True)),
        )
    ).one()
    return {"predictions": counts, "feedback": feedback}
