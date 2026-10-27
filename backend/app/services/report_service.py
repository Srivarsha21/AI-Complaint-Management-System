"""PDF and Excel complaint reports with role-based scope.

Administrators export all complaints (with the complainant's full name);
everyone else exports only their own complaints, without a complainant column.
No report ever contains email addresses or phone numbers. Administrator
exports are recorded in the audit log as "report.exported".
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.models.complaint import ComplaintStatus
from app.models.user import User
from app.reports.common import STATUS_LABELS, ReportData, ReportRow
from app.reports.excel_report import build_xlsx
from app.reports.pdf_report import build_pdf
from app.repositories import analytics_repository as repo
from app.repositories import audit_repository, category_repository
from app.services.analytics_service import IST, AnalyticsParams, to_filters
from app.services.complaint_scope import has_full_access, may_see_complainant_names, scope_for

logger = logging.getLogger(__name__)

MAX_REPORT_ROWS = 5000
ReportFormat = Literal["pdf", "xlsx"]

MEDIA_TYPES: dict[ReportFormat, str] = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@dataclass
class ReportFile:
    content: bytes
    filename: str
    media_type: str


def _filter_lines(db: Session, params: AnalyticsParams) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    if params.date_from:
        lines.append(("Created from", params.date_from.isoformat()))
    if params.date_to:
        lines.append(("Created to", params.date_to.isoformat()))
    if params.category_id:
        category = category_repository.get(db, params.category_id)
        lines.append(("Category", category.name if category else f"#{params.category_id} (not found)"))
    if params.department_id:
        name = repo.department_name(db, params.department_id)
        lines.append(("Department", name or f"#{params.department_id} (not found)"))
    if params.status:
        lines.append(("Status", STATUS_LABELS[params.status.value]))
    if params.search and params.search.strip():
        lines.append(("Search", params.search.strip()))
    return lines


def _audit_details(params: AnalyticsParams, fmt: ReportFormat, report: ReportData) -> dict:
    return {
        "format": fmt,
        "filters": {
            "date_from": params.date_from.isoformat() if params.date_from else None,
            "date_to": params.date_to.isoformat() if params.date_to else None,
            "category_id": params.category_id,
            "department_id": params.department_id,
            "status": params.status.value if params.status else None,
            "search": (params.search or "").strip() or None,
        },
        "rows": len(report.rows),
        "total_matching": report.total_matching,
        "truncated": report.truncated,
    }


def build_report_data(db: Session, user: User, params: AnalyticsParams) -> ReportData:
    filters = to_filters(params)
    scope = scope_for(user)
    include_complainant = may_see_complainant_names(user)

    status_counts = repo.status_counts(db, filters, scope)
    rows = repo.report_rows(db, filters, scope, limit=MAX_REPORT_ROWS)
    return ReportData(
        title="Complaint report",
        generated_at=datetime.now(UTC).astimezone(IST),
        scope_label="All complaints" if has_full_access(user) else "Your complaints only",
        filters=_filter_lines(db, params),
        include_complainant=include_complainant,
        rows=[
            ReportRow(
                reference_number=r.reference_number or f"#{r.id}",
                subject=r.subject,
                category=r.category,
                department=r.department,
                priority=r.priority.value if r.priority else None,
                status=r.status.value,
                complainant=r.complainant if include_complainant else None,
                created_at=r.created_at,
                resolved_at=r.resolved_at,
                closed_at=r.closed_at,
            )
            for r in rows
        ],
        total_matching=sum(status_counts.values()),
        max_rows=MAX_REPORT_ROWS,
        status_counts=[(STATUS_LABELS[s.value], status_counts.get(s, 0)) for s in ComplaintStatus],
        category_counts=[(r.name, r.count) for r in repo.category_counts(db, filters, scope)],
    )


def export(
    db: Session, *, user: User, params: AnalyticsParams, fmt: ReportFormat, ip_address: str | None = None
) -> ReportFile:
    report = build_report_data(db, user, params)
    content = build_pdf(report) if fmt == "pdf" else build_xlsx(report)
    filename = f"complaints-{report.generated_at.date().isoformat()}.{fmt}"

    if has_full_access(user):
        audit_repository.record(
            db,
            actor_id=user.id,
            action="report.exported",
            target_type="report",
            target_id=fmt,
            details=_audit_details(params, fmt, report),
            ip_address=ip_address,
        )
        db.commit()
    logger.info("report exported format=%s rows=%d user_id=%s", fmt, len(report.rows), user.id)
    return ReportFile(content=content, filename=filename, media_type=MEDIA_TYPES[fmt])
