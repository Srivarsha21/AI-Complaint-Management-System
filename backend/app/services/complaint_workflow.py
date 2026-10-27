"""Complaint lifecycle rules: who may move a complaint to which status.

    submitted -> assigned -> in_progress -> resolved -> closed
                                    ^           |
                                    +-- reopen -+

Managers drive the lifecycle and may close a complaint early with a reason.
A manager is an admin (every complaint) or a staff member of the complaint's
department (see `can_manage`). The complainant may confirm a resolution
(resolved -> closed) or reopen it (resolved -> in_progress) with a reason.
"""

from app.models.complaint import Complaint, ComplaintStatus as S
from app.models.user import User, UserRole

STAFF_TRANSITIONS: dict[S, set[S]] = {
    S.SUBMITTED: {S.ASSIGNED, S.CLOSED},
    S.ASSIGNED: {S.IN_PROGRESS, S.CLOSED},
    S.IN_PROGRESS: {S.RESOLVED, S.CLOSED},
    S.RESOLVED: {S.CLOSED, S.IN_PROGRESS},
    S.CLOSED: set(),
}

OWNER_TRANSITIONS: dict[S, set[S]] = {
    S.RESOLVED: {S.CLOSED, S.IN_PROGRESS},
}

# Display order for the UI.
_ORDER = [S.SUBMITTED, S.ASSIGNED, S.IN_PROGRESS, S.RESOLVED, S.CLOSED]


def is_staff(user: User) -> bool:
    """Admins and department staff: roles that work on complaints filed by others."""
    return user.role in (UserRole.ADMIN, UserRole.STAFF)


def can_manage(complaint: Complaint, user: User) -> bool:
    """Admins manage every complaint; staff only those routed to their own department."""
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.STAFF:
        return user.department_id is not None and complaint.department_id == user.department_id
    return False


def allowed_transitions(complaint: Complaint, user: User) -> list[S]:
    allowed: set[S] = set()
    if can_manage(complaint, user):
        allowed |= STAFF_TRANSITIONS.get(complaint.status, set())
    if complaint.user_id == user.id:
        allowed |= OWNER_TRANSITIONS.get(complaint.status, set())
    return [s for s in _ORDER if s in allowed]


def note_required(from_status: S, to_status: S) -> bool:
    """Resolutions, reopenings and early closures must be explained."""
    if to_status == S.RESOLVED:
        return True
    if from_status == S.RESOLVED and to_status == S.IN_PROGRESS:
        return True
    return to_status == S.CLOSED and from_status != S.RESOLVED
