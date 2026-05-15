"""Greedy solver against in-memory DB."""

from datetime import time

from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    ClassroomSpecialization,
    LessonSlot,
    ScheduleItem,
    School,
    StudentClass,
    Subject,
    Teacher,
)
from app.schemas.entities import ScheduleItemIn
from app.services.schedule_solver import (
    draft_teacher_absence,
    generate_draft_for_class,
    optimize_proposals_ga_fallback,
    optimize_proposals_local_search,
    suggest_slot_combinations,
)


def _tiny_world(db_session):
    school = School(name="S", address="a")
    db_session.add(school)
    db_session.flush()
    math = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    db_session.add(math)
    db_session.flush()
    cls = StudentClass(class_name="C1", students_count=15, school_id=school.id)
    db_session.add(cls)
    db_session.flush()
    t = Teacher(
        full_name="T",
        subjects=["Mathematics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    db_session.add(t)
    db_session.flush()
    room = Classroom(
        room_number="1",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add(room)
    db_session.flush()
    slot = LessonSlot(day_of_week=1, lesson_number=1, start_time=time(8, 0), end_time=time(8, 45))
    db_session.add(slot)
    db_session.flush()
    db_session.add(
        ClassSubjectHours(
            school_id=school.id,
            class_id=cls.id,
            subject_id=math.id,
            hours_per_week=1,
        )
    )
    db_session.commit()
    return {
        "school_id": school.id,
        "class_id": cls.id,
        "subject_id": math.id,
        "teacher_id": t.id,
        "classroom_id": room.id,
        "slot_id": slot.id,
    }


def test_suggest_slot_combinations_finds_error_free_pair(db_session):
    s = _tiny_world(db_session)
    base = ScheduleItemIn(
        class_id=s["class_id"],
        subject_id=s["subject_id"],
        teacher_id=s["teacher_id"],
        classroom_id=s["classroom_id"],
        lesson_slot_id=s["slot_id"],
        is_grouped=False,
        group_id=None,
        school_id=s["school_id"],
    )
    options = suggest_slot_combinations(db_session, s["school_id"], base, top_n=3)
    assert len(options) >= 1
    assert options[0]["lesson_slot_id"] == s["slot_id"]
    assert options[0]["classroom_id"] == s["classroom_id"]


def test_generate_draft_fills_one_missing_hour(db_session):
    s = _tiny_world(db_session)
    proposals, unplaced = generate_draft_for_class(db_session, s["school_id"], s["class_id"])
    assert len(proposals) == 1
    assert unplaced == []
    p = proposals[0]
    assert p.subject_id == s["subject_id"]
    assert p.class_id == s["class_id"]


def test_generate_draft_works_when_plan_compliance_is_error(db_session):
    """Greedy generator validates one lesson at a time; plan totals must not block each step."""
    s = _tiny_world(db_session)
    school = db_session.get(School, s["school_id"])
    assert school is not None
    school.scheduling_preferences = {"plan_compliance": "error"}
    db_session.commit()
    proposals, unplaced = generate_draft_for_class(db_session, s["school_id"], s["class_id"])
    assert len(proposals) == 1
    assert unplaced == []


def test_generate_draft_passes_pending_so_multi_hour_does_not_reuse_slot(db_session):
    """Each placement must see earlier proposals in this run (teacher/class/room conflicts)."""
    school = School(name="S2", address="a")
    db_session.add(school)
    db_session.flush()
    math = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    db_session.add(math)
    db_session.flush()
    cls = StudentClass(class_name="C1", students_count=15, school_id=school.id)
    db_session.add(cls)
    db_session.flush()
    t = Teacher(
        full_name="T",
        subjects=["Mathematics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    db_session.add(t)
    db_session.flush()
    room = Classroom(
        room_number="1",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add(room)
    db_session.flush()
    for day, lesson in ((1, 1), (1, 2)):
        db_session.add(
            LessonSlot(
                day_of_week=day,
                lesson_number=lesson,
                start_time=time(8, 0),
                end_time=time(8, 45),
            )
        )
    db_session.flush()
    db_session.add(
        ClassSubjectHours(
            school_id=school.id,
            class_id=cls.id,
            subject_id=math.id,
            hours_per_week=2,
        )
    )
    db_session.commit()

    proposals, unplaced = generate_draft_for_class(db_session, school.id, cls.id)
    assert unplaced == []
    assert len(proposals) == 2
    assert proposals[0].lesson_slot_id != proposals[1].lesson_slot_id


def test_generate_draft_matches_pe_teacher_alias(db_session):
    """Teacher may list 'PE' while the catalog subject is 'Physical Education'."""
    school = School(name="Spe", address="a")
    db_session.add(school)
    db_session.flush()
    pe = Subject(name="Physical Education", requires_special_room=False, required_specialization=None)
    db_session.add(pe)
    db_session.flush()
    cls = StudentClass(class_name="9Z", students_count=20, school_id=school.id)
    db_session.add(cls)
    db_session.flush()
    t = Teacher(
        full_name="Coach",
        subjects=["PE"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    db_session.add(t)
    db_session.flush()
    gym = Classroom(
        room_number="Gym",
        capacity=40,
        specialization=ClassroomSpecialization.gym,
        school_id=school.id,
    )
    std = Classroom(
        room_number="Hall",
        capacity=25,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add_all([gym, std])
    db_session.flush()
    slot = LessonSlot(day_of_week=2, lesson_number=3, start_time=time(10, 0), end_time=time(10, 45))
    db_session.add(slot)
    db_session.flush()
    db_session.add(
        ClassSubjectHours(school_id=school.id, class_id=cls.id, subject_id=pe.id, hours_per_week=1)
    )
    db_session.commit()

    proposals, unplaced = generate_draft_for_class(db_session, school.id, cls.id)
    assert unplaced == []
    assert len(proposals) == 1
    assert proposals[0].teacher_id == t.id


def test_generate_unplaced_includes_blocking_issues_without_teacher(db_session):
    school = School(name="NoTch", address="a")
    db_session.add(school)
    db_session.flush()
    chem = Subject(
        name="Chemistry",
        requires_special_room=True,
        required_specialization=ClassroomSpecialization.chemistry_lab,
    )
    db_session.add(chem)
    db_session.flush()
    cls = StudentClass(class_name="X", students_count=20, school_id=school.id)
    db_session.add(cls)
    db_session.flush()
    db_session.add(
        Teacher(
            full_name="OnlyMath",
            subjects=["Mathematics"],
            weekly_load_limit=10,
            unavailable_days=[],
            school_id=school.id,
        )
    )
    lab = Classroom(
        room_number="L",
        capacity=35,
        specialization=ClassroomSpecialization.chemistry_lab,
        school_id=school.id,
    )
    db_session.add(lab)
    slot = LessonSlot(day_of_week=1, lesson_number=1, start_time=time(8, 0), end_time=time(8, 45))
    db_session.add(slot)
    db_session.flush()
    db_session.add(
        ClassSubjectHours(school_id=school.id, class_id=cls.id, subject_id=chem.id, hours_per_week=2)
    )
    db_session.commit()

    proposals, unplaced = generate_draft_for_class(db_session, school.id, cls.id)
    assert proposals == []
    assert len(unplaced) == 2
    assert all(row["blocking_issues"] == ["NO_QUALIFIED_TEACHER"] for row in unplaced)


def test_draft_teacher_absence_produces_updates_or_deletes(db_session):
    s = _tiny_world(db_session)
    # Persist one lesson for the teacher so scenario has something to transform.
    db_session.add(
        ScheduleItem(
            class_id=s["class_id"],
            subject_id=s["subject_id"],
            teacher_id=s["teacher_id"],
            classroom_id=s["classroom_id"],
            lesson_slot_id=s["slot_id"],
            is_grouped=False,
            group_id=None,
            school_id=s["school_id"],
        )
    )
    # Substitute teacher can also teach the same subject.
    substitute = Teacher(
        full_name="Sub",
        subjects=["Mathematics"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=s["school_id"],
    )
    db_session.add(substitute)
    db_session.commit()

    operations, notes = draft_teacher_absence(
        db_session,
        s["school_id"],
        s["teacher_id"],
        day_of_week=1,
        substitute_teacher_id=substitute.id,
    )
    assert notes == []
    assert len(operations) == 1
    assert operations[0]["type"] == "update"
    assert operations[0]["payload"].teacher_id == substitute.id


def test_local_search_and_ga_optimizers_keep_shape(db_session):
    s = _tiny_world(db_session)
    proposals, _unplaced = generate_draft_for_class(db_session, s["school_id"], s["class_id"])
    improved_local = optimize_proposals_local_search(db_session, s["school_id"], proposals, iterations=5, seed=7)
    improved_ga = optimize_proposals_ga_fallback(
        db_session, s["school_id"], proposals, generations=3, population_size=4, seed=7
    )
    assert len(improved_local) == len(proposals)
    assert len(improved_ga) == len(proposals)
