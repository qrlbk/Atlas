"""Product endpoints: readiness, publish, snapshots."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_scope, get_current_user, require_roles
from app.core.db import get_db
from app.i18n import resolve_locale
from app.models.entities import SchedulePublishState, School, User, UserRole
from app.schemas.readiness import ScheduleSnapshotOut, SchoolReadinessOut
from app.services.entitlements import has_pro_access, require_capability
from app.services.schedule_snapshots import create_schedule_snapshot, list_snapshots, restore_schedule_snapshot
from app.services.school_events import log_school_event
from app.services.school_readiness import compute_readiness, invalidate_readiness_cache

router = APIRouter(tags=["product"])
manager_or_admin = require_roles(UserRole.admin, UserRole.school_manager)


@router.get("/schools/{school_id}/readiness", response_model=SchoolReadinessOut)
def school_readiness(
    school_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    locale = resolve_locale(request)
    result = compute_readiness(db, school, locale)
    db.commit()
    return SchoolReadinessOut(
        status=result.status,
        blockers=result.blockers,
        recommendations=result.recommendations,
        summary=result.summary,
    )


@router.post("/schools/{school_id}/schedule/publish")
def publish_schedule(
    school_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    locale = resolve_locale(request)
    readiness = compute_readiness(db, school, locale, use_cache=False)
    if readiness.status == "red":
        raise HTTPException(status_code=409, detail={"key": "errors.schedulePublishBlocked"})
    create_schedule_snapshot(
        db,
        school_id=school_id,
        reason="pre_publish",
        label="Before publish",
        user_id=current_user.id,
        commit=False,
    )
    school.schedule_publish_state = SchedulePublishState.published
    school.published_at = datetime.utcnow()
    log_school_event(
        db,
        school_id=school_id,
        user_id=current_user.id,
        event_type="schedule.published",
        payload={"status": readiness.status},
        commit=False,
    )
    invalidate_readiness_cache(school_id)
    db.commit()
    return {"ok": True, "publish_state": "published", "published_at": school.published_at.isoformat()}


@router.get("/schools/{school_id}/schedule/snapshots", response_model=list[ScheduleSnapshotOut])
def get_schedule_snapshots(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    snaps = list_snapshots(db, school_id)
    pro = False
    school = db.get(School, school_id)
    if school:
        pro = has_pro_access(school)
    if not pro and len(snaps) > 1:
        snaps = snaps[:1]
    return [
        ScheduleSnapshotOut(
            id=s.id,
            school_id=s.school_id,
            label=s.label,
            reason=s.reason,
            created_at=s.created_at.isoformat(),
            item_count=len(s.items_json),
        )
        for s in snaps
    ]


@router.post("/schools/{school_id}/schedule/snapshots/{snapshot_id}/restore")
def restore_snapshot(
    school_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    snaps = list_snapshots(db, school_id)
    if not has_pro_access(school) and snaps and snapshot_id != snaps[0].id:
        require_capability(db, school, "snapshot_restore_all")
    try:
        restore_schedule_snapshot(db, school_id=school_id, snapshot_id=snapshot_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"}) from exc
    log_school_event(
        db,
        school_id=school_id,
        user_id=current_user.id,
        event_type="snapshot.restored",
        payload={"snapshot_id": snapshot_id},
        commit=False,
    )
    invalidate_readiness_cache(school_id)
    db.commit()
    return {"ok": True}
