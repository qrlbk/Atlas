"""Catalog of validation issue codes: default severity class and weights for scoring."""

from __future__ import annotations

from typing import Any

# Higher weight = worse for optimization / total penalty.
DEFAULT_ISSUE_WEIGHTS: dict[str, float] = {
    "TEACHER_DOUBLE_BOOKING": 10_000.0,
    "CLASSROOM_DOUBLE_BOOKING": 10_000.0,
    "CLASS_DOUBLE_BOOKING": 10_000.0,
    "TEACHER_SUBJECT_MISMATCH": 10_000.0,
    "ROOM_CAPACITY_EXCEEDED": 8_000.0,
    "SPECIAL_ROOM_MISMATCH": 8_000.0,
    "GROUP_CAPACITY_EXCEEDED": 8_000.0,
    "TEACHER_UNAVAILABLE_DAY": 9_000.0,
    "TEACHER_WINDOW_DETECTED": 150.0,
    "TEACHER_LOAD_LIMIT_EXCEEDED": 400.0,
    "PLAN_UNDERFILLED": 300.0,
    "PLAN_OVERFLOW": 350.0,
    "CLASS_SHIFT_MISMATCH": 250.0,
    "TEACHER_SHIFT_MISMATCH": 250.0,
    "LANGUAGE_STREAM_MISMATCH": 200.0,
    "SCHOOL_EVENT_BLOCK": 9_500.0,
    "SUBJECT_TEACHER_INCONSISTENT": 500.0,
}

# issue_code -> "hard" | "soft" (informational; mirrors severity but stable for docs/tools)
ISSUE_KIND: dict[str, str] = {
    "TEACHER_DOUBLE_BOOKING": "hard",
    "CLASSROOM_DOUBLE_BOOKING": "hard",
    "CLASS_DOUBLE_BOOKING": "hard",
    "TEACHER_SUBJECT_MISMATCH": "hard",
    "ROOM_CAPACITY_EXCEEDED": "hard",
    "SPECIAL_ROOM_MISMATCH": "hard",
    "GROUP_CAPACITY_EXCEEDED": "hard",
    "TEACHER_UNAVAILABLE_DAY": "hard",
    "TEACHER_WINDOW_DETECTED": "soft",
    "TEACHER_LOAD_LIMIT_EXCEEDED": "soft",
    "PLAN_UNDERFILLED": "soft",
    "PLAN_OVERFLOW": "soft",
    "CLASS_SHIFT_MISMATCH": "soft",
    "TEACHER_SHIFT_MISMATCH": "soft",
    "LANGUAGE_STREAM_MISMATCH": "soft",
    "SCHOOL_EVENT_BLOCK": "hard",
    "SUBJECT_TEACHER_INCONSISTENT": "soft",
}


def weight_for_issue(issue_code: str, severity: str, school_preferences: dict[str, Any] | None) -> float:
    """Resolve numeric weight: school overrides `issue_weights` map, else defaults, else fallback by severity."""
    prefs = school_preferences or {}
    overrides = prefs.get("issue_weights") or {}
    if issue_code in overrides:
        try:
            return float(overrides[issue_code])
        except (TypeError, ValueError):
            pass
    if issue_code in DEFAULT_ISSUE_WEIGHTS:
        return DEFAULT_ISSUE_WEIGHTS[issue_code]
    return 500.0 if severity == "error" else 100.0


def kind_for_issue(issue_code: str) -> str:
    return ISSUE_KIND.get(issue_code, "soft")
