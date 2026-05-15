from datetime import time

from app.models.entities import (
    Classroom,
    ClassroomSpecialization,
    LessonSlot,
    ScheduleItem,
    School,
    StudentClass,
    Subject,
    Teacher,
)
from app.services.scenario_engine import ScenarioConfig, apply_scenario


def _slot(day: int, lesson: int) -> LessonSlot:
    return LessonSlot(
        day_of_week=day,
        lesson_number=lesson,
        start_time=time(8, 0),
        end_time=time(9, 0),
    )


def test_shortened_day_deletes_late_lessons(db_session):
    school = School(name="sc-school", address="a")
    db_session.add(school)
    db_session.flush()
    subj = Subject(name="Math", requires_special_room=False, required_specialization=None)
    db_session.add(subj)
    cls = StudentClass(class_name="10A", students_count=20, school_id=school.id)
    t = Teacher(full_name="T", subjects=["Math"], weekly_load_limit=0, unavailable_days=[], school_id=school.id)
    room = Classroom(
        room_number="1",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add_all([cls, t, room])
    s1, s2 = _slot(1, 1), _slot(1, 5)
    db_session.add_all([s1, s2])
    db_session.flush()
    item_early = ScheduleItem(
        school_id=school.id,
        class_id=cls.id,
        subject_id=subj.id,
        teacher_id=t.id,
        classroom_id=room.id,
        lesson_slot_id=s1.id,
        is_grouped=False,
    )
    item_late = ScheduleItem(
        school_id=school.id,
        class_id=cls.id,
        subject_id=subj.id,
        teacher_id=t.id,
        classroom_id=room.id,
        lesson_slot_id=s2.id,
        is_grouped=False,
    )
    db_session.add_all([item_early, item_late])
    db_session.commit()

    ops, issues = apply_scenario(
        db_session,
        school.id,
        ScenarioConfig(scenario="shortened_day", day_of_week=1, max_lesson_number=3),
    )
    assert issues == []
    assert len(ops) == 1
    assert ops[0]["type"] == "delete"
    assert ops[0]["id"] == item_late.id
