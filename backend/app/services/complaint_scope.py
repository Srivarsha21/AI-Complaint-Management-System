"""Single place that decides which complaints a user may see in dashboards and reports.

Administrators see everything; department staff see their department's
complaints (matching the complaint list); everyone else sees only the
complaints they filed. New roles are added here only.
"""

from app.models.user import User, UserRole
from app.repositories.analytics_repository import ComplaintScope


def scope_for(user: User) -> ComplaintScope:
    if user.role == UserRole.ADMIN:
        return ComplaintScope()
    if user.role == UserRole.STAFF and user.department_id is not None:
        return ComplaintScope(department_id=user.department_id)
    return ComplaintScope(owner_id=user.id)


def has_full_access(user: User) -> bool:
    return scope_for(user) == ComplaintScope()


def may_see_complainant_names(user: User) -> bool:
    """Complainant names appear only in administrator exports."""
    return user.role == UserRole.ADMIN
