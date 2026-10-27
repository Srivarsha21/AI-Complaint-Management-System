"""Feedback after resolution and administrator review of AI predictions (module 11)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.rate_limit import client_ip
from app.db.session import get_db
from app.models.user import User
from app.schemas.feedback import AIReviewItem, AIReviewPage, AIReviewUpdate, FeedbackCreate, FeedbackOut, QualitySummary
from app.services import feedback_service

router = APIRouter(tags=["feedback"])


@router.post("/complaints/{complaint_id}/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    complaint_id: int, body: FeedbackCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FeedbackOut:
    """The complainant rates the outcome once the complaint is resolved or closed (one per complaint)."""
    return feedback_service.submit_feedback(db, user=user, complaint_id=complaint_id, data=body)


@router.get("/complaints/{complaint_id}/feedback", response_model=FeedbackOut | None)
def get_feedback(complaint_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FeedbackOut | None:
    return feedback_service.get_feedback(db, user=user, complaint_id=complaint_id)


@router.get("/admin/ai-review", response_model=AIReviewPage)
def list_ai_reviews(
    review_status: Literal["unreviewed", "correct", "incorrect"] | None = None,
    flagged_only: bool = True,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AIReviewPage:
    """Predictions with disagreement signals (changed category, rejected suggestion, staff override, negative feedback)."""
    items, total = feedback_service.list_reviews(
        db, review_status=review_status, flagged_only=flagged_only, limit=limit, offset=offset
    )
    return AIReviewPage(items=items, total=total)


@router.patch("/admin/ai-review/{prediction_id}", response_model=AIReviewItem)
def review_prediction(
    prediction_id: int, body: AIReviewUpdate, request: Request,
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
) -> AIReviewItem:
    return feedback_service.review_prediction(db, actor=admin, prediction_id=prediction_id, data=body, ip_address=client_ip(request))


@router.get("/admin/ai-review/summary", response_model=QualitySummary)
def quality_summary(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> QualitySummary:
    return feedback_service.quality_summary(db)


@router.get("/admin/ai-review/corrections.csv")
def export_corrections(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    """Reviewed corrections for a deliberate, manual retraining run. Nothing is retrained automatically."""
    content = feedback_service.export_corrections_csv(db, actor=admin, ip_address=client_ip(request))
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ai-corrections.csv"', "Cache-Control": "private, no-store"},
    )
