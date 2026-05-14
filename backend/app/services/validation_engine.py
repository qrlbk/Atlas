from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    GroupFlow,
    School,
    ScheduleItem,
    StudentClass,
    Subject,
    Teacher,
)
from app.i18n import localize_issue
from app.schemas.entities import ScheduleItemIn
from app.schemas.validation import ValidationIssue
from app.services.constraint_catalog import weight_for_issue


def _plan_violation_severity(school_prefs: dict | None) -> str:
    if not school_prefs or not isinstance(school_prefs, dict):
        return "warning"
    if school_prefs.get("plan_compliance") == "error":
        return "error"
    return "warning"


def validate_schedule(
    db: Session,
    school_id: int,
    candidate: ScheduleItemIn | None = None,
    *,
    pending: Sequence[ScheduleItemIn] | None = None,
) -> list[ValidationIssue]:
    school_row = db.get(School, school_id)
    school_prefs = school_row.scheduling_preferences if school_row else None

    def _issue(
        code: str,
        severity: str,
        entity_refs: dict,
        message_params: dict | None = None,
        slot_ref: dict | None = None,
        suggested_fix: str | None = None,
    ) -> ValidationIssue:
        message, default_fix = localize_issue(code, "en", **(message_params or {}))
        return ValidationIssue(
            issue_code=code,
            severity=severity,
            message=message,
            message_params=message_params or None,
            entity_refs=entity_refs,
            slot_ref=slot_ref,
            suggested_fix=suggested_fix or default_fix,
            weight=weight_for_issue(code, severity, school_prefs),
        )

    items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))
    synthetic: list[ScheduleItem] = []
    if pending:
        synthetic.extend(ScheduleItem(**p.model_dump()) for p in pending)
    if candidate is not None:
        synthetic.append(ScheduleItem(**candidate.model_dump()))
    if synthetic:
        items = [*items, *synthetic]

    issues: list[ValidationIssue] = []

    # Rule 1: teacher can't be in two slots simultaneously.
    teacher_slot = defaultdict(list)
    for item in items:
        teacher_slot[(item.teacher_id, item.lesson_slot_id)].append(item)
    for key, duplicates in teacher_slot.items():
        if len(duplicates) > 1:
            teacher_id, slot_id = key
            issues.append(
                _issue(
                    "TEACHER_DOUBLE_BOOKING",
                    "error",
                    {"teacher_id": teacher_id},
                    None,
                    {"lesson_slot_id": slot_id},
                )
            )

    # Rule 2: classroom can't host two classes simultaneously.
    room_slot = defaultdict(list)
    for item in items:
        room_slot[(item.classroom_id, item.lesson_slot_id)].append(item)
    for key, duplicates in room_slot.items():
        if len(duplicates) > 1:
            room_id, slot_id = key
            issues.append(
                _issue(
                    "CLASSROOM_DOUBLE_BOOKING",
                    "error",
                    {"classroom_id": room_id},
                    None,
                    {"lesson_slot_id": slot_id},
                )
            )

    class_cache = {c.id: c for c in db.scalars(select(StudentClass).where(StudentClass.school_id == school_id))}
    room_cache = {r.id: r for r in db.scalars(select(Classroom).where(Classroom.school_id == school_id))}
    subject_cache = {s.id: s for s in db.scalars(select(Subject))}
    teacher_cache = {t.id: t for t in db.scalars(select(Teacher).where(Teacher.school_id == school_id))}
    flow_cache = {f.id: f for f in db.scalars(select(GroupFlow).where(GroupFlow.school_id == school_id))}

    # Rule 2b: a class cannot have two lessons in the same slot.
    class_slot = defaultdict(list)
    for item in items:
        class_slot[(item.class_id, item.lesson_slot_id)].append(item)
    for key, duplicates in class_slot.items():
        if len(duplicates) > 1:
            class_id, slot_id = key
            issues.append(
                _issue(
                    "CLASS_DOUBLE_BOOKING",
                    "error",
                    {"class_id": class_id},
                    None,
                    {"lesson_slot_id": slot_id},
                )
            )

    # Rule 2c: teacher must be qualified for the subject (name match with teacher.subjects).
    for item in items:
        subject = subject_cache.get(item.subject_id)
        teacher = teacher_cache.get(item.teacher_id)
        if not subject or not teacher:
            continue
        allowed = teacher.subjects or []
        if subject.name not in allowed:
            issues.append(
                _issue(
                    "TEACHER_SUBJECT_MISMATCH",
                    "error",
                    {"teacher_id": teacher.id, "subject_id": subject.id},
                    {"subject_name": subject.name},
                    {"lesson_slot_id": item.lesson_slot_id},
                )
            )

    # Rule 3: class size must fit room capacity.
    for item in items:
        c = class_cache.get(item.class_id)
        room = room_cache.get(item.classroom_id)
        if c and room and c.students_count > room.capacity:
            issues.append(
                _issue(
                    "ROOM_CAPACITY_EXCEEDED",
                    "error",
                    {"class_id": c.id, "classroom_id": room.id},
                    {"students_count": c.students_count, "room_capacity": room.capacity},
                    {"lesson_slot_id": item.lesson_slot_id},
                )
            )

    # Rule 4: special subject requires matching room specialization.
    for item in items:
        subject = subject_cache.get(item.subject_id)
        room = room_cache.get(item.classroom_id)
        if not subject or not room:
            continue
        if subject.requires_special_room and subject.required_specialization != room.specialization:
            issues.append(
                _issue(
                    "SPECIAL_ROOM_MISMATCH",
                    "error",
                    {"subject_id": subject.id, "classroom_id": room.id},
                    None,
                    {"lesson_slot_id": item.lesson_slot_id},
                )
            )

    # Rule 5: grouped flow sum capacity check.
    flow_slot_members = defaultdict(list)
    for item in items:
        if item.is_grouped and item.group_id is not None:
            flow_slot_members[(item.group_id, item.lesson_slot_id, item.classroom_id)].append(item)
    for (group_id, slot_id, room_id), group_items in flow_slot_members.items():
        flow = flow_cache.get(group_id)
        room = room_cache.get(room_id)
        if not flow or not room:
            continue
        total_students = sum(class_cache.get(cid).students_count for cid in flow.combined_classes if class_cache.get(cid))
        if total_students > room.capacity:
            issues.append(
                _issue(
                    "GROUP_CAPACITY_EXCEEDED",
                    "error",
                    {"group_id": group_id, "classroom_id": room_id},
                    {"total_students": total_students, "room_capacity": room.capacity},
                    {"lesson_slot_id": slot_id},
                )
            )

    # Rule 6: teacher gaps ("windows") warnings.
    teacher_day_slots = defaultdict(list)
    slot_day_map = {}
    for item in items:
        slot_day_map[item.lesson_slot_id] = item.lesson_slot.day_of_week if item.lesson_slot else None
    for item in items:
        teacher = teacher_cache.get(item.teacher_id)
        slot = item.lesson_slot
        if not teacher or not slot:
            continue
        teacher_day_slots[(teacher.id, slot.day_of_week)].append(slot.lesson_number)
    for (teacher_id, day), lesson_numbers in teacher_day_slots.items():
        uniq = sorted(set(lesson_numbers))
        if len(uniq) >= 3:
            for index in range(1, len(uniq) - 1):
                if uniq[index] - uniq[index - 1] > 1 or uniq[index + 1] - uniq[index] > 1:
                    issues.append(
                        _issue(
                            "TEACHER_WINDOW_DETECTED",
                            "warning",
                            {"teacher_id": teacher_id, "day_of_week": day},
                            None,
                        )
                    )
                    break

    # Rule 7: teacher unavailable days.
    for item in items:
        teacher = teacher_cache.get(item.teacher_id)
        slot = item.lesson_slot
        if not teacher or not slot:
            continue
        if slot.day_of_week in (teacher.unavailable_days or []):
            issues.append(
                _issue(
                    "TEACHER_UNAVAILABLE_DAY",
                    "error",
                    {"teacher_id": teacher.id, "day_of_week": slot.day_of_week},
                    None,
                    {"lesson_slot_id": item.lesson_slot_id},
                )
            )

    # Rule 8: teacher weekly load limit.
    teacher_load = defaultdict(int)
    for item in items:
        teacher_load[item.teacher_id] += 1
    for teacher_id, load in teacher_load.items():
        teacher = teacher_cache.get(teacher_id)
        if not teacher:
            continue
        if teacher.weekly_load_limit > 0 and load > teacher.weekly_load_limit:
            issues.append(
                _issue(
                    "TEACHER_LOAD_LIMIT_EXCEEDED",
                    "warning",
                    {"teacher_id": teacher_id},
                    {"load": load, "weekly_limit": teacher.weekly_load_limit},
                )
            )

    # Rule 9: curriculum plan vs scheduled lesson counts per class/subject.
    plan_rows = list(db.scalars(select(ClassSubjectHours).where(ClassSubjectHours.school_id == school_id)))
    if plan_rows:
        actual_by_pair: dict[tuple[int, int], int] = defaultdict(int)
        for item in items:
            actual_by_pair[(item.class_id, item.subject_id)] += 1
        for plan in plan_rows:
            actual = actual_by_pair.get((plan.class_id, plan.subject_id), 0)
            plan_sev = _plan_violation_severity(school_prefs)
            if actual < plan.hours_per_week:
                issues.append(
                    _issue(
                        "PLAN_UNDERFILLED",
                        plan_sev,
                        {"class_id": plan.class_id, "subject_id": plan.subject_id, "plan_id": plan.id},
                        {"actual": actual, "plan_hours": plan.hours_per_week},
                    )
                )
            elif actual > plan.hours_per_week:
                issues.append(
                    _issue(
                        "PLAN_OVERFLOW",
                        plan_sev,
                        {"class_id": plan.class_id, "subject_id": plan.subject_id, "plan_id": plan.id},
                        {"actual": actual, "plan_hours": plan.hours_per_week},
                    )
                )

    return issues
