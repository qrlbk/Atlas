"""Human-readable diagnostics from validation and solver codes."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.i18n import localize_issue, t
from app.services.validation_engine import validate_schedule

CP_SAT_CODE_KEYS = {
    "NO_QUALIFIED_TEACHER": "diagnostics.NO_QUALIFIED_TEACHER",
    "NO_LESSON_SLOTS": "diagnostics.NO_LESSON_SLOTS",
    "NO_CLASSROOMS": "diagnostics.NO_CLASSROOMS",
    "TEACHER_LOAD_LIMIT_EXCEEDED": "diagnostics.TEACHER_LOAD_LIMIT_EXCEEDED",
    "TEACHER_UNAVAILABLE_DAY": "diagnostics.TEACHER_UNAVAILABLE_DAY",
    "TEACHER_DOUBLE_BOOKING": "diagnostics.TEACHER_DOUBLE_BOOKING",
    "ROOM_CAPACITY_EXCEEDED": "diagnostics.ROOM_CAPACITY_EXCEEDED",
    "CLASS_SLOT_OCCUPIED": "diagnostics.CLASS_SLOT_OCCUPIED",
    "CP_SAT_NO_FEASIBLE_ASSIGNMENT": "diagnostics.CP_SAT_NO_FEASIBLE_ASSIGNMENT",
}


def diagnostic_message(locale: str, code: str, **params: object) -> str:
    key = CP_SAT_CODE_KEYS.get(code, f"diagnostics.{code}")
    msg = t(locale, key, **params)
    if msg == key and code.startswith("validation."):
        return t(locale, code, **params)
    return msg


def diagnostics_from_unplaced(unplaced_details: list[dict], locale: str, limit: int = 10) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in unplaced_details[:limit]:
        reasons = row.get("reasons") or row.get("diagnostic_codes") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        code = reasons[0] if reasons else "CP_SAT_NO_FEASIBLE_ASSIGNMENT"
        class_name = row.get("class_name", "")
        subject_name = row.get("subject_name", "")
        detail = diagnostic_message(locale, str(code))
        if class_name or subject_name:
            detail = f"{class_name} / {subject_name}: {detail}".strip(" /")
        out.append(
            {
                "title": subject_name or class_name or t(locale, "diagnostics.unplacedTitle"),
                "detail": detail,
                "severity": "error",
            }
        )
    return out


def top_validation_blockers(db: Session, school_id: int, locale: str, limit: int = 3) -> list[dict[str, str]]:
    issues = validate_schedule(db, school_id)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    ranked = errors + warnings
    code_counts = Counter(i.issue_code for i in ranked)
    blockers: list[dict[str, str]] = []
    for code, _count in code_counts.most_common(limit):
        sample = next(i for i in ranked if i.issue_code == code)
        message, fix = localize_issue(code, locale, **(sample.message_params or {}))
        blockers.append(
            {
                "title": message,
                "detail": fix or "",
                "action_hint": fix or t(locale, "readiness.openSchedule"),
                "severity": sample.severity,
            }
        )
    return blockers


def merge_diagnostics(*groups: list[dict[str, str]], limit: int = 3) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for group in groups:
        for item in group:
            key = item.get("title", "")
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= limit:
                return out
    return out
