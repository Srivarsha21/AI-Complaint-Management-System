"""Dashboard summary (every user) and administrator analytics."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.complaint import ComplaintStatus
from app.models.user import User
from app.schemas.analytics import AnalyticsOut, DashboardSummary
from app.services import analytics_service
from app.services.analytics_service import AnalyticsParams

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def analytics_params(
    date_from: date | None = Query(default=None, description="Created on or after this date (IST, inclusive)"),
    date_to: date | None = Query(default=None, description="Created on or before this date (IST, inclusive)"),
    category_id: int | None = Query(default=None, gt=0),
    department_id: int | None = Query(default=None, gt=0),
    status_filter: ComplaintStatus | None = Query(default=None, alias="status"),
) -> AnalyticsParams:
    """Shared query parameters for analytics and reports."""
    return AnalyticsParams(
        date_from=date_from, date_to=date_to, category_id=category_id,
        department_id=department_id, status=status_filter,
    )


@router.get("/summary", response_model=DashboardSummary)
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardSummary:
    """Counts and the 10 latest status changes for the caller's own complaints."""
    return analytics_service.user_summary(db, user)


@router.get("/analytics", response_model=AnalyticsOut)
def analytics(
    params: AnalyticsParams = Depends(analytics_params),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AnalyticsOut:
    """Administrator analytics. Date filters apply to created_at using Asia/Kolkata day boundaries."""
    return analytics_service.analytics(db, admin, params)
