"""Internal admin console operations."""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import (
    ScheduleSnapshot,
    School,
    SchoolEvent,
    SchoolPlan,
    UsageCounter,
    User,
    UserRole,
)
from app.schemas.admin import (
    AdminAttentionItem,
    AdminDashboardOut,
    AdminEventOut,
    AdminEventsPage,
    AdminReadinessOut,
    AdminSchoolCreate,
    AdminSchoolCreateResponse,
    AdminSchoolDetail,
    AdminSchoolListItem,
    AdminSchoolListResponse,
    AdminSchoolPatch,
    AdminSnapshotOut,
    AdminUsageOut,
    AdminUserOut,
)
from app.services.entitlements import ensure_school_trial, has_pro_access, period_key
from app.services.school_events import log_school_event
from app.services.school_readiness import compute_readiness, invalidate_readiness_cache


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _diagnostic_lines(items: list) -> list[str]:
    lines: list[str] = []
    for item in items:
        if isinstance(item, str):
            lines.append(item)
        elif isinstance(item, dict):
            title = item.get("title") or item.get("message")
            if title:
                lines.append(str(title))
            else:
                lines.append(str(item))
        else:
            lines.append(str(item))
    return lines


def _school_list_item(
    school: School,
    *,
    last_event_at: datetime | None = None,
    manager_count: int = 0,
) -> AdminSchoolListItem:
    plan = school.plan.value if hasattr(school.plan, "value") else str(school.plan)
    publish = (
        school.schedule_publish_state.value
        if hasattr(school.schedule_publish_state, "value")
        else str(school.schedule_publish_state)
    )
    return AdminSchoolListItem(
        id=school.id,
        name=school.name,
        address=school.address,
        plan=plan,
        trial_ends_at=_iso(school.trial_ends_at),
        subscription_ends_at=_iso(school.subscription_ends_at),
        schedule_publish_state=publish,
        created_at=_iso(school.created_at) or "",
        readiness_status=school.readiness_status or "unknown",
        readiness_checked_at=_iso(school.readiness_checked_at),
        last_event_at=_iso(last_event_at),
        pro_access=has_pro_access(school),
        manager_count=manager_count,
    )


def _last_event_subquery():
    return (
        select(
            SchoolEvent.school_id.label("school_id"),
            func.max(SchoolEvent.created_at).label("last_event_at"),
        )
        .group_by(SchoolEvent.school_id)
        .subquery()
    )


def get_dashboard(db: Session) -> AdminDashboardOut:
    now = datetime.utcnow()
    schools = list(db.scalars(select(School)))
    total = len(schools)
    free_count = sum(1 for s in schools if s.plan == SchoolPlan.free)
    pro_count = sum(1 for s in schools if s.plan == SchoolPlan.pro)
    trial_active = sum(1 for s in schools if s.trial_ends_at and s.trial_ends_at > now)
    red_count = sum(1 for s in schools if (s.readiness_status or "unknown") == "red")
    since_24h = now - timedelta(hours=24)
    events_24h = db.scalar(
        select(func.count(SchoolEvent.id)).where(SchoolEvent.created_at >= since_24h)
    ) or 0

    last_events = {
        row.school_id: row.last_event_at
        for row in db.execute(
            select(SchoolEvent.school_id, func.max(SchoolEvent.created_at).label("last_event_at")).group_by(
                SchoolEvent.school_id
            )
        )
    }

    attention: list[AdminAttentionItem] = []
    trial_soon = now + timedelta(days=7)
    inactive_cutoff = now - timedelta(days=30)

    for school in schools:
        reasons: list[str] = []
        last_at = last_events.get(school.id)
        if (school.readiness_status or "unknown") == "red":
            reasons.append("readiness_red")
        if school.trial_ends_at and now < school.trial_ends_at <= trial_soon:
            reasons.append("trial_expiring")
        if last_at is None or last_at < inactive_cutoff:
            reasons.append("inactive")
        if not reasons:
            continue
        plan = school.plan.value if hasattr(school.plan, "value") else str(school.plan)
        attention.append(
            AdminAttentionItem(
                school_id=school.id,
                school_name=school.name,
                reason=",".join(reasons),
                plan=plan,
                readiness_status=school.readiness_status or "unknown",
                trial_ends_at=_iso(school.trial_ends_at),
                last_event_at=_iso(last_at),
            )
        )

    attention.sort(key=lambda a: (0 if "readiness_red" in a.reason else 1, a.school_name))
    return AdminDashboardOut(
        total_schools=total,
        free_count=free_count,
        pro_count=pro_count,
        trial_active_count=trial_active,
        readiness_red_count=red_count,
        events_last_24h=events_24h,
        attention=attention[:10],
    )


