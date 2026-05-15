"""Heuristic slot suggestions and draft generation for a single class.

See README.md sections **Future timetable solver (contract)** and
**Class draft generator limitations (v1)** for how this relates to a future
optimizer and for known gaps (e.g. grouped lessons).
"""

from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    ClassroomSpecialization,
    GroupFlow,
    LessonSlot,
    ScheduleItem,
    School,
    Subject,
    Teacher,
)
from app.schemas.entities import ScheduleItemIn
from app.schemas.validation import ValidationIssue
from app.services.schedule_cp_sat import build_placement_units
from app.services.schedule_quality import score_validation_issues
from app.services.scheduling_preferences import subject_teacher_consistency_mode
from app.services.subject_teacher_match import teacher_covers_subject
from app.services.validation_engine import validate_schedule


def _error_free(issues: list[ValidationIssue]) -> bool:
    return not any(i.severity == "error" for i in issues)


def _teacher_covers_subject(teacher: Teacher, subject: Subject) -> bool:
    return teacher_covers_subject(teacher.subjects, subject.name)


def _ordered_rooms_for_subject(rooms: list[Classroom], subject: Subject) -> list[Classroom]:
    """Try better-fitting rooms first so the greedy search hits a valid cell sooner."""
    if subject.requires_special_room and subject.required_specialization is not None:
        spec = subject.required_specialization
        return sorted(rooms, key=lambda r: (0 if r.specialization == spec else 1, r.id))
    name_cf = subject.name.strip().casefold()
    pe_tokens = ("physical", "физкульт", "физическая", "sport")
    prefer_gym = name_cf in {"pe", "пф"} or any(tok in name_cf for tok in pe_tokens)
    if prefer_gym:
        return sorted(
            rooms,
            key=lambda r: (
                0 if r.specialization == ClassroomSpecialization.gym else 1,
                -r.capacity,
                r.id,
            ),
        )
    return sorted(rooms, key=lambda r: r.id)


def _probe_placement_blockers(
    db: Session,
    school_id: int,
    class_id: int,
    subject: Subject,
    qualified: list[Teacher],
    slots: list[LessonSlot],
    rooms_ordered: list[Classroom],
    proposals: list[ScheduleItemIn],
) -> list[str]:
    """Return validation errors for the first (teacher, slot, room) tried — same order as the greedy search.

    Aggregating errors across many probes mixed unrelated codes (e.g. lab mismatch vs gym capacity).
    """
    if not qualified:
        return ["NO_QUALIFIED_TEACHER"]
    if not slots:
        return ["NO_LESSON_SLOTS"]
    if not rooms_ordered:
        return ["NO_CLASSROOMS"]

    for teacher in qualified:
        for slot in slots:
            for room in rooms_ordered:
                candidate = ScheduleItemIn(
                    class_id=class_id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    classroom_id=room.id,
                    lesson_slot_id=slot.id,
                    is_grouped=False,
                    group_id=None,
                    school_id=school_id,
                )
                issues = validate_schedule(
                    db,
                    school_id,
                    candidate,
                    pending=proposals,
                    check_curriculum_totals=False,
                )
                errs = [i.issue_code for i in issues if i.severity == "error"]
                if errs:
                    return errs[:10]
    return []


