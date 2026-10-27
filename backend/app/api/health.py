"""Liveness and readiness checks."""

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health() -> dict:
    """Liveness: the process is up and serving requests."""
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/health/db")
def health_db(response: Response, db: Session = Depends(get_db)) -> dict:
    """Readiness: the database is reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report any connection failure as unavailable
        logger.error("database health check failed: %s", exc.__class__.__name__)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "unreachable"}
    return {"status": "ok", "database": "reachable"}
