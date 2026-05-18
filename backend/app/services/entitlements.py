"""School plan capabilities and usage limits."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import School, SchoolPlan, UsageCounter

SLOT_SUGGESTION_DAILY_FREE = 5
MANAGER_SEATS_FREE = 2
MANAGER_SEATS_PRO = 5

REVIEW_CODES = frozenset({"duplicate", "missing_ref", "not_found", "invalid_ref"})


def ensure_school_trial(school: School) -> None:
    if school.trial_ends_at is None and school.plan == SchoolPlan.free:
        school.trial_ends_at = datetime.utcnow() + timedelta(days=14)


def has_pro_access(school: School) -> bool:
    prefs = school.scheduling_preferences or {}
    if prefs.get("manual_pro"):
        return True
    if school.plan == SchoolPlan.pro:
        if school.subscription_ends_at is None or school.subscription_ends_at > datetime.utcnow():
            return True
    if school.trial_ends_at and school.trial_ends_at > datetime.utcnow():
        return True
    return False


def can_use_capability(school: School, capability: str) -> bool:
    pro = has_pro_access(school)
    free_caps = {
        "validation",
        "readiness",
        "manual_crud",
        "diagnostics_preview",
        "export_pdf_simple",
    }
    if capability in free_caps:
        return True
    if capability == "diagnostics_full":
        return pro
    if capability == "slot_suggestions":
        return True
    if capability in {
        "solver",
        "generate_class",
        "scenario",
        "export_xlsx",
        "export_pdf_full",
        "import_schedule",
        "snapshot_restore_all",
    }:
        return pro
    return pro


def period_key() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def increment_usage(db: Session, school_id: int, metric: str) -> int:
    period = period_key()
    row = db.scalar(
        select(UsageCounter).where(
            UsageCounter.school_id == school_id,
            UsageCounter.metric == metric,
            UsageCounter.period == period,
        )
    )
    if row is None:
        row = UsageCounter(school_id=school_id, metric=metric, period=period, count=0)
        db.add(row)
    row.count += 1
    db.flush()
    return row.count


def get_usage_count(db: Session, school_id: int, metric: str) -> int:
    period = period_key()
    row = db.scalar(
        select(UsageCounter).where(
            UsageCounter.school_id == school_id,
            UsageCounter.metric == metric,
            UsageCounter.period == period,
        )
    )
    return row.count if row else 0


def check_slot_suggestion_allowed(db: Session, school: School) -> None:
    if has_pro_access(school):
        return
    count = get_usage_count(db, school.id, "slot_suggestion")
    if count >= SLOT_SUGGESTION_DAILY_FREE:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"key": "errors.upgradeRequired", "params": {"capability": "slot_suggestions"}},
        )


def require_capability(db: Session, school: School, capability: str) -> None:
    ensure_school_trial(school)
    if capability == "solver" and not has_pro_access(school):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"key": "errors.upgradeRequired", "params": {"capability": capability}},
        )
    if not can_use_capability(school, capability):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"key": "errors.upgradeRequired", "params": {"capability": capability}},
        )


def is_onboarding_completed(school: School) -> bool:
    prefs = school.scheduling_preferences or {}
    return bool(prefs.get("onboarding_completed"))


def set_onboarding_completed(db: Session, school: School) -> None:
    prefs = dict(school.scheduling_preferences or {})
    prefs["onboarding_completed"] = True
    school.scheduling_preferences = prefs
    db.add(school)


def onboarding_import_modes() -> dict[str, str]:
    from app.schemas.imports import (
        SHEET_CLASSES,
        SHEET_CLASSROOMS,
        SHEET_CURRICULUM,
        SHEET_GROUP_FLOWS,
        SHEET_LESSON_SLOTS,
        SHEET_SCHEDULE,
        SHEET_SUBJECTS,
        SHEET_TEACHERS,
        ImportMode,
    )

    return {
        SHEET_SUBJECTS: ImportMode.upsert.value,
        SHEET_LESSON_SLOTS: ImportMode.upsert.value,
        SHEET_CLASSES: ImportMode.upsert.value,
        SHEET_TEACHERS: ImportMode.upsert.value,
        SHEET_CLASSROOMS: ImportMode.upsert.value,
        SHEET_GROUP_FLOWS: ImportMode.upsert.value,
        SHEET_CURRICULUM: ImportMode.upsert.value,
        SHEET_SCHEDULE: ImportMode.skip.value,
    }


def import_issue_buckets(issues: list) -> dict[str, int]:
    needs_review = 0
    auto_ok = 0
    for issue in issues:
        code = getattr(issue, "code", "") or ""
        if code in REVIEW_CODES:
            needs_review += 1
        else:
            auto_ok += 1
    return {"needs_review": needs_review, "auto_ok": auto_ok, "total": len(issues)}
