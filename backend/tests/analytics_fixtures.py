"""A small, fully controlled complaint data set for analytics and report tests.

All times are given in IST (UTC+05:30). Expected numbers are derived by hand
in the test modules from the table below.

ref        owner  category   department  created (IST)      status       priority  resolved after
CMP-..01   alice  Drainage   Sewerage    2026-10-01 10:00   resolved     high      10 h
CMP-..02   alice  Potholes   Roads       2026-10-01 23:30   submitted    -         -
CMP-..03   bob    Drainage   Sewerage    2026-10-02 00:30*  in_progress  low       -
CMP-..04   bob    Potholes   Roads       2026-10-03 09:00   closed       -         30 h (closed after 40 h)
CMP-..05   bob    Drainage   (none)      2026-10-05 12:00   assigned     critical  -
CMP-..06   alice  Potholes   Roads       2026-09-20 12:00   resolved     medium    288 h (2026-10-02 12:00 IST)

* 2026-10-02 00:30 IST is still 2026-10-01 in UTC: it checks IST day boundaries.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models import Category, Complaint, ComplaintPriority, ComplaintStatus, ComplaintStatusHistory, User, UserRole
from tests.conftest import make_category, make_user

IST = timezone(timedelta(hours=5, minutes=30))
S = ComplaintStatus
P = ComplaintPriority


def ist(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=IST)


@dataclass
class Fixture:
    admin: User
    alice: User
    bob: User
    drainage: Category
    potholes: Category
    complaints: dict[str, Complaint]

    def ref(self, n: int) -> str:
        return f"CMP-2026-{n:06d}"


def build(db) -> Fixture:
    admin = make_user(db, email="admin@example.com", full_name="Admin One", role=UserRole.ADMIN)
    alice = make_user(db, email="alice@example.com", full_name="Alice Reddy")
    bob = make_user(db, email="bob@example.com", full_name="Bob Naidu")
    drainage = make_category(db, name="Drainage", slug="drainage", department="Sewerage Dept")
    potholes = make_category(db, name="Potholes", slug="potholes", department="Roads Dept")

    spec = [
        (1, alice, drainage, True, ist(2026, 10, 1, 10), S.RESOLVED, P.HIGH, 10, None),
        (2, alice, potholes, True, ist(2026, 10, 1, 23, 30), S.SUBMITTED, None, None, None),
        (3, bob, drainage, True, ist(2026, 10, 2, 0, 30), S.IN_PROGRESS, P.LOW, None, None),
        (4, bob, potholes, True, ist(2026, 10, 3, 9), S.CLOSED, None, 30, 40),
        (5, bob, drainage, False, ist(2026, 10, 5, 12), S.ASSIGNED, P.CRITICAL, None, None),
        (6, alice, potholes, True, ist(2026, 9, 20, 12), S.RESOLVED, P.MEDIUM, 288, None),
    ]
    complaints: dict[str, Complaint] = {}
    for n, owner, category, routed, created, status, priority, resolved_h, closed_h in spec:
        complaint = Complaint(
            reference_number=f"CMP-2026-{n:06d}",
            user_id=owner.id,
            subject=f"Complaint number {n} about {category.name.lower()}",
            description="A sufficiently long description for the fixture data.",
            category_id=category.id,
            department_id=category.department_id if routed else None,
            location_text="Ameerpet, Hyderabad",
            status=status,
            priority=priority,
            created_at=created,
            resolved_at=created + timedelta(hours=resolved_h) if resolved_h else None,
            closed_at=created + timedelta(hours=closed_h) if closed_h else None,
        )
        db.add(complaint)
        db.flush()
        db.add(ComplaintStatusHistory(complaint_id=complaint.id, from_status=None, to_status=S.SUBMITTED,
                                      changed_by_id=owner.id, created_at=created))
        if status != S.SUBMITTED:
            db.add(ComplaintStatusHistory(
                complaint_id=complaint.id, from_status=S.SUBMITTED, to_status=status, changed_by_id=admin.id,
                note=f"Moved to {status.value}", created_at=created + timedelta(hours=1),
            ))
        complaints[complaint.reference_number] = complaint
    db.commit()
    return Fixture(admin=admin, alice=alice, bob=bob, drainage=drainage, potholes=potholes, complaints=complaints)
