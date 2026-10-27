"""AI analysis of complaints (module 5): category suggestion, priority, sentiment, duplicates.

All outputs are predictions shown to help citizens and staff; nothing here
rejects a complaint or changes its category. AI failures must never block a
complaint submission (see `record_prediction_safely`).
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.ai import classifier, duplicates, sentiment
from app.ai.preprocessing import complaint_text
from app.ai.priority import predict_priority
from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.models.ai_prediction import ComplaintAIPrediction
from app.models.complaint import Complaint, ComplaintPriority, PrioritySource
from app.models.department import Category
from app.models.user import User
from app.repositories import ai_repository, audit_repository, category_repository, complaint_repository
from app.schemas.ai import (
    AnalyzeRequest,
    AnalyzeResponse,
    CategorySuggestion,
    ComplaintAIOut,
    DuplicateOut,
    PriorityOut,
    SentimentOut,
    StoredPredictionOut,
)
from app.schemas.complaint import DepartmentBrief
from app.services import complaint_workflow

logger = logging.getLogger(__name__)

ALTERNATIVES = 3


def _suggestions(db: Session, prediction: classifier.CategoryPrediction | None) -> list[CategorySuggestion]:
    """Ranked predictions mapped to active DB categories (unknown slugs are skipped)."""
    if prediction is None:
        return []
    result = []
    for slug, probability in prediction.ranked[: ALTERNATIVES + 1]:
        category = ai_repository.get_active_category_by_slug(db, slug)
        if category is not None:
            result.append(
                CategorySuggestion(id=category.id, name=category.name, slug=category.slug, confidence=round(probability, 3))
            )
    return result


def _similar(
    db: Session, *, text: str, category_id: int, latitude: float | None, longitude: float | None,
    exclude_id: int | None = None,
) -> list[duplicates.DuplicateMatch]:
    settings = get_settings()
    since = datetime.now(UTC) - timedelta(days=settings.ai_duplicate_window_days)
    rows = ai_repository.find_duplicate_candidates(db, category_id=category_id, since=since, exclude_id=exclude_id)
    candidates = [
        duplicates.Candidate(
            id=c.id, text=complaint_text(c.subject, c.description), latitude=c.latitude, longitude=c.longitude, payload=c
        )
        for c in rows
    ]
    return duplicates.find_duplicates(
        text, candidates, latitude=latitude, longitude=longitude,
        threshold=settings.ai_duplicate_threshold, max_distance_m=settings.ai_duplicate_max_distance_m,
        limit=settings.ai_duplicate_max_results,
    )


def _duplicate_out(match: duplicates.DuplicateMatch, *, staff: bool) -> DuplicateOut:
    complaint: Complaint = match.candidate.payload
    out = DuplicateOut(reference_number=complaint.reference_number, status=complaint.status, similarity=match.similarity)
    if staff:  # other people's complaint details are visible to staff only
        out.complaint_id = complaint.id
        out.subject = complaint.subject
        out.distance_m = match.distance_m
    return out


def analyze(db: Session, *, viewer: User, request: AnalyzeRequest) -> AnalyzeResponse:
    text = complaint_text(request.subject, request.description)
    chosen: Category | None = None
    if request.category_id is not None:
        chosen = category_repository.get(db, request.category_id)
        if chosen is None or not chosen.is_active:
            raise BadRequestError("Please choose a valid category.")

    prediction = classifier.predict(text)
    ranked = _suggestions(db, prediction)
    top = ranked[0] if ranked else None
    top_category = ai_repository.get_active_category_by_slug(db, top.slug) if top else None

    basis = chosen or top_category
    priority = predict_priority(text, basis.slug if basis else None, basis.name if basis else None)
    mood = sentiment.analyse(text)

    matches = []
    if basis is not None:
        matches = _similar(db, text=text, category_id=basis.id, latitude=request.latitude, longitude=request.longitude)
    staff = complaint_workflow.is_staff(viewer)

    return AnalyzeResponse(
        model_status="ready" if classifier.is_available() else "not_trained",
        category=top,
        alternatives=ranked[1:],
        department=DepartmentBrief.model_validate(top_category.department) if top_category else None,
        priority=PriorityOut(level=ComplaintPriority(priority.level), factors=priority.factors),
        sentiment=SentimentOut(label=mood.label, score=mood.score, urgency=mood.urgency),
        possible_emergency=priority.possible_emergency,
        emergency_message=priority.emergency_message,
        duplicates=[_duplicate_out(m, staff=staff) for m in matches],
        model_version=prediction.model_version if prediction else None,
    )


# --- Submission hook ---------------------------------------------------------------------

def record_prediction(db: Session, *, complaint_id: int, ai_category_accepted: bool | None) -> ComplaintAIPrediction:
    complaint = complaint_repository.get_detail(db, complaint_id)
    if complaint is None:
        raise ValueError(f"complaint {complaint_id} not found")
    text = complaint_text(complaint.subject, complaint.description)

    prediction = classifier.predict(text)
    predicted_category = ai_repository.get_active_category_by_slug(db, prediction.slug) if prediction else None
    priority = predict_priority(text, complaint.category.slug, complaint.category.name)
    mood = sentiment.analyse(text)
    matches = _similar(
        db, text=text, category_id=complaint.category_id, latitude=complaint.latitude,
        longitude=complaint.longitude, exclude_id=complaint.id,
    )

    record = ai_repository.add_prediction(
        db,
        ComplaintAIPrediction(
            complaint_id=complaint.id,
            predicted_category_id=predicted_category.id if predicted_category else None,
            category_confidence=round(prediction.confidence, 4) if prediction else None,
            predicted_priority=ComplaintPriority(priority.level),
            priority_factors=priority.factors,
            sentiment_label=mood.label,
            sentiment_score=mood.score,
            urgency_score=mood.urgency,
            possible_emergency=priority.possible_emergency,
            duplicate_candidates=[
                {
                    "complaint_id": m.candidate.payload.id,
                    "reference_number": m.candidate.payload.reference_number,
                    "status": m.candidate.payload.status.value,
                    "similarity": m.similarity,
                    "distance_m": m.distance_m,
                }
                for m in matches
            ],
            model_version=prediction.model_version if prediction else None,
            user_accepted_category=ai_category_accepted,
        ),
    )
    # A prediction only: staff may override it, which sets priority_source = 'staff'.
    if complaint.priority_source is None:
        complaint.priority = ComplaintPriority(priority.level)
        complaint.priority_source = PrioritySource.AI
    db.commit()
    return record


def record_prediction_safely(db: Session, *, complaint_id: int, ai_category_accepted: bool | None) -> None:
    """Best-effort wrapper for the submission hook: logs and swallows every error."""
    try:
        record_prediction(db, complaint_id=complaint_id, ai_category_accepted=ai_category_accepted)
    except Exception:
        db.rollback()
        logger.exception("AI analysis failed for complaint_id=%s; complaint was saved without it", complaint_id)


# --- Staff views -------------------------------------------------------------------------

def _stored_out(record: ComplaintAIPrediction) -> StoredPredictionOut:
    category = record.predicted_category
    return StoredPredictionOut(
        predicted_category=(
            CategorySuggestion(
                id=category.id, name=category.name, slug=category.slug, confidence=record.category_confidence or 0.0
            )
            if category
            else None
        ),
        predicted_priority=record.predicted_priority,
        priority_factors=record.priority_factors or [],
        sentiment_label=record.sentiment_label,
        sentiment_score=record.sentiment_score,
        urgency_score=record.urgency_score,
        possible_emergency=record.possible_emergency,
        duplicate_candidates=record.duplicate_candidates or [],
        model_version=record.model_version,
        user_accepted_category=record.user_accepted_category,
        created_at=record.created_at,
    )


def complaint_analysis(db: Session, *, complaint: Complaint) -> ComplaintAIOut:
    """Stored prediction plus a fresh similar-complaints search (staff only; checked by the router)."""
    record = ai_repository.get_prediction(db, complaint.id)
    matches = _similar(
        db, text=complaint_text(complaint.subject, complaint.description), category_id=complaint.category_id,
        latitude=complaint.latitude, longitude=complaint.longitude, exclude_id=complaint.id,
    )
    return ComplaintAIOut(
        complaint_id=complaint.id,
        prediction=_stored_out(record) if record else None,
        priority=complaint.priority,
        priority_source=complaint.priority_source,
        similar=[_duplicate_out(m, staff=True) for m in matches],
        model_status="ready" if classifier.is_available() else "not_trained",
    )


PRIORITY_LABEL = {p: p.value.capitalize() for p in ComplaintPriority}


def override_priority(
    db: Session, *, user: User, complaint: Complaint, priority: ComplaintPriority, note: str | None,
    ip_address: str | None,
) -> None:
    previous, previous_source = complaint.priority, complaint.priority_source
    complaint.priority = priority
    complaint.priority_source = PrioritySource.STAFF

    was = (
        f"{PRIORITY_LABEL[previous]} ({'AI-predicted' if previous_source == PrioritySource.AI else 'set by staff'})"
        if previous
        else "not assessed"
    )
    text = f"Priority set to {PRIORITY_LABEL[priority]} by staff (was {was})."
    note = (note or "").strip()
    if note:
        text += f" Note: {note}"
    # History-style entry so the change shows on the complaint timeline (status unchanged).
    complaint_repository.add_history(
        db, complaint=complaint, from_status=complaint.status, to_status=complaint.status,
        changed_by_id=user.id, note=text,
    )
    audit_repository.record(
        db, actor_id=user.id, action="complaint.priority_override", target_type="complaint", target_id=complaint.id,
        details={
            "from": previous.value if previous else None,
            "from_source": previous_source.value if previous_source else None,
            "to": priority.value,
        },
        ip_address=ip_address,
    )
    complaint.updated_at = datetime.now(UTC)
    db.commit()
    logger.info("priority override ref=%s %s->%s by user_id=%s", complaint.reference_number, previous, priority.value, user.id)
