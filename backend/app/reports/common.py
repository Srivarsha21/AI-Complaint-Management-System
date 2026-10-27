"""Data shared by the PDF and Excel report builders.

Builders receive plain, already-authorised data; they never query the
database. Rows never contain contact details (email or phone), and the
complainant's name is present only when `include_complainant` is true.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), "IST")

STATUS_LABELS = {
    "submitted": "Submitted",
    "assigned": "Assigned",
    "in_progress": "In progress",
    "resolved": "Resolved",
    "closed": "Closed",
}

PRIORITY_LABELS = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical", None: "Not assessed"}


@dataclass
class ReportRow:
    reference_number: str
    subject: str
    category: str
    department: str | None
    priority: str | None
    status: str
    complainant: str | None
    created_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None


@dataclass
class ReportData:
    title: str
    generated_at: datetime  # timezone-aware
    scope_label: str
    filters: list[tuple[str, str]]  # (label, value) pairs of applied filters
    include_complainant: bool
    rows: list[ReportRow]
    total_matching: int
    max_rows: int
    status_counts: list[tuple[str, int]] = field(default_factory=list)  # (label, count)
    category_counts: list[tuple[str, int]] = field(default_factory=list)

    @property
    def truncated(self) -> bool:
        return self.total_matching > len(self.rows)

    @property
    def truncation_note(self) -> str | None:
        if not self.truncated:
            return None
        return (
            f"Showing the newest {len(self.rows):,} of {self.total_matching:,} matching complaints "
            f"(limit {self.max_rows:,} rows). Narrow the filters to export the rest."
        )


def to_ist(value: datetime | None) -> datetime | None:
    return value.astimezone(IST) if value is not None else None


def format_ist(value: datetime | None, fmt: str = "%d %b %Y %H:%M") -> str:
    local = to_ist(value)
    return local.strftime(fmt) if local else ""
