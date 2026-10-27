"""SQL aggregations for dashboards, analytics and reports.

Every number shown in dashboards and reports comes from these queries.
Day/week buckets are computed in Indian Standard Time (Asia/Kolkata), so a
complaint filed at 00:30 IST counts on that IST day even though it is the
previous day in UTC.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import Date, Row, cast, extract, func, or_, select
from sqlalchemy.orm import Session

from app.models.complaint import Complaint, ComplaintStatus, ComplaintStatusHistory
from app.models.department import Category, Department
from app.models.user import User

REPORT_TIMEZONE = "Asia/Kolkata"
OPEN_STATUSES = (ComplaintStatus.SUBMITTED, ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS)

Granularity = Literal["day", "week"]


@dataclass(frozen=True)
class ComplaintScope:
    """Which complaints a viewer may see. Both None = unrestricted (administrators)."""

    owner_id: int | None = None
    department_id: int | None = None


@dataclass
class AnalyticsFilters:
    created_from: datetime | None = None  # inclusive, timezone-aware
    created_before: datetime | None = None  # exclusive, timezone-aware
    category_id: int | None = None
    department_id: int | None = None
    status: ComplaintStatus | None = None
    search: str | None = None


def _conditions(filters: AnalyticsFilters, scope: ComplaintScope, *, include_created_range: bool = True) -> list:
    conds: list = []
    if scope.owner_id is not None:
        conds.append(Complaint.user_id == scope.owner_id)
    if scope.department_id is not None:
        conds.append(Complaint.department_id == scope.department_id)
    if include_created_range:
        if filters.created_from is not None:
            conds.append(Complaint.created_at >= filters.created_from)
        if filters.created_before is not None:
            conds.append(Complaint.created_at < filters.created_before)
    if filters.category_id:
        conds.append(Complaint.category_id == filters.category_id)
    if filters.department_id:
        conds.append(Complaint.department_id == filters.department_id)
    if filters.status:
        conds.append(Complaint.status == filters.status)
    if filters.search and filters.search.strip():
        pattern = f"%{filters.search.strip()}%"
        conds.append(or_(Complaint.reference_number.ilike(pattern), Complaint.subject.ilike(pattern)))
    return conds


def _local(column):
    """timestamptz -> local wall-clock timestamp in IST."""
    return func.timezone(REPORT_TIMEZONE, column)


# --- Counts --------------------------------------------------------------------

def status_counts(db: Session, filters: AnalyticsFilters, scope: ComplaintScope) -> dict[ComplaintStatus, int]:
    rows = db.execute(
        select(Complaint.status, func.count(Complaint.id))
        .where(*_conditions(filters, scope))
        .group_by(Complaint.status)
    ).all()
    return {status: count for status, count in rows}


def priority_counts(db: Session, filters: AnalyticsFilters, scope: ComplaintScope) -> dict[str | None, int]:
    """Keys are priority values; None means "not assessed"."""
    rows = db.execute(
        select(Complaint.priority, func.count(Complaint.id))
        .where(*_conditions(filters, scope))
        .group_by(Complaint.priority)
    ).all()
    return {(priority.value if priority is not None else None): count for priority, count in rows}


def category_counts(db: Session, filters: AnalyticsFilters, scope: ComplaintScope) -> list[Row]:
    """(id, name, count) for every category present in the results, largest first."""
    count = func.count(Complaint.id)
    return list(
        db.execute(
            select(Category.id, Category.name, count.label("count"))
            .join(Complaint, Complaint.category_id == Category.id)
            .where(*_conditions(filters, scope))
            .group_by(Category.id, Category.name)
            .order_by(count.desc(), Category.name)
        ).all()
    )


def department_counts(db: Session, filters: AnalyticsFilters, scope: ComplaintScope) -> list[Row]:
    """(id, name, count); complaints without a department have id and name None."""
    count = func.count(Complaint.id)
    return list(
        db.execute(
            select(Department.id, Department.name, count.label("count"))
            .select_from(Complaint)
            .outerjoin(Department, Complaint.department_id == Department.id)
            .where(*_conditions(filters, scope))
            .group_by(Department.id, Department.name)
            .order_by(count.desc(), Department.name)
        ).all()
    )


# --- Trends --------------------------------------------------------------------

def created_per_period(
    db: Session, filters: AnalyticsFilters, scope: ComplaintScope, granularity: Granularity
) -> dict[date, int]:
    bucket = cast(func.date_trunc(granularity, _local(Complaint.created_at)), Date)
    rows = db.execute(
        select(bucket, func.count(Complaint.id)).where(*_conditions(filters, scope)).group_by(bucket)
    ).all()
    return {period: count for period, count in rows}


def resolved_per_period(
    db: Session,
    filters: AnalyticsFilters,
    scope: ComplaintScope,
    granularity: Granularity,
    *,
    resolved_from: datetime,
    resolved_before: datetime,
) -> dict[date, int]:
    """Complaints whose resolved_at falls in [resolved_from, resolved_before), bucketed by IST period.

    The created-date filter is deliberately not applied: this series answers
    "how many complaints were resolved in this period", whenever they were filed.
    """
    bucket = cast(func.date_trunc(granularity, _local(Complaint.resolved_at)), Date)
    rows = db.execute(
        select(bucket, func.count(Complaint.id))
        .where(
            *_conditions(filters, scope, include_created_range=False),
            Complaint.resolved_at.is_not(None),
            Complaint.resolved_at >= resolved_from,
            Complaint.resolved_at < resolved_before,
        )
        .group_by(bucket)
    ).all()
    return {period: count for period, count in rows}


def earliest_created_local_date(db: Session, filters: AnalyticsFilters, scope: ComplaintScope) -> date | None:
    return db.scalar(select(cast(func.min(_local(Complaint.created_at)), Date)).where(*_conditions(filters, scope)))


# --- Resolution time -----------------------------------------------------------

def resolution_hours(db: Session, filters: AnalyticsFilters, scope: ComplaintScope) -> tuple[int, float | None, float | None]:
    """(sample size, average hours, median hours) over complaints that have resolved_at."""
    hours = extract("epoch", Complaint.resolved_at - Complaint.created_at) / 3600.0
    sample, average, median = db.execute(
        select(
            func.count(Complaint.id),
            func.avg(hours),
            func.percentile_cont(0.5).within_group(hours),
        ).where(*_conditions(filters, scope), Complaint.resolved_at.is_not(None))
    ).one()
    return (
        int(sample or 0),
        float(average) if average is not None else None,
        float(median) if median is not None else None,
    )


# --- Lists ---------------------------------------------------------------------

def oldest_open(db: Session, filters: AnalyticsFilters, scope: ComplaintScope, *, limit: int = 5) -> list[Complaint]:
    return list(
        db.scalars(
            select(Complaint)
            .where(*_conditions(filters, scope), Complaint.status.in_(OPEN_STATUSES))
            .order_by(Complaint.created_at.asc(), Complaint.id.asc())
            .limit(limit)
        ).unique()
    )


def recent_history_for_owner(db: Session, owner_id: int, *, limit: int = 10) -> list[Row]:
    """The latest status-history events on one user's complaints."""
    return list(
        db.execute(
            select(
                Complaint.id.label("complaint_id"),
                Complaint.reference_number,
                Complaint.subject,
                ComplaintStatusHistory.from_status,
                ComplaintStatusHistory.to_status,
                ComplaintStatusHistory.note,
                ComplaintStatusHistory.created_at.label("at"),
            )
            .join(Complaint, ComplaintStatusHistory.complaint_id == Complaint.id)
            .where(Complaint.user_id == owner_id)
            .order_by(ComplaintStatusHistory.created_at.desc(), ComplaintStatusHistory.id.desc())
            .limit(limit)
        ).all()
    )


def report_rows(db: Session, filters: AnalyticsFilters, scope: ComplaintScope, *, limit: int) -> list[Row]:
    """Flat rows for exports, newest first. Contains no contact details (email/phone)."""
    return list(
        db.execute(
            select(
                Complaint.id,
                Complaint.reference_number,
                Complaint.subject,
                Category.name.label("category"),
                Department.name.label("department"),
                Complaint.priority,
                Complaint.status,
                User.full_name.label("complainant"),
                Complaint.created_at,
                Complaint.resolved_at,
                Complaint.closed_at,
            )
            .select_from(Complaint)
            .join(Category, Complaint.category_id == Category.id)
            .outerjoin(Department, Complaint.department_id == Department.id)
            .join(User, Complaint.user_id == User.id)
            .where(*_conditions(filters, scope))
            .order_by(Complaint.created_at.desc(), Complaint.id.desc())
            .limit(limit)
        ).all()
    )


def department_name(db: Session, department_id: int) -> str | None:
    return db.scalar(select(Department.name).where(Department.id == department_id))
