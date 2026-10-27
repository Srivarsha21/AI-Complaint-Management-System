"""Complaints, their status history, comments, attachments and assignments."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.department import Category, Department
from app.models.user import User


def _enum(enum_cls: type[enum.Enum]) -> Enum:
    return Enum(enum_cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class ComplaintStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ComplaintPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PrioritySource(str, enum.Enum):
    """Who set `Complaint.priority`: the AI prediction (module 5) or a staff member."""

    AI = "ai"
    STAFF = "staff"


class Complaint(TimestampMixin, Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Set right after insert from the id, e.g. CMP-2026-000042.
    reference_number: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True, nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    location_text: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    incident_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ComplaintStatus] = mapped_column(
        _enum(ComplaintStatus), default=ComplaintStatus.SUBMITTED, index=True, nullable=False
    )
    # None means "not assessed yet" (assessment arrives with the AI module).
    priority: Mapped[ComplaintPriority | None] = mapped_column(_enum(ComplaintPriority), index=True)
    # Module 5: 'ai' = predicted (may be reviewed), 'staff' = set by staff; None = not assessed.
    priority_source: Mapped[PrioritySource | None] = mapped_column(_enum(PrioritySource))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Staff member of the complaint's department currently responsible for it.
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    category: Mapped[Category] = relationship(lazy="joined")
    department: Mapped[Department | None] = relationship(lazy="joined")
    history: Mapped[list["ComplaintStatusHistory"]] = relationship(
        back_populates="complaint", order_by="ComplaintStatusHistory.id", cascade="all, delete-orphan"
    )
    comments: Mapped[list["ComplaintComment"]] = relationship(
        back_populates="complaint", order_by="ComplaintComment.id", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["ComplaintAttachment"]] = relationship(
        back_populates="complaint", order_by="ComplaintAttachment.id", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["ComplaintAssignment"]] = relationship(
        back_populates="complaint", order_by="ComplaintAssignment.id", cascade="all, delete-orphan"
    )


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True, nullable=False)
    from_status: Mapped[ComplaintStatus | None] = mapped_column(_enum(ComplaintStatus))
    to_status: Mapped[ComplaintStatus] = mapped_column(_enum(ComplaintStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    complaint: Mapped[Complaint] = relationship(back_populates="history")
    changed_by: Mapped[User | None] = relationship(lazy="joined")


class ComplaintComment(Base):
    __tablename__ = "complaint_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True, nullable=False)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Internal notes are visible to staff only.
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    complaint: Mapped[Complaint] = relationship(back_populates="comments")
    author: Mapped[User | None] = relationship(lazy="joined")


class ComplaintAttachment(Base):
    __tablename__ = "complaint_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    complaint: Mapped[Complaint] = relationship(back_populates="attachments")


class ComplaintAssignment(Base):
    """One routing/assignment step: department change and/or new assignee."""

    __tablename__ = "complaint_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True, nullable=False)
    from_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    to_department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    complaint: Mapped[Complaint] = relationship(back_populates="assignments")
    from_department: Mapped[Department | None] = relationship(foreign_keys=[from_department_id], lazy="joined")
    to_department: Mapped[Department | None] = relationship(foreign_keys=[to_department_id], lazy="joined")
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    assigned_by: Mapped[User | None] = relationship(foreign_keys=[assigned_by_id], lazy="joined")
