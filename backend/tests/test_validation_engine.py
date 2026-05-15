"""Tests for schedule validation rules (SQLite fixtures)."""

from datetime import time

from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    ClassroomSpecialization,
    GroupFlow,
    LessonSlot,
    School,
    StudentClass,
    Subject,
    Teacher,
)
from app.schemas.entities import ScheduleItemIn
from app.services.validation_engine import validate_schedule
from app.models.entities import ScheduleItem


def _seed_minimal_school(db_session):
    school = School(name="T School", address="1 Test St")
    db_session.add(school)
    db_session.flush()

    sub_math = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    sub_physics = Subject(name="Physics", requires_special_room=True, required_specialization=ClassroomSpecialization.physics_lab)
    db_session.add_all([sub_math, sub_physics])
    db_session.flush()

    cls = StudentClass(class_name="9A", students_count=20, school_id=school.id)
    db_session.add(cls)
    db_session.flush()

    t_ok = Teacher(
        full_name="Teach Math",
        subjects=["Mathematics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    t_wrong = Teacher(
        full_name="Teach Only Math",
        subjects=["Mathematics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    db_session.add_all([t_ok, t_wrong])
    db_session.flush()

    room = Classroom(
        room_number="R1",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    lab = Classroom(
        room_number="LabP",
        capacity=30,
        specialization=ClassroomSpecialization.physics_lab,
        school_id=school.id,
    )
    db_session.add_all([room, lab])
    db_session.flush()

    slot1 = LessonSlot(day_of_week=1, lesson_number=1, start_time=time(8, 0), end_time=time(8, 45))
    slot2 = LessonSlot(day_of_week=1, lesson_number=2, start_time=time(8, 50), end_time=time(9, 35))
    db_session.add_all([slot1, slot2])
    db_session.flush()

    return {
        "school": school,
        "class": cls,
        "sub_math": sub_math,
        "sub_physics": sub_physics,
        "t_ok": t_ok,
        "t_wrong": t_wrong,
        "room": room,
        "lab": lab,
        "slot1": slot1,
        "slot2": slot2,
    }


def test_class_double_booking(db_session):
    s = _seed_minimal_school(db_session)
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_ok"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            group_id=None,
            school_id=s["school"].id,
        )
    )
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_ok"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            group_id=None,
            school_id=s["school"].id,
        )
    )
    db_session.commit()

    issues = validate_schedule(db_session, s["school"].id, None)
    codes = {i.issue_code for i in issues}
    assert "CLASS_DOUBLE_BOOKING" in codes


def test_teacher_subject_mismatch(db_session):
    s = _seed_minimal_school(db_session)
    # t_wrong only has Mathematics; teaching Physics in lab
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_physics"].id,
            teacher_id=s["t_wrong"].id,
            classroom_id=s["lab"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            group_id=None,
            school_id=s["school"].id,
        )
    )
    db_session.commit()

    issues = validate_schedule(db_session, s["school"].id, None)
    assert any(i.issue_code == "TEACHER_SUBJECT_MISMATCH" for i in issues)


def test_candidate_includes_mismatch(db_session):
    s = _seed_minimal_school(db_session)
    db_session.commit()

    candidate = ScheduleItemIn(
        class_id=s["class"].id,
        subject_id=s["sub_physics"].id,
        teacher_id=s["t_wrong"].id,
        classroom_id=s["lab"].id,
        lesson_slot_id=s["slot1"].id,
        is_grouped=False,
        group_id=None,
        school_id=s["school"].id,
    )
    issues = validate_schedule(db_session, s["school"].id, candidate)
    assert any(i.issue_code == "TEACHER_SUBJECT_MISMATCH" for i in issues)


def test_plan_underfilled(db_session):
    s = _seed_minimal_school(db_session)
    db_session.add(
        ClassSubjectHours(
            school_id=s["school"].id,
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            hours_per_week=5,
        )
    )
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_ok"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            group_id=None,
            school_id=s["school"].id,
        )
    )
    db_session.commit()
    issues = validate_schedule(db_session, s["school"].id, None)
    assert any(i.issue_code == "PLAN_UNDERFILLED" for i in issues)


def test_plan_overflow(db_session):
    s = _seed_minimal_school(db_session)
    db_session.add(
        ClassSubjectHours(
            school_id=s["school"].id,
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            hours_per_week=1,
        )
    )
    for slot in (s["slot1"], s["slot2"]):
        db_session.add(
            ScheduleItem(
                class_id=s["class"].id,
                subject_id=s["sub_math"].id,
                teacher_id=s["t_ok"].id,
                classroom_id=s["room"].id,
                lesson_slot_id=slot.id,
                is_grouped=False,
                group_id=None,
                school_id=s["school"].id,
            )
        )
    db_session.commit()
    issues = validate_schedule(db_session, s["school"].id, None)
    assert any(i.issue_code == "PLAN_OVERFLOW" for i in issues)