def suggest_slot_combinations(
    db: Session,
    school_id: int,
    base: ScheduleItemIn,
    top_n: int = 8,
    *,
    ignore_schedule_item_id: int | None = None,
) -> list[dict]:
    """
    Rank (lesson_slot_id, classroom_id) pairs by total validation penalty (including soft issues).
    Only returns combinations with no error-severity issues.
    """
    slots = list(db.scalars(select(LessonSlot).order_by(LessonSlot.day_of_week, LessonSlot.lesson_number)))
    rooms = list(
        db.scalars(select(Classroom).where(Classroom.school_id == school_id).order_by(Classroom.id))
    )
    subj = db.get(Subject, base.subject_id)
    rooms_for_subject = _ordered_rooms_for_subject(rooms, subj) if subj else rooms
    scored: list[tuple[int, int, float]] = []
    for slot in slots:
        for room in rooms_for_subject:
            candidate = base.model_copy(
                update={"lesson_slot_id": slot.id, "classroom_id": room.id, "school_id": school_id}
            )
            ignore_ids = {ignore_schedule_item_id} if ignore_schedule_item_id is not None else None
            issues = validate_schedule(
                db,
                school_id,
                candidate,
                check_curriculum_totals=False,
                ignore_schedule_item_ids=ignore_ids,
            )
            if not _error_free(issues):
                continue
            quality = score_validation_issues(issues)
            scored.append((slot.id, room.id, quality["total_penalty"]))
    scored.sort(key=lambda row: row[2])
    return [
        {"lesson_slot_id": slot_id, "classroom_id": room_id, "penalty": penalty}
        for slot_id, room_id, penalty in scored[: max(0, top_n)]
    ]


def generate_draft_for_class(
    db: Session,
    school_id: int,
    class_id: int,
) -> tuple[list[ScheduleItemIn], list[dict]]:
    """
    Greedy fill for missing curriculum hours using ``build_placement_units`` (grouped flows first,
    then ungrouped), aligned with the CP-SAT unit decomposition for this class.
    """
    plans = list(
        db.scalars(
            select(ClassSubjectHours).where(
                ClassSubjectHours.school_id == school_id,
                ClassSubjectHours.class_id == class_id,
            )
        )
    )
    if not plans:
        return [], [{"blocking_issues": ["NO_CURRICULUM_FOR_CLASS"]}]

    subj_by_id = {s.id: s for s in db.scalars(select(Subject))}

    def _plan_sort_key(plan: ClassSubjectHours) -> tuple[int, str]:
        s = subj_by_id.get(plan.subject_id)
        if not s:
            return (9, "")
        return (1 if s.requires_special_room else 0, s.name)

    plans.sort(key=_plan_sort_key)
    teachers = list(db.scalars(select(Teacher).where(Teacher.school_id == school_id)))
    flows = list(db.scalars(select(GroupFlow).where(GroupFlow.school_id == school_id)))

    actual_by_pair: dict[tuple[int, int], int] = {}
    for row in db.scalars(
        select(ScheduleItem).where(
            ScheduleItem.school_id == school_id,
            ScheduleItem.class_id == class_id,
        )
    ):
        key = (row.class_id, row.subject_id)
        actual_by_pair[key] = actual_by_pair.get(key, 0) + 1

    units = build_placement_units(
        school_id=school_id,
        plans=plans,
        flows=flows,
        class_ids_scope={class_id},
        actual_by_pair=actual_by_pair,
    )
    if not units:
        return [], [{"blocking_issues": ["SOLVER_NO_MISSING_HOURS"]}]

    slots = list(db.scalars(select(LessonSlot).order_by(LessonSlot.day_of_week, LessonSlot.lesson_number)))
    rooms = list(
        db.scalars(select(Classroom).where(Classroom.school_id == school_id).order_by(Classroom.id))
    )

    proposals: list[ScheduleItemIn] = []
    unplaced: list[dict] = []

    school = db.get(School, school_id)
    consistency_mode = subject_teacher_consistency_mode(
        school.scheduling_preferences if school else None
    )
    chosen_teacher: dict[tuple[int, int], int] = {}
    if consistency_mode != "off":
        for row in db.scalars(
            select(ScheduleItem).where(
                ScheduleItem.school_id == school_id,
                ScheduleItem.class_id == class_id,
            )
        ):
            key = (row.class_id, row.subject_id)
            if key not in chosen_teacher:
                chosen_teacher[key] = row.teacher_id

    for unit in units:
        subject = subj_by_id.get(unit.subject_id)
        if not subject:
            continue
        qualified_teachers = [t for t in teachers if _teacher_covers_subject(t, subject)]
        if consistency_mode != "off":
            for cid in unit.class_ids:
                locked = chosen_teacher.get((cid, unit.subject_id))
                if locked is not None:
                    qualified_teachers = [t for t in qualified_teachers if t.id == locked]
                    break
        rooms_for_subject = _ordered_rooms_for_subject(rooms, subject)
        is_grouped = len(unit.class_ids) > 1 and unit.group_id is not None

        found = False
        for teacher in qualified_teachers:
            for slot in slots:
                for room in rooms_for_subject:
                    if is_grouped:
                        batch = [
                            ScheduleItemIn(
                                class_id=cid,
                                subject_id=unit.subject_id,
                                teacher_id=teacher.id,
                                classroom_id=room.id,
                                lesson_slot_id=slot.id,
                                is_grouped=True,
                                group_id=unit.group_id,
                                school_id=school_id,
                            )
                            for cid in unit.class_ids
                        ]
                        issues = validate_schedule(
                            db,
                            school_id,
                            None,
                            pending=[*proposals, *batch],
                            check_curriculum_totals=False,
                        )
                        if _error_free(issues):
                            proposals.extend(batch)
                            if consistency_mode != "off":
                                for cid in unit.class_ids:
                                    chosen_teacher[(cid, unit.subject_id)] = teacher.id
                            found = True
                            break
                    else:
                        cid = unit.class_ids[0]
                        candidate = ScheduleItemIn(
                            class_id=cid,
                            subject_id=unit.subject_id,
                            teacher_id=teacher.id,
                            classroom_id=room.id,
                            lesson_slot_id=slot.id,
                            is_grouped=False,
                            group_id=None,
                            school_id=school_id,
                        )
                        issues = validate_schedule(
                            db,
                            school_id,
                            candidate,
                            pending=proposals,
                            check_curriculum_totals=False,
                        )
                        if _error_free(issues):
                            proposals.append(candidate)
                            if consistency_mode != "off":
                                chosen_teacher[(cid, unit.subject_id)] = teacher.id
                            found = True
                            break
                if found:
                    break
            if found:
                break

        if not found:
            probe_class = unit.class_ids[0]
            unplaced.append(
                {
                    "subject_id": unit.subject_id,
                    "subject_name": subject.name,
                    "class_ids": list(unit.class_ids),
                    "group_id": unit.group_id,
                    "hours_missing": len(unit.class_ids) if is_grouped else 1,
                    "blocking_issues": _probe_placement_blockers(
                        db,
                        school_id,
                        probe_class,
                        subject,
                        qualified_teachers,
                        slots,
                        rooms_for_subject,
                        proposals,
                    ),
                }
            )

    return proposals, unplaced


