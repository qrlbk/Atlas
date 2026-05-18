from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.db import get_db
from app.models.entities import User, UserRole
from app.schemas.admin import (
    AdminActivateProIn,
    AdminDashboardOut,
    AdminEventsPage,
    AdminExtendTrialIn,
    AdminSchoolCreate,
    AdminSchoolCreateResponse,
    AdminSchoolDetail,
    AdminSchoolListItem,
    AdminSchoolListResponse,
    AdminSchoolPatch,
)
from app.services import admin_service


router = APIRouter(prefix="/admin", tags=["admin"])
admin_user = require_roles(UserRole.admin)


@router.get("/dashboard", response_model=AdminDashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
):
    return admin_service.get_dashboard(db)


@router.get("/schools", response_model=AdminSchoolListResponse)
def list_schools(
    plan: str | None = None,
    health: str | None = None,
    q: str | None = None,
    sort: str = Query("name", pattern="^(name|last_activity|health|trial_ends_at)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
):
    return admin_service.list_schools(
        db,
        plan=plan,
        health=health,
        q=q,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.post("/schools", response_model=AdminSchoolCreateResponse)
def create_school(
    payload: AdminSchoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_user),
):
    return admin_service.create_school_with_manager(db, payload, admin_user_id=current_user.id)


@router.get("/schools/{school_id}", response_model=AdminSchoolDetail)
def get_school(
    school_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
):
    return admin_service.get_school_detail(db, school_id, locale="ru")


@router.patch("/schools/{school_id}", response_model=AdminSchoolListItem)
def patch_school(
    school_id: int,
    payload: AdminSchoolPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_user),
):
    return admin_service.patch_school_admin(
        db, school_id, payload, admin_user_id=current_user.id
    )


@router.get("/schools/{school_id}/events", response_model=AdminEventsPage)
def school_events(
    school_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    event_type: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
):
    return admin_service.list_school_events(
        db, school_id, page=page, page_size=page_size, event_type=event_type
    )


@router.post("/schools/{school_id}/actions/extend-trial", response_model=AdminSchoolListItem)
def extend_trial(
    school_id: int,
    body: AdminExtendTrialIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_user),
):
    return admin_service.extend_trial(
        db, school_id, body.days, admin_user_id=current_user.id
    )


@router.post("/schools/{school_id}/actions/activate-pro", response_model=AdminSchoolListItem)
def activate_pro(
    school_id: int,
    body: AdminActivateProIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_user),
):
    until = datetime.fromisoformat(body.until.replace("Z", "+00:00").replace("+00:00", ""))
    return admin_service.activate_pro(
        db,
        school_id,
        until,
        amount_kzt=body.amount_kzt,
        period_label=body.period_label,
        admin_user_id=current_user.id,
    )
