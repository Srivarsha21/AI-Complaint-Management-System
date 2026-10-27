"""User dashboard summary and administrator analytics.

Date filters are calendar dates in Indian Standard Time (Asia/Kolkata, UTC+05:30,
no daylight saving): `date_from=2026-10-01` means created at or after
2026-10-01 00:00 IST, and `date_to=2026-10-31` means created before
2026-11-01 00:00 IST (both ends inclusive as dates).
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.models.complaint import ComplaintPriority, ComplaintStatus
from app.models.user import User
from app.repositories import analytics_repository as repo
from app.repositories.analytics_repository import AnalyticsFilters, ComplaintScope, Granularity
from app.schemas.analytics import (
    AnalyticsOut,
    AppliedFilters,
    DashboardSummary,
    NamedCount,
    OldestOpenComplaint,
    PriorityCount,
    RecentUpdate,
    ResolutionStats,
    StatusBreakdown,
    StatusCount,
    Totals,
    Trend,
    TrendPoint,
)
from app.services.complaint_scope import scope_for

IST = timezone(timedelta(hours=5, minutes=30), "IST")
TIMEZONE_NAME = repo.REPORT_TIMEZONE
# Ranges longer than this are bucketed by ISO week (Monday start) instead of by day.
DAILY_TREND_MAX_DAYS = 90
UNASSIGNED_DEPARTMENT = "Unassigned"


@dataclass
class AnalyticsParams:
    date_from: date | None = None
    date_to: date | None = None
    category_id: int | None = None
    department_id: int | None = None
    status: ComplaintStatus | None = None
    search: str | None = None


def ist_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def now_ist() -> datetime:
    return datetime.now(IST)


def to_filters(params: AnalyticsParams) -> AnalyticsFilters:
    if params.date_from and params.date_to and params.date_from > params.date_to:
        raise BadRequestError("The start date must be on or before the end date.")
    return AnalyticsFilters(
        created_from=ist_midnight(params.date_from) if params.date_from else None,
        created_before=ist_midnight(params.date_to + timedelta(days=1)) if params.date_to else None,
        category_id=params.category_id,
        department_id=params.department_id,
        status=params.status,
        search=(params.search or "").strip() or None,
    )


def breakdown(counts: dict[ComplaintStatus, int]) -> StatusBreakdown:
    return StatusBreakdown(**{status.value: counts.get(status, 0) for status in ComplaintStatus})


# --- User dashboard --------------------------------------------------------------

def user_summary(db: Session, user: User) -> DashboardSummary:
    """Counts and recent activity for the caller's own complaints (for every role)."""
    own = ComplaintScope(owner_id=user.id)
    by_status = breakdown(repo.status_counts(db, AnalyticsFilters(), own))
    recent = repo.recent_history_for_owner(db, user.id, limit=10)
    return DashboardSummary(
        total=sum(by_status.model_dump().values()),
        pending=by_status.submitted + by_status.assigned,
        by_status=by_status,
        recent_updates=[RecentUpdate.model_validate(row, from_attributes=True) for row in recent],
    )


# --- Administrator analytics ---------------------------------------------------

def _periods(start: date, end: date, granularity: Granularity) -> list[date]:
    if granularity == "week":
        start = start - timedelta(days=start.weekday())
        step = timedelta(days=7)
    else:
        step = timedelta(days=1)
    periods, current = [], start
    while current <= end:
        periods.append(current)
        current += step
    return periods


def _trend(db: Session, params: AnalyticsParams, filters: AnalyticsFilters, scope: ComplaintScope) -> Trend:
    start = params.date_from or repo.earliest_created_local_date(db, filters, scope)
    end = params.date_to or now_ist().date()
    if start is None or start > end:
        return Trend(granularity="day", points=[])

    granularity: Granularity = "week" if (end - start).days + 1 > DAILY_TREND_MAX_DAYS else "day"
    created = repo.created_per_period(db, filters, scope, granularity)
    resolved = repo.resolved_per_period(
        db, filters, scope, granularity,
        resolved_from=ist_midnight(start), resolved_before=ist_midnight(end + timedelta(days=1)),
    )
    return Trend(
        granularity=granularity,
        points=[
            TrendPoint(period_start=p, created=created.get(p, 0), resolved=resolved.get(p, 0))
            for p in _periods(start, end, granularity)
        ],
    )


def analytics(db: Session, user: User, params: AnalyticsParams) -> AnalyticsOut:
    filters = to_filters(params)
    scope = scope_for(user)

    status_counts = repo.status_counts(db, filters, scope)
    by_status = breakdown(status_counts)
    priority_counts = repo.priority_counts(db, filters, scope)
    sample, average, median = repo.resolution_hours(db, filters, scope)
    now = datetime.now(UTC)

    return AnalyticsOut(
        generated_at=now,
        filters=AppliedFilters(
            date_from=params.date_from, date_to=params.date_to, category_id=params.category_id,
            department_id=params.department_id, status=params.status, timezone=TIMEZONE_NAME,
        ),
        totals=Totals(
            total=sum(status_counts.values()),
            open=by_status.submitted + by_status.assigned + by_status.in_progress,
            pending=by_status.submitted + by_status.assigned,
            in_progress=by_status.in_progress,
            resolved=by_status.resolved,
            closed=by_status.closed,
        ),
        by_status=[StatusCount(status=s, count=status_counts.get(s, 0)) for s in ComplaintStatus],
        by_priority=[
            *(PriorityCount(priority=p.value, count=priority_counts.get(p.value, 0)) for p in ComplaintPriority),
            PriorityCount(priority="not_assessed", count=priority_counts.get(None, 0)),
        ],
        by_category=[NamedCount(id=r.id, name=r.name, count=r.count) for r in repo.category_counts(db, filters, scope)],
        by_department=[
            NamedCount(id=r.id, name=r.name or UNASSIGNED_DEPARTMENT, count=r.count)
            for r in repo.department_counts(db, filters, scope)
        ],
        trend=_trend(db, params, filters, scope),
        resolution=ResolutionStats(
            average_hours=round(average, 2) if average is not None else None,
            median_hours=round(median, 2) if median is not None else None,
            sample_size=sample,
        ),
        oldest_open=[
            OldestOpenComplaint(
                id=c.id,
                reference_number=c.reference_number,
                subject=c.subject,
                status=c.status,
                priority=c.priority,
                category=c.category.name,
                department=c.department.name if c.department else None,
                created_at=c.created_at,
                age_days=max(0, (now - c.created_at).days),
            )
            for c in repo.oldest_open(db, filters, scope, limit=5)
        ],
    )
