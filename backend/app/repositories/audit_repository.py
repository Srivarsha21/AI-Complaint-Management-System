"""Database access for the audit trail."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry


def list_entries(db: Session, *, action: str | None, limit: int, offset: int) -> tuple[list[AuditLog], int]:
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)).all()
    return list(items), total
