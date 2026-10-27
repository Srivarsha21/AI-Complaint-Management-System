"""In-app notification schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int | None
    type: str
    message: str
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int


class ReadAllResult(BaseModel):
    updated: int
