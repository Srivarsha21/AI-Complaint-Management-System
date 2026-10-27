"""The signed-in user's in-app notifications."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationList, NotificationOut, ReadAllResult
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationList:
    """Newest first. `unread` is always the total unread count (for the bell badge)."""
    items, total, unread = notification_service.list_for_user(
        db, user=user, unread_only=unread_only, limit=limit, offset=offset
    )
    return NotificationList(items=[NotificationOut.model_validate(n) for n in items], total=total, unread=unread)


@router.post("/read-all", response_model=ReadAllResult)
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReadAllResult:
    return ReadAllResult(updated=notification_service.mark_all_read(db, user=user))


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> NotificationOut:
    return NotificationOut.model_validate(notification_service.mark_read(db, user=user, notification_id=notification_id))
