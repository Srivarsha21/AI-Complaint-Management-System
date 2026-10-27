"""Complaint submission, retrieval, comments, status changes and assignment."""

import logging
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BadRequestError, NotFoundError, PermissionDeniedError
from app.models.complaint import Complaint, ComplaintAttachment, ComplaintStatus
from app.models.user import User, UserRole
from app.repositories import audit_repository, category_repository, complaint_repository, user_repository
from app.repositories.complaint_repository import ComplaintFilters
from app.schemas.complaint import AssignRequest, ComplaintCreate, ComplaintDetail, StatusUpdate
from app.services import ai_service, complaint_workflow, file_storage, notification_service

logger = logging.getLogger(__name__)

NOT_FOUND = "Complaint not found."


def _reference_for(complaint: Complaint) -> str:
    return f"CMP-{datetime.now(UTC).year}-{complaint.id:06d}"


def _can_view(complaint: Complaint, user: User) -> bool:
    return complaint.user_id == user.id or complaint_workflow.can_manage(complaint, user)


def create_complaint(
    db: Session, *, user: User, data: ComplaintCreate, files: list[UploadFile], ai_category_accepted: bool | None = None
) -> Complaint:
    settings = get_settings()
    files = [f for f in files if f.filename]
    if len(files) > settings.max_attachments_per_complaint:
        raise BadRequestError(f"You can attach at most {settings.max_attachments_per_complaint} images.")

    category = category_repository.get(db, data.category_id)
    if category is None or not category.is_active:
        raise BadRequestError("Please choose a valid category.")

    # Validate and store files first, so a bad file rejects the whole submission.
    stored: list[file_storage.StoredFile] = []
    try:
        for upload in files:
            stored.append(file_storage.save_image(upload))

        complaint = Complaint(
            user_id=user.id,
            subject=data.subject,
            description=data.description,
            category_id=category.id,
            # Routed by the configurable category -> department mapping.
            department_id=category.department_id,
            location_text=data.location_text,
            latitude=data.latitude,
            longitude=data.longitude,
            incident_at=data.incident_at,
            status=ComplaintStatus.SUBMITTED,
        )
        complaint_repository.add(db, complaint)
        complaint.reference_number = _reference_for(complaint)
        complaint_repository.add_history(
            db, complaint=complaint, from_status=None, to_status=ComplaintStatus.SUBMITTED,
            changed_by_id=user.id, note=None,
        )
        for item in stored:
            db.add(
                ComplaintAttachment(
                    complaint=complaint,
                    original_filename=item.original_filename,
                    stored_filename=item.stored_filename,
                    content_type=item.content_type,
                    size_bytes=item.size_bytes,
                    uploaded_by_id=user.id,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        for item in stored:
            file_storage.delete_quietly(item.stored_filename)
        raise

    logger.info("complaint created ref=%s user_id=%s attachments=%d", complaint.reference_number, user.id, len(stored))

    # --- Module 5 (AI) hook: runs after the complaint is committed and swallows its own
    # errors, so an AI failure can never block or undo a submission.
    ai_service.record_prediction_safely(db, complaint_id=complaint.id, ai_category_accepted=ai_category_accepted)
    # --- end module 5 hook ---
    return _reload(db, user, complaint.id)


def list_for_user(
    db: Session, *, user: User, filters: ComplaintFilters, mine_only: bool, limit: int, offset: int
) -> tuple[list[Complaint], int]:
    # Regular users are always restricted to their own complaints;
    # staff see their department's complaints, admins see everything.
    if mine_only or not complaint_workflow.is_staff(user):
        filters.owner_id = user.id
    elif user.role == UserRole.STAFF:
        if user.department_id is None:
            return [], 0
        filters.department_id = user.department_id
    return complaint_repository.list_complaints(db, filters, limit=limit, offset=offset)


def get_for_user(db: Session, *, user: User, complaint_id: int) -> Complaint:
    complaint = complaint_repository.get_detail(db, complaint_id)
    # 404 (not 403) so users cannot probe which complaint IDs exist.
    if complaint is None or not _can_view(complaint, user):
        raise NotFoundError(NOT_FOUND)
    return complaint


def get_by_reference_for_user(db: Session, *, user: User, reference: str) -> Complaint:
    complaint = complaint_repository.get_detail_by_reference(db, reference)
    if complaint is None or not _can_view(complaint, user):
        raise NotFoundError(NOT_FOUND)
    return complaint


def to_detail(complaint: Complaint, viewer: User) -> ComplaintDetail:
    manager = complaint_workflow.can_manage(complaint, viewer)
    detail = ComplaintDetail.model_validate(
        {
            **{field: getattr(complaint, field) for field in ComplaintDetail.model_fields if hasattr(complaint, field)},
            "allowed_transitions": complaint_workflow.allowed_transitions(complaint, viewer),
            "can_manage": manager,
        }
    )
    if not manager:
        # Internal notes and routing history stay with the people handling the complaint.
        detail.comments = [c for c in detail.comments if not c.is_internal]
        detail.assignments = []
    return detail


def add_comment(db: Session, *, user: User, complaint_id: int, body: str, is_internal: bool) -> Complaint:
    complaint = get_for_user(db, user=user, complaint_id=complaint_id)
    manager = complaint_workflow.can_manage(complaint, user)
    if is_internal and not manager:
        raise PermissionDeniedError("Only staff handling this complaint can add internal notes.")
    if complaint.status == ComplaintStatus.CLOSED and not manager:
        raise BadRequestError("This complaint is closed. Comments are no longer accepted.")

    complaint_repository.add_comment(db, complaint=complaint, author_id=user.id, body=body, is_internal=is_internal)
    complaint.updated_at = datetime.now(UTC)
    db.commit()
    notification_service.notify_comment(db, complaint=complaint, actor=user, is_internal=is_internal)
    return _reload(db, user, complaint_id)


def _reload(db: Session, user: User, complaint_id: int) -> Complaint:
    # Sessions keep objects after commit; expire them so server-side values are re-read.
    db.expire_all()
    return get_for_user(db, user=user, complaint_id=complaint_id)


def change_status(db: Session, *, user: User, complaint_id: int, change: StatusUpdate) -> Complaint:
    complaint = get_for_user(db, user=user, complaint_id=complaint_id)
    current, target = complaint.status, change.status

    if target not in complaint_workflow.allowed_transitions(complaint, user):
        raise BadRequestError(f"Cannot change status from '{current.value}' to '{target.value}'.")
    note = (change.note or "").strip() or None
    if complaint_workflow.note_required(current, target) and not note:
        raise BadRequestError("Please add a note explaining this change.")

    now = datetime.now(UTC)
    complaint.status = target
    if target == ComplaintStatus.RESOLVED:
        complaint.resolved_at = now
    elif target == ComplaintStatus.IN_PROGRESS and current == ComplaintStatus.RESOLVED:
        complaint.resolved_at = None  # reopened
    if target == ComplaintStatus.CLOSED:
        complaint.closed_at = now

    complaint_repository.add_history(
        db, complaint=complaint, from_status=current, to_status=target, changed_by_id=user.id, note=note
    )
    db.commit()
    logger.info("complaint status ref=%s %s->%s by user_id=%s", complaint.reference_number, current.value, target.value, user.id)
    notification_service.notify_status_change(db, complaint=complaint, actor=user, from_status=current, to_status=target)
    return _reload(db, user, complaint_id)


def assign(
    db: Session, *, user: User, complaint_id: int, request: AssignRequest, ip_address: str | None = None
) -> Complaint:
    """Re-route (admins only) and/or assign a staff member of the (new) department."""
    complaint = get_for_user(db, user=user, complaint_id=complaint_id)
    if not complaint_workflow.can_manage(complaint, user):
        raise PermissionDeniedError("Only staff handling this complaint can assign it.")
    if complaint.status == ComplaintStatus.CLOSED:
        raise BadRequestError("Closed complaints cannot be re-assigned.")

    from_department_id = complaint.department_id
    to_department_id = request.department_id or from_department_id
    rerouted = to_department_id != from_department_id
    if rerouted:
        if user.role != UserRole.ADMIN:
            raise PermissionDeniedError("Only administrators can re-route complaints to another department.")
        department = category_repository.get_department(db, to_department_id)
        if department is None or not department.is_active:
            raise BadRequestError("Please choose an active department.")
    if to_department_id is None:
        raise BadRequestError("Route this complaint to a department before assigning it.")

    if request.assignee_id is not None:
        assignee = user_repository.get_by_id(db, request.assignee_id)
        if assignee is None or assignee.role != UserRole.STAFF or not assignee.is_active:
            raise BadRequestError("The assignee must be an active staff member.")
        if assignee.department_id != to_department_id:
            raise BadRequestError("The assignee must belong to the complaint's department.")
        new_assignee_id: int | None = assignee.id
    else:
        # Moving departments drops the old assignee, who belongs to the previous department.
        new_assignee_id = None if rerouted else complaint.assigned_to_id

    if not rerouted and new_assignee_id == complaint.assigned_to_id:
        raise BadRequestError("Nothing to change: the complaint is already assigned this way.")

    note = (request.note or "").strip() or None
    complaint.department_id = to_department_id
    complaint.assigned_to_id = new_assignee_id
    complaint_repository.add_assignment(
        db, complaint=complaint, from_department_id=from_department_id, to_department_id=to_department_id,
        assigned_to_id=new_assignee_id, assigned_by_id=user.id, note=note,
    )
    moved_to_assigned = new_assignee_id is not None and complaint.status == ComplaintStatus.SUBMITTED
    if moved_to_assigned:
        complaint.status = ComplaintStatus.ASSIGNED
        complaint_repository.add_history(
            db, complaint=complaint, from_status=ComplaintStatus.SUBMITTED, to_status=ComplaintStatus.ASSIGNED,
            changed_by_id=user.id, note=note,
        )
    complaint.updated_at = datetime.now(UTC)
    audit_repository.record(
        db, actor_id=user.id, action="complaint.assigned", target_type="complaint", target_id=complaint.id,
        details={
            "from_department_id": from_department_id,
            "to_department_id": to_department_id,
            "assigned_to_id": new_assignee_id,
        },
        ip_address=ip_address,
    )
    db.commit()
    logger.info(
        "complaint assigned ref=%s dept %s->%s assignee=%s by user_id=%s",
        complaint.reference_number, from_department_id, to_department_id, new_assignee_id, user.id,
    )

    notification_service.notify_assignment(db, complaint=complaint, actor=user)
    if moved_to_assigned:
        notification_service.notify_status_change(
            db, complaint=complaint, actor=user,
            from_status=ComplaintStatus.SUBMITTED, to_status=ComplaintStatus.ASSIGNED,
        )
    return _reload(db, user, complaint_id)


def get_attachment_for_user(db: Session, *, user: User, complaint_id: int, attachment_id: int) -> ComplaintAttachment:
    get_for_user(db, user=user, complaint_id=complaint_id)  # authorization
    attachment = complaint_repository.get_attachment(db, complaint_id, attachment_id)
    if attachment is None:
        raise NotFoundError("Attachment not found.")
    return attachment
