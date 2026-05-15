"""Helpers for school.scheduling_preferences JSON."""

from __future__ import annotations

from typing import Any


def normalize_preferences(raw: dict[str, Any] | None) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def subject_teacher_consistency_mode(prefs: dict[str, Any] | None) -> str:
    raw = normalize_preferences(prefs).get("subject_teacher_consistency", "warn")
    if raw in ("off", "warn", "error"):
        return str(raw)
    return "warn"


def solver_objective_weights(prefs: dict[str, Any] | None) -> dict[str, float]:
    obj = normalize_preferences(prefs).get("solver_objective")
    if not isinstance(obj, dict):
        return {}
    out: dict[str, float] = {}
    for key in ("earlier_slot", "room_stability", "subject_variety"):
        if key in obj:
            try:
                out[key] = float(obj[key])
            except (TypeError, ValueError):
                pass
    return out


def consistency_severity(mode: str) -> str:
    if mode == "error":
        return "error"
    if mode == "warn":
        return "warning"
    return "warning"