def list_schools(
    db: Session,
    *,
    plan: str | None = None,
    health: str | None = None,
    q: str | None = None,
    sort: str = "name",
    page: int = 1,
    page_size: int = 25,
) -> AdminSchoolListResponse:
    last_sq = _last_event_subquery()
    manager_sq = (
        select(User.school_id.label("school_id"), func.count(User.id).label("manager_count"))
        .where(User.role == UserRole.school_manager)
        .group_by(User.school_id)
        .subquery()
    )

    stmt = (
        select(School, last_sq.c.last_event_at, manager_sq.c.manager_count)
        .outerjoin(last_sq, School.id == last_sq.c.school_id)
        .outerjoin(manager_sq, School.id == manager_sq.c.school_id)
    )

    if plan in ("free", "pro"):
        stmt = stmt.where(School.plan == SchoolPlan(plan))
    if health in ("green", "yellow", "red", "unknown"):
        stmt = stmt.where(School.readiness_status == health)
    if q:
        stmt = stmt.where(or_(School.name.ilike(f"%{q}%"), School.address.ilike(f"%{q}%")))

    if sort == "last_activity":
        stmt = stmt.order_by(last_sq.c.last_event_at.desc().nullslast(), School.name)
    elif sort == "health":
        stmt = stmt.order_by(School.readiness_status, School.name)
    elif sort == "trial_ends_at":
        stmt = stmt.order_by(School.trial_ends_at.desc().nullslast(), School.name)
    else:
        stmt = stmt.order_by(School.name)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    offset = max(0, (page - 1) * page_size)
    rows = db.execute(stmt.offset(offset).limit(page_size)).all()

    items = [
        _school_list_item(
            school,
            last_event_at=last_at,
            manager_count=int(mgr_count or 0),
        )
        for school, last_at, mgr_count in rows
    ]
    return AdminSchoolListResponse(items=items, total=total, page=page, page_size=page_size)


def get_school_detail(db: Session, school_id: int, locale: str = "ru") -> AdminSchoolDetail:
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})

    last_at = db.scalar(
        select(func.max(SchoolEvent.created_at)).where(SchoolEvent.school_id == school_id)
    )
    mgr_count = db.scalar(
        select(func.count(User.id)).where(
            User.school_id == school_id,
            User.role == UserRole.school_manager,
        )
    ) or 0

    readiness_result = compute_readiness(db, school, locale)
    readiness = AdminReadinessOut(
        status=readiness_result.status,
        blockers=_diagnostic_lines(readiness_result.blockers),
        recommendations=_diagnostic_lines(readiness_result.recommendations),
        summary=readiness_result.summary,
    )

    users = list(
        db.scalars(select(User).where(User.school_id == school_id).order_by(User.role, User.email))
    )
    usage_rows = list(
        db.scalars(
            select(UsageCounter).where(
                UsageCounter.school_id == school_id,
                UsageCounter.period == period_key(),
            )
        )
    )
    snapshots = list(
        db.scalars(
            select(ScheduleSnapshot)
            .where(ScheduleSnapshot.school_id == school_id)
            .order_by(ScheduleSnapshot.created_at.desc())
            .limit(10)
        )
    )

    db.commit()

    prefs = school.scheduling_preferences or {}
    return AdminSchoolDetail(
        school=_school_list_item(school, last_event_at=last_at, manager_count=int(mgr_count)),
        readiness=readiness,
        admin_notes=prefs.get("admin_notes"),
        manual_pro=bool(prefs.get("manual_pro")),
        users=[
            AdminUserOut(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role.value if hasattr(u.role, "value") else str(u.role),
                school_id=u.school_id,
            )
            for u in users
        ],
        usage=[AdminUsageOut(metric=r.metric, period=r.period, count=r.count) for r in usage_rows],
        snapshots=[
            AdminSnapshotOut(
                id=s.id,
                label=s.label,
                reason=s.reason.value if hasattr(s.reason, "value") else str(s.reason),
                created_at=_iso(s.created_at) or "",
                item_count=len(s.items_json or []),
            )
            for s in snapshots
        ],
    )


