"""Citizen feedback and human review of AI predictions (module 11).

Reviews and feedback are stored for quality monitoring. They NEVER retrain the
models automatically: unverified user input must not change model behaviour.
Corrections marked "incorrect" by an administrator can be exported as CSV for a
deliberate, documented retraining run.
"""

import csv
import io
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.models.complaint import Complaint, ComplaintStatus, PrioritySource
from app.models.feedback import ComplaintFeedback
from app.models.user import User
from app.repositories import audit_repository, category_repository, feedback_repository
from app.schemas.complaint import CategoryBrief
from app.schemas.feedback import (
    AIReviewItem,
    AIReviewUpdate,
    FeedbackCreate,
    FeedbackOut,
    QualitySummary,
    ReviewComplaint,
)
from app.services import complaint_service

FEEDBACK_STATUSES = {ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED}


# --- Feedback ------------------------------------------------------------------------

def submit_feedback(db: Session, *, user: User, complaint_id: int, data: FeedbackCreate) -> FeedbackOut:
    complaint = complaint_service.get_for_user(db, user=user, complaint_id=complaint_id)
    if complaint.user_id != user.id:
        raise PermissionDeniedError("Only the person who filed the complaint can give feedback.")
    if complaint.status not in FEEDBACK_STATUSES:
        raise BadRequestError("Feedback can be given once the complaint is resolved.")
    if feedback_repository.get_feedback(db, complaint_id) is not None:
        raise ConflictError("Feedback has already been submitted for this complaint.")

    feedback = ComplaintFeedback(
        complaint_id=complaint_id,
        user_id=user.id,
        rating=data.rating,
        resolved_satisfactorily=data.resolved_satisfactorily,
        ai_helpful=data.ai_helpful,
        comment=(data.comment or "").strip() or None,
    )
    try:
        feedback_repository.add_feedback(db, feedback)
        db.commit()
    except IntegrityError as exc:  # concurrent double submit
        db.rollback()
        raise ConflictError("Feedback has already been submitted for this complaint.") from exc
    return FeedbackOut.model_validate(feedback)


def get_feedback(db: Session, *, user: User, complaint_id: int) -> FeedbackOut | None:
    complaint = complaint_service.get_for_user(db, user=user, complaint_id=complaint_id)  # authorization
    feedback = feedback_repository.get_feedback(db, complaint.id)
    return FeedbackOut.model_validate(feedback) if feedback else None


# --- AI review -------------------------------------------------------------------------

def _signals(prediction, complaint, feedback) -> list[str]:
    signals = []
    if prediction.predicted_category_id is not None and prediction.predicted_category_id != complaint.category_id:
        signals.append("category_changed")
    if prediction.user_accepted_category is False:
        signals.append("suggestion_rejected")
    if complaint.priority_source == PrioritySource.STAFF and prediction.predicted_priority != complaint.priority:
        signals.append("priority_overridden")
    if feedback is not None and feedback.ai_helpful is False:
        signals.append("ai_not_helpful")
    return signals


def _brief(category) -> CategoryBrief | None:
    return CategoryBrief.model_validate(category) if category is not None else None


def _item(prediction, complaint, feedback) -> AIReviewItem:
    return AIReviewItem(
        prediction_id=prediction.id,
        complaint=ReviewComplaint(
            id=complaint.id, reference_number=complaint.reference_number, subject=complaint.subject, status=complaint.status
        ),
        final_category=CategoryBrief.model_validate(complaint.category),
        predicted_category=_brief(prediction.predicted_category),
        category_confidence=prediction.category_confidence,
        user_accepted_category=prediction.user_accepted_category,
        predicted_priority=prediction.predicted_priority,
        final_priority=complaint.priority,
        priority_source=complaint.priority_source,
        signals=_signals(prediction, complaint, feedback),
        review_status=prediction.review_status,
        corrected_category=_brief(prediction.corrected_category),
        review_note=prediction.review_note,
        reviewed_at=prediction.reviewed_at,
        model_version=prediction.model_version,
    )


