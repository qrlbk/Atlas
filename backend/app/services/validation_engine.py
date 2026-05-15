from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    GroupFlow,
    LessonSlot,
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
from app.services.subject_teacher_match import teacher_covers_subject


def _plan_violation_severity(school_prefs: dict | None) -> str:
    if not school_prefs or not isinstance(school_prefs, dict):
        return "warning"
    if school_prefs.get("plan_compliance") == "error":
        return "error"
    return "warning"


def _preference_lookup(mapping: dict | None, key: int) -> str | None:
    if not mapping or not isinstance(mapping, dict):
        return None
    raw = mapping.get(str(key), mapping.get(key))
    if raw is None:
        return None
    value = str(raw).strip().lower()
    return value or None


def _slot_shift(slot_lesson_number: int, school_prefs: dict | None) -> str:
    boundary = 4
    if school_prefs and isinstance(school_prefs, dict):
        raw = school_prefs.get("shift_boundary_lesson")
        if isinstance(raw, int) and raw > 0:
            boundary = raw
    return "morning" if slot_lesson_number <= boundary else "afternoon"


def validate_schedule(
    db: Session,
    school_id: int,
    candidate: ScheduleItemIn | None = None,
    *,
    pending: Sequence[ScheduleItemIn] | None = None,
    check_curriculum_totals: bool = True,
    ignore_schedule_item_ids: set[int] | None = None,
    replacement_batch: Sequence[tuple[int, ScheduleItemIn]] | None = None,
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
    ignore = ignore_schedule_item_ids or set()
    if ignore:
        items = [it for it in items if it.id not in ignore]

    synthetic: list[ScheduleItem] = []
    if replacement_batch:
        for rid, payload in replacement_batch:
            row = ScheduleItem(id=rid, **payload.model_dump())
            synthetic.append(row)
    if pending:
        synthetic.extend(ScheduleItem(**p.model_dump()) for p in pending)
    if candidate is not None:
        same_slot = [
            it
            for it in items
            if it.class_id == candidate.class_id and it.lesson_slot_id == candidate.lesson_slot_id
        ]
        if len(same_slot) == 1:
            ex = same_slot[0]
            same_body = (
                ex.subject_id == candidate.subject_id
                and ex.teacher_id == candidate.teacher_id
                and ex.classroom_id == candidate.classroom_id
                and bool(ex.is_grouped) == bool(candidate.is_grouped)
                and (ex.group_id or None) == (candidate.group_id or None)
            )
            if same_body:
                pass
            else:
                items = [it for it in items if it.id != ex.id]
                row = ScheduleItem(id=ex.id, **candidate.model_dump())
                synthetic.append(row)
        elif not same_slot:
            synthetic.append(ScheduleItem(**candidate.model_dump()))
        else:
            synthetic.append(ScheduleItem(**candidate.model_dump()))
    if synthetic:
        items = [*items, *synthetic]

    slot_by_id = {s.id: s for s in db.scalars(select(LessonSlot))}
    for it in items:
        if it.lesson_slot is None and it.lesson_slot_id:
            ls = slot_by_id.get(it.lesson_slot_id)
            if ls is not None:
                it.lesson_slot = ls

    issues: list[ValidationIssue] = []

    def _is_grouped_joint_booking(duplicates: list[ScheduleItem]) -> bool:
        if len(duplicates) < 2:
            return False
        if not all(item.is_grouped and item.group_id is not None for item in duplicates):
            return False
        return len({item.group_id for item in duplicates}) == 1

    # Rule 1: teacher can't be in two slots simultaneously.
    teacher_slot = defaultdict(list)
    for item in items:
        teacher_slot[(item.teacher_id, item.lesson_slot_id)].append(item)
    for key, duplicates in teacher_slot.items():
        if len(duplicates) > 1 and not _is_grouped_joint_booking(duplicates):
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
        if len(duplicates) > 1 and not _is_grouped_joint_booking(duplicates):
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
        if not teacher_covers_subject(allowed, subject.name):
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
    # When ``check_curriculum_totals`` is False (e.g. greedy draft placement), skip this rule so
    # ``plan_compliance: error`` does not mark every other under-filled plan row as an error on each
    # single-lesson candidate — which would make incremental placement impossible.
    if check_curriculum_totals:
        plan_rows = list(db.scalars(select(ClassSubjectHours).where(ClassSubjectHours.school_id == school_id)))
    else:
        plan_rows = []
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

    # Rule 10 (KZ): class/teacher shift preferences by scheduling_preferences maps.
    class_shift_map = school_prefs.get("class_shift_map") if isinstance(school_prefs, dict) else None
    teacher_shift_map = school_prefs.get("teacher_shift_map") if isinstance(school_prefs, dict) else None
    for item in items:
        slot = item.lesson_slot
        if not slot:
            continue
        actual_shift = _slot_shift(slot.lesson_number, school_prefs)
        expected_class_shift = _preference_lookup(class_shift_map, item.class_id)
        if expected_class_shift and expected_class_shift != actual_shift:
            issues.append(
                _issue(
                    "CLASS_SHIFT_MISMATCH",
                    "warning",
                    {"class_id": item.class_id, "expected_shift": expected_class_shift, "actual_shift": actual_shift},
                    {"expected_shift": expected_class_shift, "actual_shift": actual_shift},
                    {"lesson_slot_id": item.lesson_slot_id},
                )
            )
        expected_teacher_shift = _preference_lookup(teacher_shift_map, item.teacher_id)
        if expected_teacher_shift and expected_teacher_shift != actual_shift:
            issues.append(
                _issue(
                    "TEACHER_SHIFT_MISMATCH",
                    "warning",
                    {"teacher_id": item.teacher_id, "expected_shift": expected_teacher_shift, "actual_shift": actual_shift},
                    {"expected_shift": expected_teacher_shift, "actual_shift": actual_shift},
                    {"lesson_slot_id": item.lesson_slot_id},
                )
            )

    # Rule 11 (KZ): language stream checks from optional maps.
    class_language_map = school_prefs.get("class_language_map") if isinstance(school_prefs, dict) else None
    subject_language_requirements = (
        school_prefs.get("subject_language_requirements") if isinstance(school_prefs, dict) else None
    )
    if isinstance(subject_language_requirements, dict):
        for item in items:
            subject = subject_cache.get(item.subject_id)
            if not subject:
                continue
            req = subject_language_requirements.get(subject.name)
            if not isinstance(req, list) or not req:
                continue
            allowed_streams = {str(v).strip().lower() for v in req}
            class_stream = _preference_lookup(class_language_map, item.class_id)
            if class_stream and class_stream not in allowed_streams:
                issues.append(
                    _issue(
                        "LANGUAGE_STREAM_MISMATCH",
                        "warning",
                        {"class_id": item.class_id, "subject_id": item.subject_id, "class_stream": class_stream},
                        {"class_stream": class_stream, "subject_name": subject.name},
                        {"lesson_slot_id": item.lesson_slot_id},
                    )
                )

    # Rule 12 (KZ): school-wide event blocks (assemblies, exams, ceremonies).
    if isinstance(school_prefs, dict):
        blocked_raw = school_prefs.get("event_blocked_slot_ids") or []
        blocked_slots = {int(v) for v in blocked_raw if isinstance(v, (int, str)) and str(v).isdigit()}
        event_severity = "error" if school_prefs.get("event_block_severity") == "error" else "warning"
    else:
        blocked_slots = set()
        event_severity = "warning"
    if blocked_slots:
        for item in items:
            if item.lesson_slot_id not in blocked_slots:
                continue
            issues.append(
                _issue(
                    "SCHOOL_EVENT_BLOCK",
                    event_severity,
                    {"lesson_slot_id": item.lesson_slot_id},
                    None,
                    {"lesson_slot_id": item.lesson_slot_id},
                )
            )

    return issues
