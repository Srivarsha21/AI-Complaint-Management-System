"""In-app notifications.

The `notify_*` hooks are called by complaint_service after the main action has
been committed. They never raise: a notification failure is logged and rolled
back on its own, so it can never undo or fail the complaint change itself.
"""

import functools
import logging
from collections.abc import Callable, Iterable

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.complaint import Complaint, ComplaintStatus
from app.models.notification import Notification
from app.models.user import User
from app.repositories import notification_repository, user_repository

logger = logging.getLogger(__name__)

STATUS_TEXT = {
    ComplaintStatus.SUBMITTED: "Submitted",
    ComplaintStatus.ASSIGNED: "Assigned",
    ComplaintStatus.IN_PROGRESS: "In progress",
    ComplaintStatus.RESOLVED: "Resolved",
    ComplaintStatus.CLOSED: "Closed",
}


def _never_fail(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(db: Session, **kwargs) -> None:
        try:
            func(db, **kwargs)
        except Exception:
            db.rollback()
            logger.exception("notification hook %s failed", func.__name__)

    return wrapper


def _send(db: Session, complaint: Complaint, recipient_ids: Iterable[int], type_: str, message: str) -> None:
    for user_id in dict.fromkeys(recipient_ids):  # de-duplicate, keep order
        notification_repository.add(db, user_id=user_id, complaint_id=complaint.id, type=type_, message=message[:500])
    db.commit()


def _handlers(db: Session, complaint: Complaint, actor: User) -> list[int]:
    """Who works on a complaint: its assignee, otherwise every active staff member of its department."""
    if complaint.assigned_to_id is not None:
        ids = [complaint.assigned_to_id]
    elif complaint.department_id is not None:
        ids = [u.id for u in user_repository.list_active_staff(db, complaint.department_id)]
    else:
        ids = []
    return [i for i in ids if i != actor.id]


@_never_fail
def notify_status_change(
    db: Session, *, complaint: Complaint, actor: User, from_status: ComplaintStatus, to_status: ComplaintStatus
) -> None:
    ref = complaint.reference_number
    if complaint.user_id != actor.id:
        _send(db, complaint, [complaint.user_id], "status_changed",
              f"{ref}: status changed to {STATUS_TEXT[to_status]}.")
    elif from_status == ComplaintStatus.RESOLVED and to_status == ComplaintStatus.IN_PROGRESS:
        _send(db, complaint, _handlers(db, complaint, actor), "complaint_reopened",
              f"{ref}: the complainant reopened this complaint.")


@_never_fail
def notify_comment(db: Session, *, complaint: Complaint, actor: User, is_internal: bool) -> None:
    if is_internal:
        return
    ref = complaint.reference_number
    if complaint.user_id != actor.id:
        _send(db, complaint, [complaint.user_id], "comment_added", f"{ref}: {actor.full_name} added a comment.")
    else:
        _send(db, complaint, _handlers(db, complaint, actor), "complainant_comment",
              f"{ref}: the complainant added a comment.")


@_never_fail
def notify_assignment(db: Session, *, complaint: Complaint, actor: User) -> None:
    if complaint.assigned_to_id is None or complaint.assigned_to_id == actor.id:
        return
    _send(db, complaint, [complaint.assigned_to_id], "assigned",
          f"{complaint.reference_number}: assigned to you by {actor.full_name}.")


# --- Reading -------------------------------------------------------------------------

def list_for_user(
    db: Session, *, user: User, unread_only: bool, limit: int, offset: int
) -> tuple[list[Notification], int, int]:
    return notification_repository.list_for_user(
        db, user_id=user.id, unread_only=unread_only, limit=limit, offset=offset
    )


def mark_read(db: Session, *, user: User, notification_id: int) -> Notification:
    notification = notification_repository.get_for_user(db, user_id=user.id, notification_id=notification_id)
    # Another user's notification is reported as missing.
    if notification is None:
        raise NotFoundError("Notification not found.")
    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_read(db: Session, *, user: User) -> int:
    updated = notification_repository.mark_all_read(db, user_id=user.id)
    db.commit()
    return updated
