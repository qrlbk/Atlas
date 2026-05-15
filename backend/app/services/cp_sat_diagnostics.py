"""Diagnostic helpers for CP-SAT placement pre-filtering."""

from __future__ import annotations

from collections import Counter

from app.models.entities import Classroom, LessonSlot, Subject, Teacher
from app.services.subject_teacher_match import teacher_covers_subject


def diagnose_empty_feasible(
    *,
    subject: Subject,
    teachers: list[Teacher],
    slots: list[LessonSlot],
    rooms: list[Classroom],
    frozen_slot_ids: set[int],
    teacher_weekly_count: Counter[int],
    teacher_slot_count: Counter[tuple[int, int]],
    class_slot_blocked: bool,
    total_students: int,
) -> list[str]:
    """Sample reasons why no (teacher, slot, room) tuple passed pre-filter."""
    reasons: list[str] = []
    qualified = [t for t in teachers if teacher_covers_subject(t.subjects, subject.name)]
    if not qualified:
        return ["NO_QUALIFIED_TEACHER"]
    if class_slot_blocked and not any(
        s.id not in frozen_slot_ids for s in slots
    ):
        reasons.append("CLASS_SLOT_OCCUPIED")
    open_slots = [s for s in slots if s.id not in frozen_slot_ids]
    if not open_slots:
        reasons.append("NO_LESSON_SLOTS")
        return reasons[:3]
    if not rooms:
        reasons.append("NO_CLASSROOMS")
        return reasons[:3]

    any_teacher_cap = False
    any_teacher_day = False
    any_room = False
    any_slot_teacher = False
    for slot in open_slots:
        slot_ok = False
        for teacher in qualified:
            if teacher.weekly_load_limit > 0 and teacher_weekly_count[teacher.id] >= teacher.weekly_load_limit:
                any_teacher_cap = True
                continue
            if slot.day_of_week in (teacher.unavailable_days or []):
                any_teacher_day = True
                continue
            if teacher_slot_count[(teacher.id, slot.id)] >= 1:
                any_slot_teacher = True
                continue
            for room in rooms:
                if subject.requires_special_room and subject.required_specialization is not None:
                    if room.specialization != subject.required_specialization:
                        any_room = True
                        continue
                if room.capacity < total_students:
                    any_room = True
                    continue
                slot_ok = True
                break
            if slot_ok:
                break
        if slot_ok:
            return ["CP_SAT_NO_FEASIBLE_ASSIGNMENT"]
    if any_teacher_cap:
        reasons.append("TEACHER_LOAD_LIMIT_EXCEEDED")
    if any_teacher_day:
        reasons.append("TEACHER_UNAVAILABLE_DAY")
    if any_slot_teacher:
        reasons.append("TEACHER_DOUBLE_BOOKING")
    if any_room:
        reasons.append("ROOM_CAPACITY_EXCEEDED")
    if class_slot_blocked:
        reasons.append("CLASS_SLOT_OCCUPIED")
    if not reasons:
        reasons.append("CP_SAT_NO_FEASIBLE_ASSIGNMENT")
    return reasons[:3]
