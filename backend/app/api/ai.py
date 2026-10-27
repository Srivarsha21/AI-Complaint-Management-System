"""AI endpoints.

- Text analysis while filing, staff analysis view and priority override (module 5).
- Photo analysis and Telugu/English translation for review (modules 9-10).
"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.errors import PermissionDeniedError
from app.core.rate_limit import client_ip, limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import (
    AnalyzeRequest,
    AnalyzeResponse,
    ComplaintAIOut,
    ImageAnalysisOut,
    PriorityOverride,
    TranslateOut,
    TranslateRequest,
)
from app.schemas.complaint import ComplaintDetail
from app.services import ai_service, complaint_service, complaint_workflow, image_analysis, translation_service

router = APIRouter(tags=["ai"])


# --- Rate limits -----------------------------------------------------------------

def ai_rate_limit(scope: str):
    """Per-user limit for CPU-heavy or paid AI calls (shared in-memory limiter)."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        settings = get_settings()
        retry_after = limiter.hit(
            f"ai:{scope}:user:{user.id}", settings.ai_rate_limit_attempts, settings.ai_rate_limit_window_seconds
        )
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )
        return user

    return dependency


def _analyze_rate_limit(request: Request) -> None:
    """Per-IP limit with its own (more generous) budget than the auth endpoints."""
    settings = get_settings()
    retry_after = limiter.hit(
        f"ai-analyze:{client_ip(request)}",
        settings.ai_analyze_rate_limit_attempts,
        settings.ai_analyze_rate_limit_window_seconds,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many analysis requests. Please wait and try again.",
            headers={"Retry-After": str(retry_after)},
        )


# --- Text analysis (module 5) ------------------------------------------------------

@router.post("/ai/analyze", response_model=AnalyzeResponse, dependencies=[Depends(_analyze_rate_limit)])
def analyze(body: AnalyzeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AnalyzeResponse:
    """Suggest a category, predict priority and sentiment, and list possible duplicates. Never stores anything."""
    return ai_service.analyze(db, viewer=user, request=body)


def _get_managed_complaint(db: Session, user: User, complaint_id: int):
    complaint = complaint_service.get_for_user(db, user=user, complaint_id=complaint_id)
    # Admins manage every complaint; staff only their own department's.
    if not complaint_workflow.can_manage(complaint, user):
        raise PermissionDeniedError("Staff access required.")
    return complaint


@router.get("/complaints/{complaint_id}/ai", response_model=ComplaintAIOut)
def complaint_analysis(
    complaint_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ComplaintAIOut:
    """Managers only: the prediction stored at submission plus a fresh similar-complaints search."""
    complaint = _get_managed_complaint(db, user, complaint_id)
    return ai_service.complaint_analysis(db, complaint=complaint)


@router.patch("/complaints/{complaint_id}/priority", response_model=ComplaintDetail)
def override_priority(
    complaint_id: int,
    body: PriorityOverride,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplaintDetail:
    """Managers only: set the priority (priority_source becomes 'staff'); audited and shown in the history."""
    complaint = _get_managed_complaint(db, user, complaint_id)
    ai_service.override_priority(
        db, user=user, complaint=complaint, priority=body.priority, note=body.note, ip_address=client_ip(request)
    )
    db.expire_all()
    return complaint_service.to_detail(complaint_service.get_for_user(db, user=user, complaint_id=complaint_id), user)


# --- Photo analysis and translation (modules 9-10) ----------------------------------

@router.post("/ai/image-analysis", response_model=ImageAnalysisOut)
def analyse_image(
    image: UploadFile = File(...),
    _: User = Depends(ai_rate_limit("image-analysis")),
) -> ImageAnalysisOut:
    """Check photo quality and list COCO objects found. The image is not stored."""
    return image_analysis.analyse_upload(image)


@router.get("/complaints/{complaint_id}/attachments/{attachment_id}/analysis", response_model=ImageAnalysisOut)
def attachment_analysis(
    complaint_id: int,
    attachment_id: int,
    user: User = Depends(ai_rate_limit("attachment-analysis")),
    db: Session = Depends(get_db),
) -> ImageAnalysisOut:
    """Same authorisation as downloading the attachment; complete results are cached."""
    return image_analysis.analyse_attachment(db, user=user, complaint_id=complaint_id, attachment_id=attachment_id)


@router.post("/ai/translate", response_model=TranslateOut)
def translate(body: TranslateRequest, _: User = Depends(ai_rate_limit("translate"))) -> TranslateOut:
    """Translate for review only; 503 when the translation provider is unavailable."""
    return translation_service.translate(body)