def list_reviews(db: Session, *, review_status: str | None, flagged_only: bool, limit: int, offset: int):
    rows, total = feedback_repository.list_reviews(
        db, review_status=review_status, flagged_only=flagged_only, limit=limit, offset=offset
    )
    return [_item(p, c, f) for p, c, f in rows], total


def review_prediction(db: Session, *, actor: User, prediction_id: int, data: AIReviewUpdate, ip_address: str | None) -> AIReviewItem:
    prediction = feedback_repository.get_prediction(db, prediction_id)
    if prediction is None:
        raise NotFoundError("Prediction not found.")
    if data.corrected_category_id is not None:
        if data.review_status != "incorrect":
            raise BadRequestError("A corrected category only applies to predictions marked incorrect.")
        if category_repository.get(db, data.corrected_category_id) is None:
            raise BadRequestError("Please choose a valid category.")

    prediction.review_status = data.review_status
    prediction.corrected_category_id = data.corrected_category_id
    prediction.review_note = (data.note or "").strip() or None
    prediction.reviewed_by_id = actor.id
    prediction.reviewed_at = datetime.now(UTC)
    audit_repository.record(
        db, actor_id=actor.id, action="ai.prediction_reviewed", target_type="complaint", target_id=prediction.complaint_id,
        details={"review_status": data.review_status, "corrected_category_id": data.corrected_category_id},
        ip_address=ip_address,
    )
    db.commit()
    db.expire_all()
    prediction = feedback_repository.get_prediction(db, prediction_id)
    complaint = db.get(Complaint, prediction.complaint_id)
    return _item(prediction, complaint, feedback_repository.get_feedback(db, complaint.id))


def export_corrections_csv(db: Session, *, actor: User, ip_address: str | None) -> str:
    """Reviewed-incorrect predictions with the corrected label, for manual retraining.

    Contains complaint text (subject and description) but no names, emails or IDs of people.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["reference_number", "text", "predicted_category", "corrected_category", "model_version", "reviewed_at"])
    rows = feedback_repository.reviewed_incorrect(db)
    for prediction, complaint in rows:
        corrected = prediction.corrected_category or complaint.category
        text = f"{complaint.subject}. {complaint.description}".replace("\n", " ")
        # Neutralise spreadsheet formula injection.
        if text[:1] in ("=", "+", "-", "@"):
            text = "'" + text
        writer.writerow([
            complaint.reference_number,
            text,
            prediction.predicted_category.slug if prediction.predicted_category else "",
            corrected.slug,
            prediction.model_version or "",
            prediction.reviewed_at.isoformat() if prediction.reviewed_at else "",
        ])
    audit_repository.record(
        db, actor_id=actor.id, action="ai.corrections_exported", target_type="ai_prediction", details={"rows": len(rows)},
        ip_address=ip_address,
    )
    db.commit()
    return buffer.getvalue()


def quality_summary(db: Session) -> QualitySummary:
    counts = feedback_repository.quality_counts(db)
    total, suggested, agreed, answered, accepted, overrides, reviewed, incorrect = counts["predictions"]
    fb_total, fb_avg, satisfied, ai_answered, ai_yes = counts["feedback"]

    def rate(part: int, whole: int) -> float | None:
        return round(part / whole, 3) if whole else None

    return QualitySummary(
        predictions=total,
        with_category_suggestion=suggested,
        category_agreement_rate=rate(agreed, suggested),
        suggestion_acceptance_rate=rate(accepted, answered),
        priority_overrides=overrides,
        reviewed=reviewed,
        marked_incorrect=incorrect,
        feedback_count=fb_total,
        average_rating=round(float(fb_avg), 2) if fb_avg is not None else None,
        satisfied_rate=rate(satisfied, fb_total),
        ai_helpful_rate=rate(ai_yes, ai_answered),
    )
