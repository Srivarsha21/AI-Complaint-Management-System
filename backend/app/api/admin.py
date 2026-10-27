"""Administrator-only endpoints for user management and the audit trail."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.rate_limit import client_ip
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories import audit_repository, user_repository
from app.schemas.audit import AuditLogList, AuditLogOut
from app.schemas.user import AdminUserUpdate, UserList, UserOut
from app.services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserList)
def list_users(
    search: str | None = Query(default=None, max_length=100),
    role: UserRole | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserList:
    items, total = user_repository.list_users(db, search=search, role=role, limit=limit, offset=offset)
    return UserList(items=[UserOut.model_validate(u) for u in items], total=total)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = user_service.admin_update_user(
        db, actor=admin, user_id=user_id, changes=body, ip_address=client_ip(request)
    )
    return UserOut.model_validate(user)


@router.get("/audit-logs", response_model=AuditLogList)
def list_audit_logs(
    action: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AuditLogList:
    items, total = audit_repository.list_entries(db, action=action, limit=limit, offset=offset)
    return AuditLogList(items=[AuditLogOut.model_validate(e) for e in items], total=total)
