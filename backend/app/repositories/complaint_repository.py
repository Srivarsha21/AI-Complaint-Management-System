"""Database access for complaints and their related records."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.complaint import (
    Complaint,
    ComplaintAssignment,
    ComplaintAttachment,
    ComplaintComment,
    ComplaintPriority,
    ComplaintStatus,
    ComplaintStatusHistory,
)

_DETAIL_OPTIONS = (
    selectinload(Complaint.history),
    selectinload(Complaint.comments),
    selectinload(Complaint.attachments),
    selectinload(Complaint.assignments),
)


@dataclass
class ComplaintFilters:
    owner_id: int | None = None  # None = all complaints (staff view)
    department_id: int | None = None  # set for department staff
    status: ComplaintStatus | None = None
    category_id: int | None = None
    priority: ComplaintPriority | None = None
    search: str | None = None
    sort: Literal["newest", "oldest", "updated"] = "newest"


def add(db: Session, complaint: Complaint) -> Complaint:
    db.add(complaint)
    db.flush()
    return complaint


def get_detail(db: Session, complaint_id: int) -> Complaint | None:
    return db.scalar(select(Complaint).options(*_DETAIL_OPTIONS).where(Complaint.id == complaint_id))


def get_detail_by_reference(db: Session, reference: str) -> Complaint | None:
    return db.scalar(
        select(Complaint).options(*_DETAIL_OPTIONS).where(Complaint.reference_number == reference.strip().upper())
    )


def list_complaints(db: Session, filters: ComplaintFilters, *, limit: int, offset: int) -> tuple[list[Complaint], int]:
    query = select(Complaint)
    if filters.owner_id is not None:
        query = query.where(Complaint.user_id == filters.owner_id)
    if filters.department_id is not None:
        query = query.where(Complaint.department_id == filters.department_id)
    if filters.status:
        query = query.where(Complaint.status == filters.status)
    if filters.category_id:
        query = query.where(Complaint.category_id == filters.category_id)
    if filters.priority:
        query = query.where(Complaint.priority == filters.priority)
    if filters.search:
        pattern = f"%{filters.search.strip()}%"
        query = query.where(or_(Complaint.reference_number.ilike(pattern), Complaint.subject.ilike(pattern)))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    order = {
        "newest": (Complaint.created_at.desc(), Complaint.id.desc()),
        "oldest": (Complaint.created_at.asc(), Complaint.id.asc()),
        "updated": (Complaint.updated_at.desc(), Complaint.id.desc()),
    }[filters.sort]
    items = db.scalars(query.order_by(*order).limit(limit).offset(offset)).unique().all()
    return list(items), total


def add_history(
    db: Session, *, complaint: Complaint, from_status: ComplaintStatus | None, to_status: ComplaintStatus,
    changed_by_id: int | None, note: str | None,
) -> ComplaintStatusHistory:
    entry = ComplaintStatusHistory(
        complaint=complaint, from_status=from_status, to_status=to_status, changed_by_id=changed_by_id, note=note
    )
    db.add(entry)
    return entry


def add_comment(db: Session, *, complaint: Complaint, author_id: int, body: str, is_internal: bool) -> ComplaintComment:
    comment = ComplaintComment(complaint=complaint, author_id=author_id, body=body, is_internal=is_internal)
    db.add(comment)
    db.flush()
    return comment


def get_attachment(db: Session, complaint_id: int, attachment_id: int) -> ComplaintAttachment | None:
    return db.scalar(
        select(ComplaintAttachment).where(
            ComplaintAttachment.id == attachment_id, ComplaintAttachment.complaint_id == complaint_id
        )
    )


def add_assignment(
    db: Session, *, complaint: Complaint, from_department_id: int | None, to_department_id: int | None,
    assigned_to_id: int | None, assigned_by_id: int, note: str | None,
) -> ComplaintAssignment:
    entry = ComplaintAssignment(
        complaint=complaint, from_department_id=from_department_id, to_department_id=to_department_id,
        assigned_to_id=assigned_to_id, assigned_by_id=assigned_by_id, note=note,
    )
    db.add(entry)
    return entry
