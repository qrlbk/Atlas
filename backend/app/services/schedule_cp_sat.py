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
    StudentClass,
    Subject,
    Teacher,
)
from app.schemas.entities import ScheduleItemIn
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


@dataclass(frozen=True)
class _Assignment:
    unit_id: int
    lesson_slot_id: int
    teacher_id: int
    classroom_id: int


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

    # Phase 2: grouped units first (same flow, same subject, all currently missing).
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

    # Phase 1: ungrouped units for remaining missing hours.
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

    frozen = frozen_lesson_slot_ids or set()
    slots = list(db.scalars(select(LessonSlot).order_by(LessonSlot.day_of_week, LessonSlot.lesson_number)))
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

    # Occupancy must reflect the entire school schedule so we do not propose
    # teacher/room/class slots already taken by other classes (solver job may be single-class).
    class_slot_count: Counter[tuple[int, int]] = Counter()
    teacher_slot_count: Counter[tuple[int, int]] = Counter()
    room_slot_count: Counter[tuple[int, int]] = Counter()
    for item in all_scheduled:
        class_slot_count[(item.class_id, item.lesson_slot_id)] += 1
        teacher_slot_count[(item.teacher_id, item.lesson_slot_id)] += 1
        room_slot_count[(item.classroom_id, item.lesson_slot_id)] += 1

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

        total_students = sum(classes[cid].students_count for cid in unit.class_ids if cid in classes)
        feasible: list[_Assignment] = []
        for slot in slots:
            if slot.id in frozen:
                continue
            if any(class_slot_count[(cid, slot.id)] >= 1 for cid in unit.class_ids):
                continue
            for teacher in teachers:
                if not teacher_covers_subject(teacher.subjects, subject.name):
                    continue
                if slot.day_of_week in (teacher.unavailable_days or []):
                    continue
                if teacher_slot_count[(teacher.id, slot.id)] >= 1:
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
                        )
                    )
        assignments_by_unit[unit.unit_id] = feasible

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    skip_vars: dict[int, cp_model.IntVar] = {}

    # Build decision vars: one assignment or skip for each unit.
    for unit in units:
        skip = model.NewBoolVar(f"skip_u{unit.unit_id}")
        skip_vars[unit.unit_id] = skip
        row_vars = [skip]
        for aid, assignment in enumerate(assignments_by_unit.get(unit.unit_id, [])):
            var = model.NewBoolVar(f"x_u{unit.unit_id}_a{aid}")
            x[(unit.unit_id, aid)] = var
            row_vars.append(var)
        model.Add(sum(row_vars) == 1)

    # Global no-conflict constraints among selected assignments.
    class_slot_vars: dict[tuple[int, int], list[cp_model.IntVar]] = defaultdict(list)
    teacher_slot_vars: dict[tuple[int, int], list[cp_model.IntVar]] = defaultdict(list)
    room_slot_vars: dict[tuple[int, int], list[cp_model.IntVar]] = defaultdict(list)

    units_by_id = {unit.unit_id: unit for unit in units}
    for (unit_id, aid), var in x.items():
        unit = units_by_id[unit_id]
        assignment = assignments_by_unit[unit_id][aid]
        for cid in unit.class_ids:
            class_slot_vars[(cid, assignment.lesson_slot_id)].append(var)
        teacher_slot_vars[(assignment.teacher_id, assignment.lesson_slot_id)].append(var)
        room_slot_vars[(assignment.classroom_id, assignment.lesson_slot_id)].append(var)

    for key, vars_for_key in class_slot_vars.items():
        cap = max(0, 1 - class_slot_count.get(key, 0))
        model.Add(sum(vars_for_key) <= cap)
    for key, vars_for_key in teacher_slot_vars.items():
        cap = max(0, 1 - teacher_slot_count.get(key, 0))
        model.Add(sum(vars_for_key) <= cap)
    for key, vars_for_key in room_slot_vars.items():
        cap = max(0, 1 - room_slot_count.get(key, 0))
        model.Add(sum(vars_for_key) <= cap)

    # Minimize unplaced units first; secondarily prefer earlier slots.
    weighted = []
    for unit in units:
        weighted.append(skip_vars[unit.unit_id] * 100_000)
    for (unit_id, aid), var in x.items():
        slot_id = assignments_by_unit[unit_id][aid].lesson_slot_id
        weighted.append(var * slot_id)
    model.Minimize(sum(weighted))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max(1, max_runtime_seconds))
    status = solver.Solve(model)
    accepted = {cp_model.OPTIMAL, cp_model.FEASIBLE}
    if status not in accepted:
        return [], [{"blocking_issues": [f"CP_SAT_STATUS_{int(status)}"]}]

    proposals: list[ScheduleItemIn] = []
    for unit in units:
        if solver.Value(skip_vars[unit.unit_id]) == 1:
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
            if solver.Value(x[(unit.unit_id, aid)]) == 1:
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
