"""Dashboard and analytics response schemas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.complaint import ComplaintPriority, ComplaintStatus

PriorityKey = Literal["low", "medium", "high", "critical", "not_assessed"]


class StatusBreakdown(BaseModel):
    submitted: int = 0
    assigned: int = 0
    in_progress: int = 0
    resolved: int = 0
    closed: int = 0


class RecentUpdate(BaseModel):
    complaint_id: int
    reference_number: str | None
    subject: str
    from_status: ComplaintStatus | None
    to_status: ComplaintStatus
    note: str | None
    at: datetime


class DashboardSummary(BaseModel):
    total: int
    pending: int  # submitted + assigned
    by_status: StatusBreakdown
    recent_updates: list[RecentUpdate]


class AppliedFilters(BaseModel):
    date_from: date | None
    date_to: date | None
    category_id: int | None
    department_id: int | None
    status: ComplaintStatus | None
    timezone: str


class Totals(BaseModel):
    total: int
    open: int  # submitted + assigned + in_progress
    pending: int  # submitted + assigned
    in_progress: int
    resolved: int
    closed: int


class StatusCount(BaseModel):
    status: ComplaintStatus
    count: int


class PriorityCount(BaseModel):
    priority: PriorityKey
    count: int


class NamedCount(BaseModel):
    id: int | None  # None = complaints without a department ("Unassigned")
    name: str
    count: int


class TrendPoint(BaseModel):
    period_start: date
    created: int
    resolved: int


class Trend(BaseModel):
    granularity: Literal["day", "week"]
    points: list[TrendPoint]


class ResolutionStats(BaseModel):
    average_hours: float | None
    median_hours: float | None
    sample_size: int  # complaints with a resolved_at timestamp


class OldestOpenComplaint(BaseModel):
    id: int
    reference_number: str | None
    subject: str
    status: ComplaintStatus
    priority: ComplaintPriority | None
    category: str
    department: str | None
    created_at: datetime
    age_days: int


class AnalyticsOut(BaseModel):
    generated_at: datetime
    filters: AppliedFilters
    totals: Totals
    by_status: list[StatusCount]
    by_priority: list[PriorityCount]
    by_category: list[NamedCount]
    by_department: list[NamedCount]
    trend: Trend
    resolution: ResolutionStats
    oldest_open: list[OldestOpenComplaint]
