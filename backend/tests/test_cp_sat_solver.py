from __future__ import annotations

import builtins
from datetime import time

import pytest

from sqlalchemy import select

from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    ClassroomSpecialization,
    GroupFlow,
    LessonSlot,
    ScheduleItem,
    School,
    StudentClass,
    Subject,
    Teacher,
)
from app.services.schedule_cp_sat import solve_missing_placements_whole_school

try:
    from ortools.sat.python import cp_model as _cp_model  # noqa: F401

    HAS_ORTOOLS = True
except Exception:
    HAS_ORTOOLS = False


def _slot(day: int, lesson: int) -> LessonSlot:
    return LessonSlot(
        day_of_week=day,
        lesson_number=lesson,
        start_time=time(8 + (lesson - 1), 0),
        end_time=time(8 + lesson, 0),
    )


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_cp_sat_solves_missing_hours_across_classes(db_session):
    school = School(name="cp-sat-school", address="a")
    db_session.add(school)
    db_session.flush()

    math = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    physics = Subject(
        name="Physics",
        requires_special_room=True,
        required_specialization=ClassroomSpecialization.physics_lab,
    )
    db_session.add_all([math, physics])
    db_session.flush()

    c1 = StudentClass(class_name="10A", students_count=25, school_id=school.id)
    c2 = StudentClass(class_name="10B", students_count=24, school_id=school.id)
    db_session.add_all([c1, c2])
    db_session.flush()

    t_math = Teacher(
        full_name="Math T",
        subjects=["Mathematics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    t_phys = Teacher(
        full_name="Phys T",
        subjects=["Physics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    db_session.add_all([t_math, t_phys])
    db_session.flush()

    r_std = Classroom(
        room_number="101",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    r_lab = Classroom(
        room_number="Lab-P",
        capacity=30,
        specialization=ClassroomSpecialization.physics_lab,
        school_id=school.id,
    )
    db_session.add_all([r_std, r_lab])
    db_session.add_all([_slot(1, 1), _slot(1, 2)])
    db_session.flush()

    db_session.add_all(
        [
            ClassSubjectHours(school_id=school.id, class_id=c1.id, subject_id=math.id, hours_per_week=1),
            ClassSubjectHours(school_id=school.id, class_id=c2.id, subject_id=physics.id, hours_per_week=1),
        ]
    )
    db_session.commit()

    proposals, unplaced = solve_missing_placements_whole_school(
        db_session,
        school_id=school.id,
        class_ids=[c1.id, c2.id],
        max_runtime_seconds=5,
    )

    assert unplaced == []
    assert len(proposals) == 2
    by_class = {p.class_id: p for p in proposals}
    assert by_class[c1.id].subject_id == math.id
    assert by_class[c2.id].subject_id == physics.id


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_cp_sat_builds_grouped_lessons_for_flow(db_session):
    school = School(name="cp-sat-grouped", address="a")
    db_session.add(school)
    db_session.flush()

    physics = Subject(
        name="Physics",
        requires_special_room=True,
        required_specialization=ClassroomSpecialization.physics_lab,
    )
    db_session.add(physics)
    db_session.flush()

    c1 = StudentClass(class_name="10A", students_count=26, school_id=school.id)
    c2 = StudentClass(class_name="10B", students_count=27, school_id=school.id)
    db_session.add_all([c1, c2])
    db_session.flush()

    flow = GroupFlow(group_name="Science", combined_classes=[c1.id, c2.id], school_id=school.id)
    db_session.add(flow)

    teacher = Teacher(
        full_name="Phys Teacher",
        subjects=["Physics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    db_session.add(teacher)
    db_session.add(
        Classroom(
            room_number="Lab-P",
            capacity=60,
            specialization=ClassroomSpecialization.physics_lab,
            school_id=school.id,
        )
    )
    db_session.add_all([_slot(1, 1), _slot(1, 2)])
    db_session.flush()

    db_session.add_all(
        [
            ClassSubjectHours(school_id=school.id, class_id=c1.id, subject_id=physics.id, hours_per_week=1),
            ClassSubjectHours(school_id=school.id, class_id=c2.id, subject_id=physics.id, hours_per_week=1),
        ]
    )
    db_session.commit()

    proposals, unplaced = solve_missing_placements_whole_school(
        db_session,
        school_id=school.id,
        class_ids=[c1.id, c2.id],
        max_runtime_seconds=5,
    )

    assert unplaced == []
    assert len(proposals) == 2
    assert all(p.is_grouped for p in proposals)
    assert all(p.group_id == flow.id for p in proposals)
    assert len({p.lesson_slot_id for p in proposals}) == 1
    assert len({p.teacher_id for p in proposals}) == 1
    assert len({p.classroom_id for p in proposals}) == 1


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_cp_sat_respects_other_classes_teacher_and_room(db_session):
    """Single-class job must not reuse teacher/room slots held elsewhere in the school."""
    school = School(name="cp-sat-cross", address="a")
    db_session.add(school)
    db_session.flush()

    math = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    db_session.add(math)
    db_session.flush()

    c1 = StudentClass(class_name="10A", students_count=20, school_id=school.id)
    c2 = StudentClass(class_name="10B", students_count=20, school_id=school.id)
    db_session.add_all([c1, c2])
    db_session.flush()

    teacher = Teacher(
        full_name="Shared T",
        subjects=["Mathematics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    db_session.add(teacher)
    room = Classroom(
        room_number="101",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add(room)
    db_session.add_all([_slot(1, 1), _slot(1, 2)])
    db_session.flush()

    s1 = db_session.scalar(select(LessonSlot).where(LessonSlot.day_of_week == 1, LessonSlot.lesson_number == 1))
    s2 = db_session.scalar(select(LessonSlot).where(LessonSlot.day_of_week == 1, LessonSlot.lesson_number == 2))
    assert s1 is not None and s2 is not None
    # Other class already occupies teacher+room on first slot.
    db_session.add(
        ScheduleItem(
            class_id=c2.id,
            subject_id=math.id,
            teacher_id=teacher.id,
            classroom_id=room.id,
            lesson_slot_id=s1.id,
            is_grouped=False,
            group_id=None,
            school_id=school.id,
        )
    )
    db_session.add(
        ClassSubjectHours(school_id=school.id, class_id=c1.id, subject_id=math.id, hours_per_week=1)
    )
    db_session.commit()

    proposals, unplaced = solve_missing_placements_whole_school(
        db_session,
        school_id=school.id,
        class_ids=[c1.id],
        max_runtime_seconds=5,
    )

    assert unplaced == []
    assert len(proposals) == 1
    assert proposals[0].lesson_slot_id == s2.id
    assert proposals[0].teacher_id == teacher.id
    assert proposals[0].classroom_id == room.id


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_cp_sat_reports_infeasible_unit(db_session):
    school = School(name="cp-sat-infeasible", address="a")
    db_session.add(school)
    db_session.flush()

    math = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    db_session.add(math)
    db_session.flush()

    cls = StudentClass(class_name="10A", students_count=25, school_id=school.id)
    db_session.add(cls)
    db_session.flush()

    teacher = Teacher(
        full_name="Math Teacher",
        subjects=["Mathematics"],
        weekly_load_limit=0,
        unavailable_days=[1, 2, 3, 4, 5],
        school_id=school.id,
    )
    db_session.add(teacher)
    db_session.add(
        Classroom(
            room_number="101",
            capacity=30,
            specialization=ClassroomSpecialization.standard,
            school_id=school.id,
        )
    )
    db_session.add(_slot(1, 1))
    db_session.flush()

    db_session.add(
        ClassSubjectHours(school_id=school.id, class_id=cls.id, subject_id=math.id, hours_per_week=1)
    )
    db_session.commit()

    proposals, unplaced = solve_missing_placements_whole_school(
        db_session,
        school_id=school.id,
        class_ids=[cls.id],
        max_runtime_seconds=5,
    )

    assert proposals == []
    assert len(unplaced) == 1
    assert "CP_SAT_NO_FEASIBLE_ASSIGNMENT" in (unplaced[0].get("blocking_issues") or [])


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_cp_sat_respects_teacher_weekly_load_limit(db_session):
    school = School(name="cp-sat-load-cap", address="a")
    db_session.add(school)
    db_session.flush()

    math = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    db_session.add(math)
    db_session.flush()

    cls = StudentClass(class_name="10A", students_count=25, school_id=school.id)
    db_session.add(cls)
    db_session.flush()

    teacher = Teacher(
        full_name="Math Teacher",
        subjects=["Mathematics"],
        weekly_load_limit=2,
        unavailable_days=[],
        school_id=school.id,
    )
    room = Classroom(
        room_number="101",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add_all([teacher, room])
    slots = [_slot(d, n) for d in range(1, 4) for n in range(1, 4)]
    db_session.add_all(slots)
    db_session.flush()

    for slot in slots[:2]:
        db_session.add(
            ScheduleItem(
                school_id=school.id,
                class_id=cls.id,
                subject_id=math.id,
                teacher_id=teacher.id,
                classroom_id=room.id,
                lesson_slot_id=slot.id,
                is_grouped=False,
            )
        )
    db_session.add(
        ClassSubjectHours(school_id=school.id, class_id=cls.id, subject_id=math.id, hours_per_week=4)
    )
    db_session.commit()

    proposals, unplaced = solve_missing_placements_whole_school(
        db_session,
        school_id=school.id,
        class_ids=[cls.id],
        max_runtime_seconds=5,
    )

    assert len(proposals) <= 2
    assert all(p.teacher_id == teacher.id for p in proposals)
    if len(proposals) < 2:
        assert any(
            "TEACHER_LOAD_LIMIT_EXCEEDED" in (row.get("blocking_issues") or [])
            for row in unplaced
        )


def test_cp_sat_reports_runtime_unavailable_when_import_fails(db_session, monkeypatch):
    original_import = builtins.__import__

    def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ortools.sat.python":
            raise ImportError("missing ortools")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _patched_import)

    proposals, unplaced = solve_missing_placements_whole_school(
        db_session,
        school_id=1,
        class_ids=[1],
        max_runtime_seconds=1,
    )
    assert proposals == []
    assert len(unplaced) == 1
    assert "CP_SAT_RUNTIME_UNAVAILABLE" in (unplaced[0].get("blocking_issues") or [])
