"""Database access for in-app notifications."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification


def add(db: Session, *, user_id: int, complaint_id: int | None, type: str, message: str) -> Notification:
    notification = Notification(user_id=user_id, complaint_id=complaint_id, type=type, message=message)
    db.add(notification)
    return notification


def list_for_user(
    db: Session, *, user_id: int, unread_only: bool, limit: int, offset: int
) -> tuple[list[Notification], int, int]:
    """Returns (page, total matching, unread count)."""
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    unread = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        )
    ) or 0
    items = db.scalars(
        query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total, unread


def get_for_user(db: Session, *, user_id: int, notification_id: int) -> Notification | None:
    return db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    )


def mark_all_read(db: Session, *, user_id: int) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    return result.rowcount or 0
