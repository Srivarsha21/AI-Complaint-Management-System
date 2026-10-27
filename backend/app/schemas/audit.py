from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    action: str
    target_type: str
    target_id: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class AuditLogList(BaseModel):
    items: list[AuditLogOut]
    total: int