def test_plan_underfilled_severity_error_when_plan_compliance_error(db_session):
    s = _seed_minimal_school(db_session)
    school = db_session.get(School, s["school"].id)
    assert school is not None
    school.scheduling_preferences = {"plan_compliance": "error"}
    db_session.add(
        ClassSubjectHours(
            school_id=s["school"].id,
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            hours_per_week=5,
        )
    )
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_ok"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            group_id=None,
            school_id=s["school"].id,
        )
    )
    db_session.commit()
    issues = validate_schedule(db_session, s["school"].id, None)
    under = [i for i in issues if i.issue_code == "PLAN_UNDERFILLED"]
    assert len(under) == 1
    assert under[0].severity == "error"


def test_plan_underfilled_severity_warning_by_default(db_session):
    s = _seed_minimal_school(db_session)
    db_session.add(
        ClassSubjectHours(
            school_id=s["school"].id,
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            hours_per_week=5,
        )
    )
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_ok"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            group_id=None,
            school_id=s["school"].id,
        )
    )
    db_session.commit()
    issues = validate_schedule(db_session, s["school"].id, None)
    under = [i for i in issues if i.issue_code == "PLAN_UNDERFILLED"]
    assert len(under) == 1
    assert under[0].severity == "warning"


def test_class_shift_mismatch_from_school_preferences(db_session):
    s = _seed_minimal_school(db_session)
    school = db_session.get(School, s["school"].id)
    assert school is not None
    school.scheduling_preferences = {"class_shift_map": {str(s["class"].id): "afternoon"}, "shift_boundary_lesson": 4}
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_ok"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            group_id=None,
            school_id=s["school"].id,
        )
    )
    db_session.commit()
    issues = validate_schedule(db_session, s["school"].id, None)
    assert any(i.issue_code == "CLASS_SHIFT_MISMATCH" for i in issues)


def test_school_event_block_emits_issue(db_session):
    s = _seed_minimal_school(db_session)
    school = db_session.get(School, s["school"].id)
    assert school is not None
    school.scheduling_preferences = {"event_blocked_slot_ids": [s["slot1"].id], "event_block_severity": "error"}
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_ok"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            group_id=None,
            school_id=s["school"].id,
        )
    )
    db_session.commit()
    issues = validate_schedule(db_session, s["school"].id, None)
    blocked = [i for i in issues if i.issue_code == "SCHOOL_EVENT_BLOCK"]
    assert len(blocked) == 1
    assert blocked[0].severity == "error"


def test_grouped_joint_booking_allows_shared_teacher_and_room(db_session):
    s = _seed_minimal_school(db_session)
    cls_b = StudentClass(class_name="9B", students_count=18, school_id=s["school"].id)
    db_session.add(cls_b)
    db_session.flush()

    flow = GroupFlow(
        group_name="Stream",
        combined_classes=[s["class"].id, cls_b.id],
        school_id=s["school"].id,
    )
    db_session.add(flow)
    db_session.flush()

    for class_id in flow.combined_classes:
        db_session.add(
            ScheduleItem(
                class_id=class_id,
                subject_id=s["sub_physics"].id,
                teacher_id=s["t_ok"].id,
                classroom_id=s["lab"].id,
                lesson_slot_id=s["slot1"].id,
                is_grouped=True,
                group_id=flow.id,
                school_id=s["school"].id,
            )
        )
    db_session.commit()

    issues = validate_schedule(db_session, s["school"].id, None)
    codes = {i.issue_code for i in issues if i.severity == "error"}
    assert "TEACHER_DOUBLE_BOOKING" not in codes
    assert "CLASSROOM_DOUBLE_BOOKING" not in codes


def test_subject_teacher_inconsistent_when_configured(db_session):
    s = _seed_minimal_school(db_session)
    s["school"].scheduling_preferences = {"subject_teacher_consistency": "error"}
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_ok"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot1"].id,
            is_grouped=False,
            school_id=s["school"].id,
        )
    )
    db_session.add(
        ScheduleItem(
            class_id=s["class"].id,
            subject_id=s["sub_math"].id,
            teacher_id=s["t_wrong"].id,
            classroom_id=s["room"].id,
            lesson_slot_id=s["slot2"].id,
            is_grouped=False,
            school_id=s["school"].id,
        )
    )
    db_session.commit()
    issues = validate_schedule(db_session, s["school"].id, None)
    codes = {i.issue_code for i in issues if i.severity == "error"}
    assert "SUBJECT_TEACHER_INCONSISTENT" in codes
