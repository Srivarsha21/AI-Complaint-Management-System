"""Department and category management (admin) and department staff lookup."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.rate_limit import client_ip
from app.db.session import get_db
from app.models.user import User
from app.repositories import category_repository
from app.schemas.complaint import UserBrief
from app.schemas.department import (
    CategoryAdminOut,
    CategoryCreate,
    CategoryUpdate,
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
)
from app.services import department_service

router = APIRouter(tags=["departments"])


@router.get("/admin/departments", response_model=list[DepartmentOut])
def list_departments(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[DepartmentOut]:
    """All departments, including inactive ones."""
    return [DepartmentOut.model_validate(d) for d in category_repository.list_departments(db)]


@router.post("/admin/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    body: DepartmentCreate, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> DepartmentOut:
    department = department_service.create_department(db, actor=admin, data=body, ip_address=client_ip(request))
    return DepartmentOut.model_validate(department)


@router.patch("/admin/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int,
    body: DepartmentUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentOut:
    department = department_service.update_department(
        db, actor=admin, department_id=department_id, changes=body, ip_address=client_ip(request)
    )
    return DepartmentOut.model_validate(department)


@router.get("/admin/categories", response_model=list[CategoryAdminOut])
def list_categories(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[CategoryAdminOut]:
    """All categories with their department mapping, including inactive ones."""
    return [CategoryAdminOut.model_validate(c) for c in category_repository.list_all(db)]


@router.post("/admin/categories", response_model=CategoryAdminOut, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> CategoryAdminOut:
    category = department_service.create_category(db, actor=admin, data=body, ip_address=client_ip(request))
    return CategoryAdminOut.model_validate(category)


@router.patch("/admin/categories/{category_id}", response_model=CategoryAdminOut)
def update_category(
    category_id: int,
    body: CategoryUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CategoryAdminOut:
    category = department_service.update_category(
        db, actor=admin, category_id=category_id, changes=body, ip_address=client_ip(request)
    )
    return CategoryAdminOut.model_validate(category)


@router.get("/departments/{department_id}/staff", response_model=list[UserBrief])
def list_department_staff(
    department_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[UserBrief]:
    """Active staff of a department (assignment candidates). Admins: any department; staff: their own."""
    staff = department_service.list_department_staff(db, viewer=user, department_id=department_id)
    return [UserBrief.model_validate(u) for u in staff]
