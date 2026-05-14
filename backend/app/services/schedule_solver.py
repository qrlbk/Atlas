"""Heuristic slot suggestions and draft generation for a single class.

See README.md sections **Future timetable solver (contract)** and
**Class draft generator limitations (v1)** for how this relates to a future
optimizer and for known gaps (e.g. grouped lessons).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    ClassroomSpecialization,
    LessonSlot,
    ScheduleItem,
    Subject,
    Teacher,
)
from app.schemas.entities import ScheduleItemIn
from app.schemas.validation import ValidationIssue
from app.services.schedule_quality import score_validation_issues
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
            issues = validate_schedule(db, school_id, candidate, check_curriculum_totals=False)
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
    Greedy fill: for each curriculum row, add missing lessons using first error-free (slot, room, teacher).
    Each candidate is validated together with ``pending`` (proposals already collected in this run) so
    teacher/class/room double-bookings cannot slip through between iterations.
    Returns (proposals, unplaced) where unplaced entries describe subject_id and missing count.

    Limitations: every proposal uses ``is_grouped=False`` (no grouped-flow lessons).
    README: **Class draft generator limitations (v1)**.
    """
    plans = list(
        db.scalars(
            select(ClassSubjectHours).where(
                ClassSubjectHours.school_id == school_id,
                ClassSubjectHours.class_id == class_id,
            )
        )
    )
    subj_by_id = {s.id: s for s in db.scalars(select(Subject))}
    # Prefer subjects that fit a standard room first so partial drafts succeed when labs are tight.
    def _plan_sort_key(plan: ClassSubjectHours) -> tuple[int, str]:
        s = subj_by_id.get(plan.subject_id)
        if not s:
            return (9, "")
        return (1 if s.requires_special_room else 0, s.name)

    plans.sort(key=_plan_sort_key)
    teachers = list(db.scalars(select(Teacher).where(Teacher.school_id == school_id)))

    def count_db(subject_id: int) -> int:
        return int(
            db.scalar(
                select(func.count())
                .select_from(ScheduleItem)
                .where(
                    ScheduleItem.school_id == school_id,
                    ScheduleItem.class_id == class_id,
                    ScheduleItem.subject_id == subject_id,
                )
            )
            or 0
        )

    slots = list(db.scalars(select(LessonSlot).order_by(LessonSlot.day_of_week, LessonSlot.lesson_number)))
    rooms = list(
        db.scalars(select(Classroom).where(Classroom.school_id == school_id).order_by(Classroom.id))
    )

    proposals: list[ScheduleItemIn] = []
    unplaced: list[dict] = []

    for plan in plans:
        subject = subj_by_id.get(plan.subject_id)
        if not subject:
            continue
        qualified_teachers = [t for t in teachers if _teacher_covers_subject(t, subject)]
        rooms_for_subject = _ordered_rooms_for_subject(rooms, subject)

        while True:
            pending = sum(1 for p in proposals if p.subject_id == plan.subject_id)
            placed_total = count_db(plan.subject_id) + pending
            if placed_total >= plan.hours_per_week:
                break
            found = False
            for teacher in qualified_teachers:
                for slot in slots:
                    for room in rooms_for_subject:
                        candidate = ScheduleItemIn(
                            class_id=class_id,
                            subject_id=plan.subject_id,
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
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            if not found:
                still = plan.hours_per_week - count_db(plan.subject_id) - sum(
                    1 for p in proposals if p.subject_id == plan.subject_id
                )
                if still > 0:
                    unplaced.append(
                        {
                            "subject_id": plan.subject_id,
                            "subject_name": subject.name,
                            "hours_missing": still,
                            "blocking_issues": _probe_placement_blockers(
                                db,
                                school_id,
                                class_id,
                                subject,
                                qualified_teachers,
                                slots,
                                rooms_for_subject,
                                proposals,
                            ),
                        }
                    )
                break

    return proposals, unplaced
