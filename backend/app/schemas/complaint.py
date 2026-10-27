"""Complaint request/response schemas."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.models.complaint import ComplaintPriority, ComplaintStatus, PrioritySource
from app.models.user import UserRole


def _clean_text(min_length: int, label: str):
    def validator(value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < min_length:
            raise ValueError(f"{label} must be at least {min_length} characters")
        return cleaned

    return AfterValidator(validator)


def _single_line(value: str) -> str:
    return " ".join(value.split())


Subject = Annotated[str, Field(max_length=150), AfterValidator(_single_line), _clean_text(5, "Subject")]
Description = Annotated[str, Field(max_length=5000), _clean_text(20, "Description")]
LocationText = Annotated[str, Field(max_length=255), AfterValidator(_single_line), _clean_text(3, "Location")]
CommentBody = Annotated[str, Field(max_length=2000), _clean_text(1, "Comment")]


# --- Lookups -----------------------------------------------------------------

class DepartmentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class CategoryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    description: str | None
    department: DepartmentBrief


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    role: UserRole


# --- Requests ------------------------------------------------------------------

class ComplaintCreate(BaseModel):
    subject: Subject
    description: Description
    category_id: int = Field(gt=0)
    location_text: LocationText
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    incident_at: datetime | None = None

    @model_validator(mode="after")
    def _check(self) -> "ComplaintCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or neither")
        if self.incident_at is not None:
            if self.incident_at.tzinfo is None:
                raise ValueError("incident_at must include a timezone")
            # Small allowance for clock differences between browser and server.
            if self.incident_at > datetime.now(UTC) + timedelta(minutes=5):
                raise ValueError("Incident date and time cannot be in the future")
        return self


class CommentCreate(BaseModel):
    body: CommentBody
    is_internal: bool = False


class StatusUpdate(BaseModel):
    status: ComplaintStatus
    note: str | None = Field(default=None, max_length=1000)


class AssignRequest(BaseModel):
    """Re-route to another department (admins) and/or assign a staff member."""

    department_id: int | None = Field(default=None, gt=0)
    assignee_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check(self) -> "AssignRequest":
        if self.department_id is None and self.assignee_id is None:
            raise ValueError("Choose a department or a staff member")
        return self


# --- Responses -----------------------------------------------------------------

class ComplaintListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    subject: str
    status: ComplaintStatus
    priority: ComplaintPriority | None
    # Module 5: 'ai' = AI-predicted (may be reviewed), 'staff' = set by staff.
    priority_source: PrioritySource | None = None
    category: CategoryBrief
    department: DepartmentBrief | None
    location_text: str
    user: UserBrief
    assigned_to: UserBrief | None = None
    created_at: datetime
    updated_at: datetime


class StatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_status: ComplaintStatus | None
    to_status: ComplaintStatus
    note: str | None
    changed_by: UserBrief | None
    created_at: datetime


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    body: str
    is_internal: bool
    author: UserBrief | None
    created_at: datetime


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_department: DepartmentBrief | None
    to_department: DepartmentBrief | None
    assigned_to: UserBrief | None
    assigned_by: UserBrief | None
    note: str | None
    created_at: datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class ComplaintDetail(ComplaintListItem):
    description: str
    latitude: float | None
    longitude: float | None
    incident_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    history: list[StatusHistoryOut]
    comments: list[CommentOut]
    attachments: list[AttachmentOut]
    # Status changes the current viewer may perform, so the UI only offers valid actions.
    allowed_transitions: list[ComplaintStatus]
    # Routing history; only shown to people who manage the complaint (empty otherwise).
    assignments: list[AssignmentOut] = []
    # True when the viewer is an admin or staff of the complaint's department.
    can_manage: bool = False


class ComplaintPage(BaseModel):
    items: list[ComplaintListItem]
    total: int
