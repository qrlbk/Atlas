"""School readiness (Health) score — GREEN / YELLOW / RED / UNKNOWN."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.i18n import t
from app.models.entities import School
from app.services.entitlements import ensure_school_trial, has_pro_access
from app.services.human_diagnostics import merge_diagnostics, top_validation_blockers
from app.services.plan_status import compute_schedule_plan_status
from app.services.school_events import log_school_event
from app.services.validation_engine import validate_schedule

_CACHE: dict[int, tuple[float, dict]] = {}
_CACHE_TTL = 45.0


@dataclass
class ReadinessResult:
    status: str
    blockers: list[dict]
    recommendations: list[str]
    summary: dict


def _plan_gap_blocker(plan_data, locale: str) -> dict | None:
    under_rows = [r for r in plan_data.rows_out if getattr(r, "under", False)]
    if not under_rows:
        return None
    worst = max(under_rows, key=lambda r: r.planned_hours - r.scheduled_hours)
    gap = worst.planned_hours - worst.scheduled_hours
    return {
        "title": t(locale, "readiness.planGapTitle", class_name=worst.class_name, subject=worst.subject_name),
        "detail": t(locale, "readiness.planGapDetail", hours=gap),
        "action_hint": t(locale, "readiness.openCurriculum"),
        "severity": "warning",
    }


def _teacher_overload_blocker(db: Session, school_id: int, locale: str) -> dict | None:
    from collections import defaultdict

    from sqlalchemy import select

    from app.models.entities import ScheduleItem, Teacher

    teachers = list(db.scalars(select(Teacher).where(Teacher.school_id == school_id)))
    items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))
    counts: dict[int, int] = defaultdict(int)
    for item in items:
        counts[item.teacher_id] += 1
    rows = [
        {"teacher_name": t.full_name, "current_load": counts[t.id], "weekly_limit": t.weekly_load_limit}
        for t in teachers
    ]
    overloaded = [r for r in rows if r["weekly_limit"] > 0 and r["current_load"] > r["weekly_limit"]]
    if not overloaded:
        return None
    worst = max(overloaded, key=lambda r: r["current_load"] - r["weekly_limit"])
    return {
        "title": t(locale, "readiness.teacherOverloadTitle", name=worst["teacher_name"]),
        "detail": t(
            locale,
            "readiness.teacherOverloadDetail",
            current=worst["current_load"],
            limit=worst["weekly_limit"],
        ),
        "action_hint": t(locale, "readiness.openSchedule"),
        "severity": "warning",
    }


def compute_readiness(db: Session, school: School, locale: str, *, use_cache: bool = True) -> ReadinessResult:
    ensure_school_trial(school)
    school_id = school.id
    now = time.time()
    if use_cache and school_id in _CACHE:
        ts, cached = _CACHE[school_id]
        if now - ts < _CACHE_TTL:
            return ReadinessResult(**cached)

    issues = validate_schedule(db, school_id)
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    plan_data = compute_schedule_plan_status(db, school_id)
    summary = plan_data.summary
    fill_rate = summary.fill_rate
    lesson_count = plan_data.lesson_count
    plan_row_count = summary.plan_row_count

    if plan_row_count == 0 or lesson_count == 0:
        status = "unknown"
    elif error_count > 0 or fill_rate < 0.80 or summary.classes_without_plan_count > 0:
        status = "red"
    elif warning_count > 0 or fill_rate < 0.95 or summary.rows_under > 0:
        status = "yellow"
    else:
        status = "green"

    val_blockers = top_validation_blockers(db, school_id, locale, limit=2)
    gap_blocker = _plan_gap_blocker(plan_data, locale)
    teacher_blocker = _teacher_overload_blocker(db, school_id, locale)
    extra = [b for b in (gap_blocker, teacher_blocker) if b]
    blockers = merge_diagnostics(val_blockers, extra, limit=3)

    recommendations: list[str] = []
    if status == "unknown":
        recommendations.append(t(locale, "readiness.recOnboarding"))
    if summary.rows_under > 0:
        recommendations.append(t(locale, "readiness.recPlanHours", count=summary.rows_under))
    if error_count > 0:
        recommendations.append(t(locale, "readiness.recFixErrors"))
    if status == "red" and not has_pro_access(school):
        recommendations.append(t(locale, "readiness.recTryPro"))
    recommendations = recommendations[:3]

    result = ReadinessResult(
        status=status,
        blockers=blockers,
        recommendations=recommendations,
        summary={
            "error_count": error_count,
            "warning_count": warning_count,
            "fill_rate": fill_rate,
            "plan_row_count": plan_row_count,
            "lesson_count": lesson_count,
            "rows_under": summary.rows_under,
            "classes_without_plan_count": summary.classes_without_plan_count,
            "plan": school.plan.value if hasattr(school.plan, "value") else str(school.plan),
            "pro_access": has_pro_access(school),
            "trial_ends_at": school.trial_ends_at.isoformat() if school.trial_ends_at else None,
            "onboarding_completed": bool((school.scheduling_preferences or {}).get("onboarding_completed")),
            "publish_state": (
                school.schedule_publish_state.value
                if hasattr(school.schedule_publish_state, "value")
                else str(school.schedule_publish_state)
            ),
        },
    )
    payload = {
        "status": result.status,
        "blockers": result.blockers,
        "recommendations": result.recommendations,
        "summary": result.summary,
    }
    _CACHE[school_id] = (now, payload)
    school.readiness_status = status
    school.readiness_checked_at = datetime.utcnow()
    db.add(school)
    log_school_event(db, school_id=school_id, event_type="readiness.checked", payload={"status": status}, commit=False)
    return result


def invalidate_readiness_cache(school_id: int) -> None:
    _CACHE.pop(school_id, None)