def patch_school_admin(
    db: Session,
    school_id: int,
    payload: AdminSchoolPatch,
    *,
    admin_user_id: int | None = None,
) -> AdminSchoolListItem:
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})

    prefs = dict(school.scheduling_preferences or {})
    changed_plan = False

    if payload.name is not None:
        school.name = payload.name
    if payload.address is not None:
        school.address = payload.address
    if payload.plan is not None:
        new_plan = SchoolPlan(payload.plan)
        if school.plan != new_plan:
            changed_plan = True
        school.plan = new_plan
    if payload.trial_ends_at is not None:
        school.trial_ends_at = datetime.fromisoformat(payload.trial_ends_at.replace("Z", "+00:00").replace("+00:00", ""))
    if payload.subscription_ends_at is not None:
        school.subscription_ends_at = datetime.fromisoformat(
            payload.subscription_ends_at.replace("Z", "+00:00").replace("+00:00", "")
        )
    if payload.admin_notes is not None:
        prefs["admin_notes"] = payload.admin_notes
    if payload.manual_pro is not None:
        prefs["manual_pro"] = payload.manual_pro
    if payload.billing is not None:
        billing = dict(prefs.get("billing") or {})
        b = payload.billing
        if b.status is not None:
            billing["status"] = b.status
        if b.amount_kzt is not None:
            billing["amount_kzt"] = b.amount_kzt
        if b.period_label is not None:
            billing["period_label"] = b.period_label
        if b.paid_at is not None:
            billing["paid_at"] = b.paid_at
        if b.notes is not None:
            billing["notes"] = b.notes
        prefs["billing"] = billing

    school.scheduling_preferences = prefs
    invalidate_readiness_cache(school_id)

    if changed_plan:
        log_school_event(
            db,
            school_id=school_id,
            user_id=admin_user_id,
            event_type="admin.plan_changed",
            payload={"plan": school.plan.value},
            commit=False,
        )
    if payload.admin_notes is not None:
        log_school_event(
            db,
            school_id=school_id,
            user_id=admin_user_id,
            event_type="admin.notes_updated",
            payload={},
            commit=False,
        )

    db.commit()
    db.refresh(school)
    return _school_list_item(school)


def _random_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_school_with_manager(
    db: Session,
    payload: AdminSchoolCreate,
    *,
    admin_user_id: int | None = None,
) -> AdminSchoolCreateResponse:
    existing = db.scalar(select(User).where(User.email == payload.manager_email))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"key": "errors.requestValidation"})

    password = _random_password()
    school = School(
        name=payload.name,
        address=payload.address,
        plan=SchoolPlan.free,
        trial_ends_at=datetime.utcnow() + timedelta(days=payload.trial_days),
    )
    ensure_school_trial(school)
    db.add(school)
    db.flush()

    user = User(
        email=payload.manager_email,
        full_name=payload.manager_full_name,
        password_hash=get_password_hash(password),
        role=UserRole.school_manager,
        school_id=school.id,
    )
    db.add(user)

    log_school_event(
        db,
        school_id=school.id,
        user_id=admin_user_id,
        event_type="admin.school_created",
        payload={"manager_email": payload.manager_email, "trial_days": payload.trial_days},
        commit=False,
    )
    db.commit()

    return AdminSchoolCreateResponse(
        school_id=school.id,
        manager_email=payload.manager_email,
        manager_password=password,
    )


def list_school_events(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
    event_type: str | None = None,
) -> AdminEventsPage:
    if db.get(School, school_id) is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})

    base = select(SchoolEvent).where(SchoolEvent.school_id == school_id)
    if event_type:
        base = base.where(SchoolEvent.event_type == event_type)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = max(0, (page - 1) * page_size)
    rows = list(
        db.scalars(base.order_by(SchoolEvent.created_at.desc()).offset(offset).limit(page_size))
    )
    items = [
        AdminEventOut(
            id=e.id,
            event_type=e.event_type,
            created_at=_iso(e.created_at) or "",
            user_id=e.user_id,
            payload=e.payload,
        )
        for e in rows
    ]
    return AdminEventsPage(items=items, total=total, page=page, page_size=page_size)


def extend_trial(
    db: Session,
    school_id: int,
    days: int,
    *,
    admin_user_id: int | None = None,
) -> AdminSchoolListItem:
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})

    base = school.trial_ends_at if school.trial_ends_at and school.trial_ends_at > datetime.utcnow() else datetime.utcnow()
    school.trial_ends_at = base + timedelta(days=days)
    log_school_event(
        db,
        school_id=school_id,
        user_id=admin_user_id,
        event_type="admin.trial_extended",
        payload={"days": days, "trial_ends_at": _iso(school.trial_ends_at)},
        commit=False,
    )
    db.commit()
    db.refresh(school)
    return _school_list_item(school)


def activate_pro(
    db: Session,
    school_id: int,
    until: datetime,
    *,
    amount_kzt: int | None = None,
    period_label: str | None = None,
    admin_user_id: int | None = None,
) -> AdminSchoolListItem:
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})

    school.plan = SchoolPlan.pro
    school.subscription_ends_at = until
    prefs = dict(school.scheduling_preferences or {})
    billing = dict(prefs.get("billing") or {})
    billing["status"] = "paid"
    if amount_kzt is not None:
        billing["amount_kzt"] = amount_kzt
    if period_label is not None:
        billing["period_label"] = period_label
    billing["paid_at"] = datetime.utcnow().isoformat()
    prefs["billing"] = billing
    school.scheduling_preferences = prefs

    log_school_event(
        db,
        school_id=school_id,
        user_id=admin_user_id,
        event_type="admin.pro_activated",
        payload={
            "until": _iso(until),
            "amount_kzt": amount_kzt,
            "period_label": period_label,
        },
        commit=False,
    )
    db.commit()
    db.refresh(school)
    return _school_list_item(school)