def draft_teacher_absence(
    db: Session,
    school_id: int,
    teacher_id: int,
    *,
    day_of_week: int | None = None,
    substitute_teacher_id: int | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Produce non-persisted draft operations for teacher absence:
    - update lesson to substitute teacher when possible
    - otherwise delete lesson (free period)
    """
    slots = {row.id: row for row in db.scalars(select(LessonSlot))}
    subject_by_id = {row.id: row for row in db.scalars(select(Subject))}
    teachers = list(db.scalars(select(Teacher).where(Teacher.school_id == school_id)))
    teacher_by_id = {t.id: t for t in teachers}
    all_items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))

    if teacher_id not in teacher_by_id:
        return [], ["TEACHER_NOT_FOUND"]

    affected: list[ScheduleItem] = []
    for item in all_items:
        if item.teacher_id != teacher_id:
            continue
        slot = slots.get(item.lesson_slot_id)
        if day_of_week is not None and (not slot or slot.day_of_week != day_of_week):
            continue
        affected.append(item)

    if not affected:
        return [], ["NO_AFFECTED_LESSONS"]

    # Keep occupancy map without absent teacher lessons so replacements can reuse those slots.
    teacher_busy: set[tuple[int, int]] = {
        (item.teacher_id, item.lesson_slot_id)
        for item in all_items
        if item.teacher_id != teacher_id
    }

    operations: list[dict] = []
    notes: list[str] = []

    for item in affected:
        subject = subject_by_id.get(item.subject_id)
        if substitute_teacher_id is not None:
            candidates = [teacher_by_id.get(substitute_teacher_id)] if teacher_by_id.get(substitute_teacher_id) else []
        else:
            candidates = []
            if subject is not None:
                candidates = [t for t in teachers if t.id != teacher_id and _teacher_covers_subject(t, subject)]
        chosen: Teacher | None = None
        for candidate in candidates:
            if candidate is None:
                continue
            if (candidate.id, item.lesson_slot_id) in teacher_busy:
                continue
            if subject is not None and not _teacher_covers_subject(candidate, subject):
                continue
            chosen = candidate
            break
        if chosen is None:
            operations.append({"type": "delete", "id": item.id})
            notes.append(f"LESSON_{item.id}_WILL_BE_FREED")
            continue
        teacher_busy.add((chosen.id, item.lesson_slot_id))
        payload = ScheduleItemIn(
            class_id=item.class_id,
            subject_id=item.subject_id,
            teacher_id=chosen.id,
            classroom_id=item.classroom_id,
            lesson_slot_id=item.lesson_slot_id,
            is_grouped=item.is_grouped,
            group_id=item.group_id,
            school_id=item.school_id,
        )
        operations.append({"type": "update", "id": item.id, "payload": payload})

    return operations, notes


def _schedule_item_to_in(item: ScheduleItem) -> ScheduleItemIn:
    return ScheduleItemIn(
        class_id=item.class_id,
        subject_id=item.subject_id,
        teacher_id=item.teacher_id,
        classroom_id=item.classroom_id,
        lesson_slot_id=item.lesson_slot_id,
        is_grouped=item.is_grouped,
        group_id=item.group_id,
        school_id=item.school_id,
    )


def compute_reoptimize_schedule_updates(
    db: Session,
    school_id: int,
    *,
    class_ids_scope: list[int] | None,
    frozen_lesson_slot_ids: set[int] | None,
    max_passes: int = 32,
    seed: int = 42,
) -> tuple[list[dict], list[str]]:
    """Greedy improvements: ``update`` operations that reduce validation penalty (error-free)."""
    rng = random.Random(seed)
    frozen = frozen_lesson_slot_ids or set()
    items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))
    if class_ids_scope is not None:
        wanted = set(class_ids_scope)
        items = [it for it in items if it.class_id in wanted]
    items = [it for it in items if it.lesson_slot_id not in frozen]
    if not items:
        return [], ["NO_MOVABLE_LESSONS"]

    def penalty_for_batch(batch: list[tuple[int, ScheduleItemIn]]) -> float:
        issues = validate_schedule(
            db,
            school_id,
            None,
            check_curriculum_totals=True,
            replacement_batch=batch or None,
        )
        return float(score_validation_issues(issues)["total_penalty"])

    def error_free_batch(batch: list[tuple[int, ScheduleItemIn]]) -> bool:
        issues = validate_schedule(
            db,
            school_id,
            None,
            check_curriculum_totals=True,
            replacement_batch=batch or None,
        )
        return not any(i.severity == "error" for i in issues)

    batch: list[tuple[int, ScheduleItemIn]] = []
    baseline_penalty = penalty_for_batch([])
    notes: list[str] = []

    for _ in range(max(1, max_passes)):
        best_gain = 0.0
        best_move: tuple[int, ScheduleItemIn] | None = None
        rng.shuffle(items)
        for it in items:
            base = next((pl for rid, pl in batch if rid == it.id), None) or _schedule_item_to_in(it)
            opts = suggest_slot_combinations(db, school_id, base, top_n=10, ignore_schedule_item_id=it.id)
            for opt in opts:
                if opt["lesson_slot_id"] == base.lesson_slot_id and opt["classroom_id"] == base.classroom_id:
                    continue
                trial_payload = base.model_copy(
                    update={
                        "lesson_slot_id": opt["lesson_slot_id"],
                        "classroom_id": opt["classroom_id"],
                    }
                )
                trial_batch = [tpl for tpl in batch if tpl[0] != it.id] + [(it.id, trial_payload)]
                if not error_free_batch(trial_batch):
                    continue
                pen = penalty_for_batch(trial_batch)
                gain = baseline_penalty - pen
                if gain > best_gain + 1e-6:
                    best_gain = gain
                    best_move = (it.id, trial_payload)
        if best_move is None:
            break
        batch = [tpl for tpl in batch if tpl[0] != best_move[0]]
        batch.append(best_move)
        baseline_penalty = penalty_for_batch(batch)
        notes.append(f"REOPT_MOVE_{best_move[0]}")

    operations: list[dict] = []
    for rid, payload in batch:
        operations.append({"type": "update", "id": rid, "payload": payload})
    return operations, notes


def _candidate_penalty(db: Session, school_id: int, candidate: ScheduleItemIn) -> float:
    issues = validate_schedule(db, school_id, candidate, check_curriculum_totals=False)
    quality = score_validation_issues(issues)
    return float(quality["total_penalty"])


def optimize_proposals_local_search(
    db: Session,
    school_id: int,
    proposals: list[ScheduleItemIn],
    *,
    iterations: int = 40,
    seed: int = 42,
) -> list[ScheduleItemIn]:
    if not proposals:
        return proposals
    rng = random.Random(seed)
    best = [p.model_copy() for p in proposals]
    best_score = sum(_candidate_penalty(db, school_id, p) for p in best)
    for _ in range(max(1, iterations)):
        idx = rng.randrange(0, len(best))
        current = best[idx]
        options = suggest_slot_combinations(db, school_id, current, top_n=5)
        if not options:
            continue
        pick = options[rng.randrange(0, len(options))]
        trial_item = current.model_copy(
            update={"lesson_slot_id": pick["lesson_slot_id"], "classroom_id": pick["classroom_id"]}
        )
        trial = [p.model_copy() for p in best]
        trial[idx] = trial_item
        trial_score = sum(_candidate_penalty(db, school_id, p) for p in trial)
        if trial_score <= best_score:
            best = trial
            best_score = trial_score
    return best


def optimize_proposals_ga_fallback(
    db: Session,
    school_id: int,
    proposals: list[ScheduleItemIn],
    *,
    generations: int = 20,
    population_size: int = 8,
    mutation_rate: float = 0.25,
    seed: int = 42,
) -> list[ScheduleItemIn]:
    if not proposals:
        return proposals
    rng = random.Random(seed)

    def make_variant(base: list[ScheduleItemIn]) -> list[ScheduleItemIn]:
        variant = [p.model_copy() for p in base]
        for i, item in enumerate(variant):
            if rng.random() > mutation_rate:
                continue
            options = suggest_slot_combinations(db, school_id, item, top_n=3)
            if not options:
                continue
            choice = options[rng.randrange(0, len(options))]
            variant[i] = item.model_copy(
                update={"lesson_slot_id": choice["lesson_slot_id"], "classroom_id": choice["classroom_id"]}
            )
        return variant

    def fitness(candidate_set: list[ScheduleItemIn]) -> float:
        return -sum(_candidate_penalty(db, school_id, row) for row in candidate_set)

    population = [[p.model_copy() for p in proposals]]
    while len(population) < population_size:
        population.append(make_variant(population[0]))

    for _ in range(max(1, generations)):
        population.sort(key=fitness, reverse=True)
        elites = population[:2]
        next_population = [elite for elite in elites]
        while len(next_population) < population_size:
            parent_a = population[rng.randrange(0, len(population))]
            parent_b = population[rng.randrange(0, len(population))]
            child = []
            for idx in range(len(proposals)):
                source = parent_a if rng.random() > 0.5 else parent_b
                child.append(source[idx].model_copy())
            next_population.append(make_variant(child))
        population = next_population

    population.sort(key=fitness, reverse=True)
    return population[0]
