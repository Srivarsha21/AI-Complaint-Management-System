"""Downloadable complaint reports (PDF and Excel)."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dashboard import analytics_params
from app.api.deps import get_current_user
from app.core.rate_limit import client_ip
from app.db.session import get_db
from app.models.user import User
from app.services import report_service
from app.services.analytics_service import AnalyticsParams

router = APIRouter(prefix="/reports", tags=["reports"])


def _download(
    request: Request, user: User, db: Session, params: AnalyticsParams, search: str | None,
    fmt: report_service.ReportFormat,
) -> Response:
    params.search = search
    report = report_service.export(db, user=user, params=params, fmt=fmt, ip_address=client_ip(request))
    return Response(
        content=report.content,
        media_type=report.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{report.filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/complaints.pdf", response_class=Response)
def complaints_pdf(
    request: Request,
    params: AnalyticsParams = Depends(analytics_params),
    search: str | None = Query(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Admins: all complaints. Others: own complaints only. At most 5000 rows (noted when truncated)."""
    return _download(request, user, db, params, search, "pdf")


@router.get("/complaints.xlsx", response_class=Response)
def complaints_xlsx(
    request: Request,
    params: AnalyticsParams = Depends(analytics_params),
    search: str | None = Query(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Admins: all complaints. Others: own complaints only. At most 5000 rows (noted when truncated)."""
    return _download(request, user, db, params, search, "xlsx")
