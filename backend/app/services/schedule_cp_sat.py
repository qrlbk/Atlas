"""CP-SAT based draft generation for whole-school missing curriculum hours."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    GroupFlow,
    LessonSlot,
    ScheduleItem,
    School,
    StudentClass,
    Subject,
    Teacher,
)
from app.schemas.entities import ScheduleItemIn
from app.services.cp_sat_diagnostics import diagnose_empty_feasible
from app.services.scheduling_preferences import (
    solver_objective_weights,
    subject_teacher_consistency_mode,
)
from app.services.subject_teacher_match import teacher_covers_subject


@dataclass(frozen=True)
class _PlacementUnit:
    unit_id: int
    subject_id: int
    class_ids: tuple[int, ...]
    group_id: int | None

    @property
    def is_grouped(self) -> bool:
        return self.group_id is not None and len(self.class_ids) > 1

    @property
    def consistency_key(self) -> tuple[tuple[int, ...], int]:
        return (self.class_ids, self.subject_id)


@dataclass(frozen=True)
class _Assignment:
    unit_id: int
    lesson_slot_id: int
    teacher_id: int
    classroom_id: int
    slot_lesson_number: int


def _subject_fits_room(subject: Subject, room: Classroom) -> bool:
    if not subject.requires_special_room:
        return True
    if subject.required_specialization is None:
        return True
    return room.specialization == subject.required_specialization


def build_placement_units(
    *,
    school_id: int,
    plans: list[ClassSubjectHours],
    flows: list[GroupFlow],
    class_ids_scope: set[int],
    actual_by_pair: dict[tuple[int, int], int],
) -> list[_PlacementUnit]:
    missing_by_pair: dict[tuple[int, int], int] = {}
    for row in plans:
        if row.class_id not in class_ids_scope:
            continue
        actual = actual_by_pair.get((row.class_id, row.subject_id), 0)
        missing = max(0, row.hours_per_week - actual)
        if missing > 0:
            missing_by_pair[(row.class_id, row.subject_id)] = missing

    units: list[_PlacementUnit] = []
    next_unit_id = 0

    for flow in flows:
        flow_scope = [cid for cid in flow.combined_classes if cid in class_ids_scope]
        if len(flow_scope) < 2:
            continue
        subject_ids = {
            sid for (cid, sid), amount in missing_by_pair.items() if amount > 0 and cid in flow_scope
        }
        for subject_id in sorted(subject_ids):
            participants = [
                cid
                for cid in flow_scope
                if missing_by_pair.get((cid, subject_id), 0) > 0
            ]
            while len(participants) >= 2:
                class_ids = tuple(sorted(participants))
                units.append(
                    _PlacementUnit(
                        unit_id=next_unit_id,
                        subject_id=subject_id,
                        class_ids=class_ids,
                        group_id=flow.id,
                    )
                )
                next_unit_id += 1
                for cid in class_ids:
                    missing_by_pair[(cid, subject_id)] = max(
                        0, missing_by_pair.get((cid, subject_id), 0) - 1
                    )
                participants = [
                    cid
                    for cid in flow_scope
                    if missing_by_pair.get((cid, subject_id), 0) > 0
                ]

    for (class_id, subject_id), amount in sorted(missing_by_pair.items()):
        for _ in range(amount):
            units.append(
                _PlacementUnit(
                    unit_id=next_unit_id,
                    subject_id=subject_id,
                    class_ids=(class_id,),
                    group_id=None,
                )
            )
            next_unit_id += 1

    return units


def _existing_teacher_by_consistency_key(
    all_scheduled: list[ScheduleItem],
) -> dict[tuple[tuple[int, ...], int], int]:
    """If schedule already uses a single teacher per (class, subject), lock the group."""
    by_class_pair: dict[tuple[int, int], set[int]] = defaultdict(set)
    for item in all_scheduled:
        by_class_pair[(item.class_id, item.subject_id)].add(item.teacher_id)

    locked: dict[tuple[tuple[int, ...], int], int] = {}
    pair_to_classes: dict[tuple[int, int], list[tuple[int, ...]]] = defaultdict(list)
    for (class_id, subject_id) in by_class_pair:
        pair_to_classes[(class_id, subject_id)].append((class_id,))

    for (class_id, subject_id), teachers in by_class_pair.items():
        if len(teachers) != 1:
            continue
        teacher_id = next(iter(teachers))
        locked[((class_id,), subject_id)] = teacher_id

    return locked


def solve_missing_placements_whole_school(
    db: Session,
    *,
    school_id: int,
    class_ids: list[int],
    frozen_lesson_slot_ids: set[int] | None = None,
    max_runtime_seconds: int = 20,
) -> tuple[list[ScheduleItemIn], list[dict]]:
    """Solve missing hours for provided classes using CP-SAT.

    Returns (proposals, unplaced_meta).
    """
    try:
        from ortools.sat.python import cp_model
    except Exception:
        return [], [{"blocking_issues": ["CP_SAT_RUNTIME_UNAVAILABLE"]}]

    class_ids_scope = set(class_ids)
    if not class_ids_scope:
        return [], [{"blocking_issues": ["NO_CLASSES_FOR_SOLVER"]}]

    school = db.get(School, school_id)
    prefs = school.scheduling_preferences if school else None
    consistency_mode = subject_teacher_consistency_mode(prefs)
    obj_weights = solver_objective_weights(prefs)

    frozen = frozen_lesson_slot_ids or set()
    slots = list(db.scalars(select(LessonSlot).order_by(LessonSlot.day_of_week, LessonSlot.lesson_number)))
    slot_by_id = {s.id: s for s in slots}
    classes = {
        row.id: row
        for row in db.scalars(
            select(StudentClass).where(
                StudentClass.school_id == school_id,
                StudentClass.id.in_(class_ids_scope),
            )
        )
    }
    teachers = list(db.scalars(select(Teacher).where(Teacher.school_id == school_id)))
    teacher_by_id = {t.id: t for t in teachers}
    rooms = list(db.scalars(select(Classroom).where(Classroom.school_id == school_id)))
    subjects = {row.id: row for row in db.scalars(select(Subject))}
    flows = list(db.scalars(select(GroupFlow).where(GroupFlow.school_id == school_id)))

    plans = list(
        db.scalars(
            select(ClassSubjectHours).where(
                ClassSubjectHours.school_id == school_id,
                ClassSubjectHours.class_id.in_(class_ids_scope),
            )
        )
    )
    if not plans:
        return [], [{"blocking_issues": ["NO_CURRICULUM_FOR_CLASS"]}]

    all_scheduled = list(
        db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id))
    )
    scheduled_scoped = [item for item in all_scheduled if item.class_id in class_ids_scope]
    actual_by_pair: dict[tuple[int, int], int] = defaultdict(int)
    for item in scheduled_scoped:
        actual_by_pair[(item.class_id, item.subject_id)] += 1

    units = build_placement_units(
        school_id=school_id,
        plans=plans,
        flows=flows,
        class_ids_scope=class_ids_scope,
        actual_by_pair=actual_by_pair,
    )
    if not units:
        return [], [{"blocking_issues": ["SOLVER_NO_MISSING_HOURS"]}]

    class_slot_count: Counter[tuple[int, int]] = Counter()
    teacher_slot_count: Counter[tuple[int, int]] = Counter()
    room_slot_count: Counter[tuple[int, int]] = Counter()
    teacher_weekly_count: Counter[int] = Counter()
    teacher_rooms_existing: dict[int, set[int]] = defaultdict(set)
    for item in all_scheduled:
        class_slot_count[(item.class_id, item.lesson_slot_id)] += 1
        teacher_slot_count[(item.teacher_id, item.lesson_slot_id)] += 1
        room_slot_count[(item.classroom_id, item.lesson_slot_id)] += 1
        teacher_weekly_count[item.teacher_id] += 1
        teacher_rooms_existing[item.teacher_id].add(item.classroom_id)

    locked_teacher_by_key = _existing_teacher_by_consistency_key(all_scheduled)

    assignments_by_unit: dict[int, list[_Assignment]] = {}
    unplaced_meta: list[dict] = []

    for unit in units:
        subject = subjects.get(unit.subject_id)
        if subject is None:
            assignments_by_unit[unit.unit_id] = []
            unplaced_meta.append(
                {
                    "subject_id": unit.subject_id,
                    "class_ids": list(unit.class_ids),
                    "group_id": unit.group_id,
                    "blocking_issues": ["UNKNOWN_SUBJECT"],
                }
            )
            continue

        required_teacher: int | None = None
        if consistency_mode != "off":
            required_teacher = locked_teacher_by_key.get(unit.consistency_key)

        total_students = sum(classes[cid].students_count for cid in unit.class_ids if cid in classes)
        feasible: list[_Assignment] = []
        class_blocked_all = all(class_slot_count[(cid, s.id)] >= 1 for cid in unit.class_ids for s in slots)

        for slot in slots:
            if slot.id in frozen:
                continue
            if any(class_slot_count[(cid, slot.id)] >= 1 for cid in unit.class_ids):
                continue
            for teacher in teachers:
                if required_teacher is not None and teacher.id != required_teacher:
                    continue
                if not teacher_covers_subject(teacher.subjects, subject.name):
                    continue
                if slot.day_of_week in (teacher.unavailable_days or []):
                    continue
                if teacher_slot_count[(teacher.id, slot.id)] >= 1:
                    continue
                if teacher.weekly_load_limit > 0 and teacher_weekly_count[teacher.id] >= teacher.weekly_load_limit:
                    continue
                for room in rooms:
                    if not _subject_fits_room(subject, room):
                        continue
                    if room.capacity < total_students:
                        continue
                    if room_slot_count[(room.id, slot.id)] >= 1:
                        continue
                    feasible.append(
                        _Assignment(
                            unit_id=unit.unit_id,
                            lesson_slot_id=slot.id,
                            teacher_id=teacher.id,
                            classroom_id=room.id,
                            slot_lesson_number=slot.lesson_number,
                        )
                    )
        assignments_by_unit[unit.unit_id] = feasible
        if not feasible:
            unplaced_meta.append(
                {
                    "subject_id": unit.subject_id,
                    "class_ids": list(unit.class_ids),
                    "group_id": unit.group_id,
                    "blocking_issues": diagnose_empty_feasible(
                        subject=subject,
                        teachers=teachers,
                        slots=slots,
                        rooms=rooms,
                        frozen_slot_ids=frozen,
                        teacher_weekly_count=teacher_weekly_count,
                        teacher_slot_count=teacher_slot_count,
                        class_slot_blocked=class_blocked_all,
                        total_students=total_students,
                    ),
                }
            )

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    skip_vars: dict[int, cp_model.IntVar] = {}

    units_by_id = {unit.unit_id: unit for unit in units}
    active_units = [u for u in units if assignments_by_unit.get(u.unit_id)]

    for unit in active_units:
        skip = model.NewBoolVar(f"skip_u{unit.unit_id}")
        skip_vars[unit.unit_id] = skip
        row_vars = [skip]
        for aid, _assignment in enumerate(assignments_by_unit.get(unit.unit_id, [])):
            var = model.NewBoolVar(f"x_u{unit.unit_id}_a{aid}")
            x[(unit.unit_id, aid)] = var
            row_vars.append(var)
        model.Add(sum(row_vars) == 1)

    class_slot_vars: dict[tuple[int, int], list] = defaultdict(list)
    teacher_slot_vars: dict[tuple[int, int], list] = defaultdict(list)
    room_slot_vars: dict[tuple[int, int], list] = defaultdict(list)
    teacher_weekly_vars: dict[int, list] = defaultdict(list)

    for (unit_id, aid), var in x.items():
        unit = units_by_id[unit_id]
        assignment = assignments_by_unit[unit_id][aid]
        for cid in unit.class_ids:
            class_slot_vars[(cid, assignment.lesson_slot_id)].append(var)
        teacher_slot_vars[(assignment.teacher_id, assignment.lesson_slot_id)].append(var)
        room_slot_vars[(assignment.classroom_id, assignment.lesson_slot_id)].append(var)
        teacher_weekly_vars[assignment.teacher_id].append(var)

    for key, vars_for_key in class_slot_vars.items():
        cap = max(0, 1 - class_slot_count.get(key, 0))
        model.Add(sum(vars_for_key) <= cap)
    for key, vars_for_key in teacher_slot_vars.items():
        cap = max(0, 1 - teacher_slot_count.get(key, 0))
        model.Add(sum(vars_for_key) <= cap)
    for key, vars_for_key in room_slot_vars.items():
        cap = max(0, 1 - room_slot_count.get(key, 0))
        model.Add(sum(vars_for_key) <= cap)

    for teacher_id, vars_for_teacher in teacher_weekly_vars.items():
        teacher = teacher_by_id.get(teacher_id)
        if not teacher or teacher.weekly_load_limit <= 0:
            continue
        existing = teacher_weekly_count[teacher_id]
        remaining = max(0, teacher.weekly_load_limit - existing)
        model.Add(sum(vars_for_teacher) <= remaining)

    group_pick_vars: dict[tuple[tuple[int, ...], int, int], cp_model.IntVar] = {}
    if consistency_mode != "off":
        units_by_consistency: dict[tuple[tuple[int, ...], int], list[_PlacementUnit]] = defaultdict(list)
        for unit in active_units:
            if locked_teacher_by_key.get(unit.consistency_key) is not None:
                continue
            units_by_consistency[unit.consistency_key].append(unit)

        for ckey, group_units in units_by_consistency.items():
            class_ids_key, subject_id = ckey
            subject = subjects.get(subject_id)
            if not subject:
                continue
            qualified = [
                t.id
                for t in teachers
                if teacher_covers_subject(t.subjects, subject.name)
            ]
            if len(qualified) <= 1:
                continue
            pick_vars = []
            for tid in qualified:
                pick = model.NewBoolVar(f"pick_{class_ids_key}_{subject_id}_t{tid}")
                group_pick_vars[(class_ids_key, subject_id, tid)] = pick
                pick_vars.append(pick)
            model.Add(sum(pick_vars) == 1)
            for unit in group_units:
                for aid, assignment in enumerate(assignments_by_unit.get(unit.unit_id, [])):
                    var = x.get((unit.unit_id, aid))
                    if var is None:
                        continue
                    pick = group_pick_vars.get((class_ids_key, subject_id, assignment.teacher_id))
                    if pick is not None:
                        model.Add(var <= pick)

    weighted: list = []
    skip_weight = 100_000
    earlier_w = obj_weights.get("earlier_slot", 1.0)
    room_stab_w = obj_weights.get("room_stability", 0.0)
    variety_w = obj_weights.get("subject_variety", 0.0)

    for unit in active_units:
        weighted.append(skip_vars[unit.unit_id] * skip_weight)

    for (unit_id, aid), var in x.items():
        assignment = assignments_by_unit[unit_id][aid]
        if earlier_w:
            weighted.append(var * int(max(1, earlier_w) * assignment.slot_lesson_number))
        if room_stab_w:
            known = teacher_rooms_existing.get(assignment.teacher_id, set())
            if known and assignment.classroom_id not in known:
                weighted.append(var * int(max(1, room_stab_w) * 10))

    if variety_w:
        seen_pairs: set[tuple[int, int, int, int]] = set()
        for (unit_id, aid), var in x.items():
            unit = units_by_id[unit_id]
            assignment = assignments_by_unit[unit_id][aid]
            slot = slot_by_id.get(assignment.lesson_slot_id)
            if not slot:
                continue
            for (other_uid, other_aid), other_var in x.items():
                if other_uid <= unit_id:
                    continue
                pair_key = (unit_id, aid, other_uid, other_aid)
                if pair_key in seen_pairs:
                    continue
                other_unit = units_by_id[other_uid]
                if other_unit.subject_id != unit.subject_id:
                    continue
                if not set(other_unit.class_ids) & set(unit.class_ids):
                    continue
                other_a = assignments_by_unit[other_uid][other_aid]
                other_slot = slot_by_id.get(other_a.lesson_slot_id)
                if not other_slot or other_slot.day_of_week != slot.day_of_week:
                    continue
                if abs(other_slot.lesson_number - slot.lesson_number) != 1:
                    continue
                seen_pairs.add(pair_key)
                both = model.NewBoolVar(f"adj_{unit_id}_{aid}_{other_uid}_{other_aid}")
                model.Add(both <= var)
                model.Add(both <= other_var)
                model.Add(both >= var + other_var - 1)
                weighted.append(both * int(max(1, variety_w) * 5))

    if weighted:
        model.Minimize(sum(weighted))
    else:
        model.Minimize(0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max(1, max_runtime_seconds))
    status = solver.Solve(model)
    accepted = {cp_model.OPTIMAL, cp_model.FEASIBLE}
    if status not in accepted:
        return [], [{"blocking_issues": [f"CP_SAT_STATUS_{int(status)}"]}]

    proposals: list[ScheduleItemIn] = []
    for unit in units:
        if unit.unit_id not in skip_vars:
            continue
        if solver.Value(skip_vars[unit.unit_id]) == 1:
            if not any(m.get("subject_id") == unit.subject_id and m.get("class_ids") == list(unit.class_ids) for m in unplaced_meta):
                reasons = (
                    ["CP_SAT_NO_FEASIBLE_ASSIGNMENT"]
                    if not assignments_by_unit.get(unit.unit_id)
                    else ["CP_SAT_UNPLACED_AFTER_OPTIMIZATION"]
                )
                unplaced_meta.append(
                    {
                        "subject_id": unit.subject_id,
                        "class_ids": list(unit.class_ids),
                        "group_id": unit.group_id,
                        "blocking_issues": reasons,
                    }
                )
            continue

        chosen_assignment: _Assignment | None = None
        for aid, assignment in enumerate(assignments_by_unit.get(unit.unit_id, [])):
            key = (unit.unit_id, aid)
            if key in x and solver.Value(x[key]) == 1:
                chosen_assignment = assignment
                break
        if chosen_assignment is None:
            unplaced_meta.append(
                {
                    "subject_id": unit.subject_id,
                    "class_ids": list(unit.class_ids),
                    "group_id": unit.group_id,
                    "blocking_issues": ["CP_SAT_INTERNAL_SELECTION_MISSING"],
                }
            )
            continue

        for class_id in unit.class_ids:
            proposals.append(
                ScheduleItemIn(
                    class_id=class_id,
                    subject_id=unit.subject_id,
                    teacher_id=chosen_assignment.teacher_id,
                    classroom_id=chosen_assignment.classroom_id,
                    lesson_slot_id=chosen_assignment.lesson_slot_id,
                    is_grouped=unit.is_grouped,
                    group_id=unit.group_id,
                    school_id=school_id,
                )
            )

    return proposals, unplaced_meta


def missing_hours_count(db: Session, *, school_id: int, class_ids: list[int]) -> int:
    """Useful diagnostic for tests and job messages."""
    class_ids_scope = set(class_ids)
    if not class_ids_scope:
        return 0
    plans = list(
        db.scalars(
            select(ClassSubjectHours).where(
                ClassSubjectHours.school_id == school_id,
                ClassSubjectHours.class_id.in_(class_ids_scope),
            )
        )
    )
    if not plans:
        return 0
    raw_counts = db.execute(
        select(ScheduleItem.class_id, ScheduleItem.subject_id, func.count())
        .where(
            ScheduleItem.school_id == school_id,
            ScheduleItem.class_id.in_(class_ids_scope),
        )
        .group_by(ScheduleItem.class_id, ScheduleItem.subject_id)
    ).all()
    actual_pairs = {(class_id, subject_id): int(count) for class_id, subject_id, count in raw_counts}
    missing = 0
    for row in plans:
        actual = int(actual_pairs.get((row.class_id, row.subject_id), 0))
        missing += max(0, row.hours_per_week - actual)
    return missing
