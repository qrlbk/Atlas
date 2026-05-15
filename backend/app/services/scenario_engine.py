"""What-if scenario overlays as draft operations (no DB mutation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import LessonSlot, ScheduleItem, Subject, Teacher
from app.schemas.entities import ScheduleItemIn
from app.services.subject_teacher_match import teacher_covers_subject


@dataclass(frozen=True)
class ScenarioConfig:
    scenario: str
    day_of_week: int | None = None
    teacher_id: int | None = None
    substitute_teacher_id: int | None = None
    original_teacher_id: int | None = None
    max_lesson_number: int | None = None
    classroom_id: int | None = None
    class_id: int | None = None
    lesson_slot_id: int | None = None


def _item_payload(item: ScheduleItem) -> ScheduleItemIn:
    return ScheduleItemIn(
        class_id=item.class_id,
        subject_id=item.subject_id,
        teacher_id=item.teacher_id,
        classroom_id=item.classroom_id,
        lesson_slot_id=item.lesson_slot_id,
        is_grouped=bool(item.is_grouped),
        group_id=item.group_id,
        school_id=item.school_id,
    )


def _slot_matches_day(item: ScheduleItem, slots: dict[int, LessonSlot], day: int | None) -> bool:
    if day is None:
        return True
    slot = slots.get(item.lesson_slot_id)
    return slot is not None and slot.day_of_week == day


def apply_scenario(
    db: Session,
    school_id: int,
    config: ScenarioConfig,
) -> tuple[list[dict], list[str]]:
    """Return draft operations and informational issue codes."""
    items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))
    slots = {row.id: row for row in db.scalars(select(LessonSlot))}
    subjects = {row.id: row for row in db.scalars(select(Subject))}
    teachers = {row.id: row for row in db.scalars(select(Teacher).where(Teacher.school_id == school_id))}
    issues: list[str] = []
    operations: list[dict] = []

    scenario = config.scenario

    if scenario == "teacher_absent":
        if config.teacher_id is None:
            return [], ["TEACHER_NOT_FOUND"]
        return _teacher_absent(items, slots, subjects, teachers, config.teacher_id, config.day_of_week, config.substitute_teacher_id)

    if scenario == "substitute_teacher":
        orig = config.original_teacher_id or config.teacher_id
        sub = config.substitute_teacher_id
        if orig is None or sub is None:
            return [], ["TEACHER_NOT_FOUND"]
        for item in items:
            if item.teacher_id != orig:
                continue
            if not _slot_matches_day(item, slots, config.day_of_week):
                continue
            payload = _item_payload(item).model_copy(update={"teacher_id": sub})
            operations.append({"type": "update", "id": item.id, "payload": payload})
        return operations, issues

    if scenario == "shortened_day":
        if config.day_of_week is None or config.max_lesson_number is None:
            return [], ["SCENARIO_INVALID_CONFIG"]
        for item in items:
            slot = slots.get(item.lesson_slot_id)
            if not slot or slot.day_of_week != config.day_of_week:
                continue
            if slot.lesson_number > config.max_lesson_number:
                operations.append({"type": "delete", "id": item.id})
        return operations, issues

    if scenario == "room_unavailable":
        if config.classroom_id is None:
            return [], ["SCENARIO_INVALID_CONFIG"]
        for item in items:
            if item.classroom_id != config.classroom_id:
                continue
            if not _slot_matches_day(item, slots, config.day_of_week):
                continue
            operations.append({"type": "delete", "id": item.id})
        return operations, issues

    if scenario == "emergency_free":
        if config.class_id is None or config.lesson_slot_id is None:
            return [], ["SCENARIO_INVALID_CONFIG"]
        for item in items:
            if item.class_id == config.class_id and item.lesson_slot_id == config.lesson_slot_id:
                operations.append({"type": "delete", "id": item.id})
        return operations, issues

    return [], ["SCENARIO_UNKNOWN"]


def _teacher_absent(
    items: list[ScheduleItem],
    slots: dict[int, LessonSlot],
    subjects: dict[int, Subject],
    teachers: dict[int, Teacher],
    absent_id: int,
    day_of_week: int | None,
    substitute_id: int | None,
) -> tuple[list[dict], list[str]]:
    if absent_id not in teachers:
        return [], ["TEACHER_NOT_FOUND"]
    operations: list[dict] = []
    issues: list[str] = []
    for item in items:
        if item.teacher_id != absent_id:
            continue
        if not _slot_matches_day(item, slots, day_of_week):
            continue
        subject = subjects.get(item.subject_id)
        if substitute_id is not None:
            sub = teachers.get(substitute_id)
            if sub and subject and teacher_covers_subject(sub.subjects, subject.name):
                payload = _item_payload(item).model_copy(update={"teacher_id": substitute_id})
                operations.append({"type": "update", "id": item.id, "payload": payload})
                continue
        operations.append({"type": "delete", "id": item.id})
        issues.append("SUBSTITUTE_NOT_FOUND")
    return operations, sorted(set(issues))
