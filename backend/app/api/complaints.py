"""Complaint endpoints: categories, submission, tracking, comments and status changes."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import NotFoundError
from app.core.rate_limit import client_ip
from app.db.session import get_db
from app.models.complaint import ComplaintPriority, ComplaintStatus
from app.models.user import User
from app.repositories import category_repository
from app.repositories.complaint_repository import ComplaintFilters
from app.schemas.complaint import (
    AssignRequest,
    CategoryOut,
    CommentCreate,
    ComplaintCreate,
    ComplaintDetail,
    ComplaintListItem,
    ComplaintPage,
    StatusUpdate,
)
from app.services import complaint_service, file_storage

router = APIRouter(tags=["complaints"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in category_repository.list_active(db)]


@router.post("/complaints", response_model=ComplaintDetail, status_code=status.HTTP_201_CREATED)
def create_complaint(
    subject: str = Form(...),
    description: str = Form(...),
    category_id: int = Form(...),
    location_text: str = Form(...),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    incident_at: datetime | None = Form(default=None),
    # Module 5: whether the citizen kept the AI-suggested category (null = no suggestion shown).
    ai_category_accepted: bool | None = Form(default=None),
    attachments: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplaintDetail:
    """Submit a complaint as multipart/form-data with up to 3 optional images."""
    try:
        data = ComplaintCreate(
            subject=subject, description=description, category_id=category_id, location_text=location_text,
            latitude=latitude, longitude=longitude, incident_at=incident_at,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False)) from exc

    complaint = complaint_service.create_complaint(
        db, user=user, data=data, files=attachments, ai_category_accepted=ai_category_accepted
    )
    return complaint_service.to_detail(complaint, user)


@router.get("/complaints", response_model=ComplaintPage)
def list_complaints(
    status_filter: ComplaintStatus | None = Query(default=None, alias="status"),
    category_id: int | None = Query(default=None, gt=0),
    priority: ComplaintPriority | None = None,
    search: str | None = Query(default=None, max_length=100),
    sort: Literal["newest", "oldest", "updated"] = "newest",
    mine: bool = Query(default=False, description="Admins/staff only: restrict to complaints you filed"),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplaintPage:
    """Users get only their own complaints; staff their department's; admins all. `mine=true` narrows to your own."""
    filters = ComplaintFilters(
        status=status_filter, category_id=category_id, priority=priority, search=search, sort=sort
    )
    items, total = complaint_service.list_for_user(
        db, user=user, filters=filters, mine_only=mine, limit=limit, offset=offset
    )
    return ComplaintPage(items=[ComplaintListItem.model_validate(c) for c in items], total=total)


@router.get("/complaints/reference/{reference}", response_model=ComplaintDetail)
def get_by_reference(reference: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ComplaintDetail:
    if len(reference) > 32:
        raise NotFoundError(complaint_service.NOT_FOUND)
    complaint = complaint_service.get_by_reference_for_user(db, user=user, reference=reference)
    return complaint_service.to_detail(complaint, user)


@router.get("/complaints/{complaint_id}", response_model=ComplaintDetail)
def get_complaint(complaint_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ComplaintDetail:
    complaint = complaint_service.get_for_user(db, user=user, complaint_id=complaint_id)
    return complaint_service.to_detail(complaint, user)


@router.post("/complaints/{complaint_id}/comments", response_model=ComplaintDetail, status_code=status.HTTP_201_CREATED)
def add_comment(
    complaint_id: int, body: CommentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ComplaintDetail:
    complaint = complaint_service.add_comment(
        db, user=user, complaint_id=complaint_id, body=body.body, is_internal=body.is_internal
    )
    return complaint_service.to_detail(complaint, user)


@router.post("/complaints/{complaint_id}/status", response_model=ComplaintDetail)
def change_status(
    complaint_id: int, body: StatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ComplaintDetail:
    complaint = complaint_service.change_status(db, user=user, complaint_id=complaint_id, change=body)
    return complaint_service.to_detail(complaint, user)


@router.post("/complaints/{complaint_id}/assign", response_model=ComplaintDetail)
def assign_complaint(
    complaint_id: int,
    body: AssignRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplaintDetail:
    """Admins: re-route and/or assign; staff: assign within their own department."""
    complaint = complaint_service.assign(
        db, user=user, complaint_id=complaint_id, request=body, ip_address=client_ip(request)
    )
    return complaint_service.to_detail(complaint, user)


@router.get("/complaints/{complaint_id}/attachments/{attachment_id}")
def download_attachment(
    complaint_id: int, attachment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FileResponse:
    attachment = complaint_service.get_attachment_for_user(
        db, user=user, complaint_id=complaint_id, attachment_id=attachment_id
    )
    path = file_storage.path_for(attachment.stored_filename)
    if not path.is_file():
        raise NotFoundError("Attachment file is missing.")
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.original_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )
