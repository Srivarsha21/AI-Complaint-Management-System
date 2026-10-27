"""Complaint-guidance chatbot and verified office lookup endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.chatbot import service as chatbot_service
from app.core.errors import BadRequestError
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.location.office_search import Point, search
from app.models.user import User
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.schemas.office import OfficeSearchResult

router = APIRouter(tags=["chatbot"])

_chat_rate_limit = rate_limit(
    "chatbot",
    attempts_setting="chatbot_rate_limit_attempts",
    window_setting="chatbot_rate_limit_window_seconds",
)


@router.post(
    "/chatbot/message",
    response_model=ChatResponse,
    dependencies=[Depends(_chat_rate_limit)],
)
def chatbot_message(
    payload: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ChatResponse:
    """Guidance on where to report a civic problem, from verified official records only."""
    return chatbot_service.handle(db, payload, user)


@router.get("/offices", response_model=OfficeSearchResult)
def list_offices(
    category: str | None = Query(default=None, max_length=80, pattern=r"^[a-z0-9-]+$"),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OfficeSearchResult:
    """Verified offices (nearest first when `lat`/`lng` are given) and online/phone channels."""
    if (lat is None) != (lng is None):
        raise BadRequestError("Send both lat and lng, or neither.")
    origin = Point(lat, lng) if lat is not None and lng is not None else None
    offices, channels = search(db, category, origin, office_limit=100)
    return OfficeSearchResult(offices=offices, channels=channels)
