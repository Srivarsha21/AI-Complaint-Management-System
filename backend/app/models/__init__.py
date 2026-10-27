"""ORM models. Import every model module here so Alembic autogenerate sees it."""

from app.db.base import Base
from app.models.ai_prediction import ComplaintAIPrediction
from app.models.attachment_analysis import AttachmentAnalysis
from app.models.audit_log import AuditLog
from app.models.auth_token import PasswordResetToken, RevokedToken
from app.models.complaint import (
    Complaint,
    ComplaintAssignment,
    ComplaintAttachment,
    ComplaintComment,
    ComplaintPriority,
    ComplaintStatus,
    ComplaintStatusHistory,
    PrioritySource,
)
from app.models.department import Category, Department
from app.models.feedback import ComplaintFeedback
from app.models.notification import Notification
from app.models.office import ChannelType, Office, SourceType
from app.models.user import User, UserRole

__all__ = [
    "AttachmentAnalysis",
    "AuditLog",
    "Base",
    "Category",
    "ChannelType",
    "Complaint",
    "ComplaintAIPrediction",
    "ComplaintAssignment",
    "ComplaintAttachment",
    "ComplaintComment",
    "ComplaintFeedback",
    "ComplaintPriority",
    "ComplaintStatus",
    "ComplaintStatusHistory",
    "Department",
    "Notification",
    "Office",
    "PasswordResetToken",
    "PrioritySource",
    "RevokedToken",
    "SourceType",
    "User",
    "UserRole",
]
