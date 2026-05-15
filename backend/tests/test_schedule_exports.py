from datetime import time

from app.models.entities import Classroom, ClassroomSpecialization, LessonSlot, ScheduleItem, School, StudentClass, Subject, Teacher
from app.services.schedule_exports import build_schedule_export


def _seed_export_world(db_session):
    school = School(name="Export School", address="A")
    db_session.add(school)
    db_session.flush()
    subject = Subject(name="Math", requires_special_room=False, required_specialization=None)
    db_session.add(subject)
    db_session.flush()
    student_class = StudentClass(class_name="7A", students_count=25, school_id=school.id)
    teacher = Teacher(
        full_name="Teacher One",
        subjects=["Math"],
        weekly_load_limit=20,
        unavailable_days=[],
        school_id=school.id,
    )
    room = Classroom(
        room_number="101",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add_all([student_class, teacher, room])
    db_session.flush()
    slot = LessonSlot(day_of_week=1, lesson_number=1, start_time=time(8, 0), end_time=time(8, 45))
    db_session.add(slot)
    db_session.flush()
    db_session.add(
        ScheduleItem(
            class_id=student_class.id,
            subject_id=subject.id,
            teacher_id=teacher.id,
            classroom_id=room.id,
            lesson_slot_id=slot.id,
            is_grouped=False,
            group_id=None,
            school_id=school.id,
        )
    )
    db_session.commit()
    return school.id, student_class.id, teacher.id


def test_build_schedule_export_xlsx_for_class(db_session):
    school_id, class_id, _teacher_id = _seed_export_world(db_session)
    payload, media_type, filename = build_schedule_export(
        db_session,
        school_id,
        view="class",
        fmt="xlsx",
        entity_id=class_id,
    )
    assert payload[:2] == b"PK"
    assert media_type.endswith("sheet")
    assert filename.endswith(".xlsx")


def test_build_schedule_export_pdf_for_teacher(db_session):
    school_id, _class_id, teacher_id = _seed_export_world(db_session)
    payload, media_type, filename = build_schedule_export(
        db_session,
        school_id,
        view="teacher",
        fmt="pdf",
        entity_id=teacher_id,
    )
    assert payload.startswith(b"%PDF-1.4")
    assert media_type == "application/pdf"
    assert filename.endswith(".pdf")
