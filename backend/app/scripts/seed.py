"""Idempotent database seed: college demo with logically linked timetable data."""

from __future__ import annotations

import os
from datetime import time

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.core.security import get_password_hash
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
    User,
    UserRole,
)
from app.services.validation_engine import validate_schedule

DEMO_SCHOOL_NAME = "Atlas Demo School"
DEMO_SCHOOL_ADDRESS = "1 Seed Street"

DAY_NAME_TO_NUM = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
}

# (full_name, [subjects], weekly_load_limit, unavailable_day_names)
DEMO_TEACHERS: list[tuple[str, list[str], int, list[str]]] = [
    ("Айбек Нурланов", ["Mathematics"], 24, ["Friday"]),
    ("Жанар Садыкова", ["English"], 20, ["Wednesday"]),
    ("Руслан Толеубаев", ["Informatics"], 18, ["Monday"]),
    ("Алия Муратова", ["Chemistry"], 16, ["Thursday"]),
    ("Дамир Есенов", ["Physics"], 18, ["Tuesday"]),
    ("Сабина Касымова", ["Biology"], 20, ["Friday"]),
    ("Ермек Жумабек", ["PE"], 28, []),
    ("Лаура Ахметова", ["History"], 22, ["Monday"]),
    ("Марат Исмаилов", ["Kazakh Language"], 24, ["Thursday"]),
    ("Диана Серикова", ["Russian Language"], 24, ["Tuesday"]),
]

# (room_number, capacity, specialization enum)
DEMO_CLASSROOMS: list[tuple[str, int, ClassroomSpecialization]] = [
    ("101", 30, ClassroomSpecialization.standard),
    ("102", 28, ClassroomSpecialization.language_room),
    ("103", 30, ClassroomSpecialization.standard),
    ("104", 30, ClassroomSpecialization.chemistry_lab),
    ("105", 30, ClassroomSpecialization.physics_lab),
    ("106", 30, ClassroomSpecialization.standard),
    ("201", 35, ClassroomSpecialization.standard),
    ("202", 35, ClassroomSpecialization.standard),
    ("Gym", 60, ClassroomSpecialization.gym),
    ("Library", 40, ClassroomSpecialization.language_room),
]

DEMO_CLASSES: list[tuple[str, int]] = [
    ("7A", 26),
    ("7B", 24),
    ("8A", 28),
    ("8B", 27),
    ("9A", 25),
    ("9B", 23),
]

DEMO_FLOWS: list[tuple[str, list[str]]] = [
    ("English Advanced", ["8A", "8B"]),
    ("Robotics Club", ["9A", "9B"]),
    ("Olympiad Math", ["7A", "7B"]),
]
FLOW_CLASS_NAMES = {name: classes for name, classes in DEMO_FLOWS}

# (name, requires_special_room, required_specialization)
DEMO_SUBJECTS: list[tuple[str, bool, ClassroomSpecialization | None]] = [
    ("Mathematics", True, ClassroomSpecialization.standard),
    ("English", False, None),
    ("Informatics", True, ClassroomSpecialization.standard),
    ("Chemistry", True, ClassroomSpecialization.chemistry_lab),
    ("Physics", True, ClassroomSpecialization.physics_lab),
    ("Biology", True, ClassroomSpecialization.standard),
    ("PE", True, ClassroomSpecialization.gym),
    ("History", False, None),
    ("Kazakh Language", False, None),
    ("Russian Language", False, None),
]

# (class_name, subject_name, hours_per_week)
DEMO_PLAN_ROWS: list[tuple[str, str, int]] = [
    ("7A", "Mathematics", 5),
    ("7A", "English", 3),
    ("7A", "Informatics", 2),
    ("7A", "Chemistry", 2),
    ("7A", "PE", 3),
    ("7A", "History", 2),
    ("7A", "Kazakh Language", 4),
    ("7A", "Russian Language", 4),
    ("8A", "Mathematics", 5),
    ("8A", "English", 4),
    ("8A", "Informatics", 2),
    ("8A", "Physics", 3),
    ("8A", "Chemistry", 2),
    ("8A", "Biology", 2),
    ("8A", "PE", 3),
    ("9A", "Mathematics", 6),
    ("9A", "English", 4),
    ("9A", "Informatics", 3),
    ("9A", "Physics", 4),
    ("9A", "Chemistry", 3),
    ("9A", "Biology", 2),
    ("9A", "History", 2),
    ("7B", "Mathematics", 5),
    ("7B", "English", 3),
    ("7B", "Informatics", 2),
    ("7B", "Chemistry", 2),
    ("7B", "PE", 3),
    ("7B", "History", 2),
    ("7B", "Kazakh Language", 4),
    ("7B", "Russian Language", 4),
    ("8B", "Mathematics", 5),
    ("8B", "English", 4),
    ("8B", "Informatics", 2),
    ("8B", "Physics", 3),
    ("8B", "Chemistry", 2),
    ("8B", "Biology", 2),
    ("8B", "PE", 3),
    ("9B", "Mathematics", 6),
    ("9B", "English", 4),
    ("9B", "Informatics", 3),
    ("9B", "Physics", 4),
    ("9B", "Chemistry", 3),
    ("9B", "Biology", 2),
    ("9B", "History", 2),
]

# (day_name, lesson_number, start_h, start_m, end_h, end_m, class, subject, teacher, room)
# Adjustments vs the user's raw grid (teacher unavailable_days):
#   Mon 7A Informatics -> Wed L2 (Руслан unavailable Monday)
#   Tue 8A Physics -> Wed L1 (Дамир unavailable Tuesday)
#   Fri 8B Biology -> Thu L1 (Сабина unavailable Friday)
DEMO_LESSONS: list[tuple[str, int, int, int, int, int, str, str, str, str]] = [
    ("Monday", 1, 8, 0, 8, 45, "7A", "Mathematics", "Айбек Нурланов", "101"),
    ("Monday", 2, 8, 55, 9, 40, "7A", "English", "Жанар Садыкова", "102"),
    ("Monday", 3, 9, 50, 10, 35, "7A", "Chemistry", "Алия Муратова", "104"),
    ("Monday", 4, 10, 45, 11, 30, "7A", "PE", "Ермек Жумабек", "Gym"),
    ("Monday", 5, 11, 40, 12, 25, "7A", "Kazakh Language", "Марат Исмаилов", "201"),
    ("Tuesday", 1, 8, 0, 8, 45, "8A", "Mathematics", "Айбек Нурланов", "101"),
    ("Tuesday", 2, 8, 55, 9, 40, "8A", "Chemistry", "Алия Муратова", "104"),
    ("Tuesday", 3, 9, 50, 10, 35, "8A", "English", "Жанар Садыкова", "102"),
    ("Tuesday", 4, 10, 45, 11, 30, "8A", "Biology", "Сабина Касымова", "106"),
    ("Tuesday", 5, 11, 40, 12, 25, "8A", "PE", "Ермек Жумабек", "Gym"),
    ("Wednesday", 1, 8, 0, 8, 45, "8A", "Physics", "Дамир Есенов", "105"),
    ("Wednesday", 2, 8, 55, 9, 40, "7A", "Informatics", "Руслан Толеубаев", "103"),
    ("Wednesday", 3, 9, 50, 10, 35, "9A", "Mathematics", "Айбек Нурланов", "101"),
    ("Wednesday", 4, 10, 45, 11, 30, "9A", "Physics", "Дамир Есенов", "105"),
    ("Wednesday", 5, 11, 40, 12, 25, "9A", "Informatics", "Руслан Толеубаев", "103"),
    ("Wednesday", 6, 13, 35, 14, 20, "9A", "Chemistry", "Алия Муратова", "104"),
    ("Wednesday", 7, 14, 25, 15, 10, "9A", "History", "Лаура Ахметова", "202"),
    ("Thursday", 1, 8, 0, 8, 45, "8B", "Biology", "Сабина Касымова", "106"),
    ("Thursday", 1, 8, 0, 8, 45, "7B", "Russian Language", "Диана Серикова", "102"),
    ("Thursday", 2, 8, 55, 9, 40, "7B", "Mathematics", "Айбек Нурланов", "101"),
    ("Thursday", 3, 9, 50, 10, 35, "7B", "PE", "Ермек Жумабек", "Gym"),
    ("Thursday", 4, 10, 45, 11, 30, "7B", "History", "Лаура Ахметова", "201"),
    ("Thursday", 5, 11, 40, 12, 25, "7B", "English", "Жанар Садыкова", "102"),
    ("Friday", 1, 8, 0, 8, 45, "8B", "Physics", "Дамир Есенов", "105"),
    ("Friday", 2, 8, 55, 9, 40, "8B", "Chemistry", "Алия Муратова", "104"),
    ("Friday", 3, 9, 50, 10, 35, "8B", "Informatics", "Руслан Толеубаев", "103"),
    ("Friday", 4, 10, 45, 11, 30, "8B", "PE", "Ермек Жумабек", "Gym"),
]


def effective_demo_plan_rows() -> list[tuple[str, str, int]]:
    if os.environ.get("ATLAS_DEMO_GENERATION_PROFILE", "").strip().lower() == "sparse":
        return [(c, s, h + 2) for c, s, h in DEMO_PLAN_ROWS]
    return list(DEMO_PLAN_ROWS)


def _day_nums(day_names: list[str]) -> list[int]:
    out: list[int] = []
    for name in day_names:
        key = name.strip().casefold()
        if key in ("none", "", "—", "-"):
            continue
        num = DAY_NAME_TO_NUM.get(key)
        if num is None:
            raise ValueError(f"Unknown day name: {name!r}")
        out.append(num)
    return out


def _time(h: int, m: int) -> time:
    return time(hour=h, minute=m)


def _clear_school_data(db, school_id: int) -> None:
    db.execute(delete(ScheduleItem).where(ScheduleItem.school_id == school_id))
    db.execute(delete(ClassSubjectHours).where(ClassSubjectHours.school_id == school_id))
    db.execute(delete(GroupFlow).where(GroupFlow.school_id == school_id))
    db.execute(delete(StudentClass).where(StudentClass.school_id == school_id))
    db.execute(delete(Teacher).where(Teacher.school_id == school_id))
    db.execute(delete(Classroom).where(Classroom.school_id == school_id))
    db.flush()


def _ensure_lesson_slots(db) -> dict[tuple[int, int], LessonSlot]:
    slot_times: dict[tuple[int, int], tuple[time, time]] = {}
    for day_name, lesson_number, sh, sm, eh, em, *_rest in DEMO_LESSONS:
        day = DAY_NAME_TO_NUM[day_name.casefold()]
        slot_times[(day, lesson_number)] = (_time(sh, sm), _time(eh, em))
    for day in range(1, 6):
        for lesson_number in range(1, 8):
            if (day, lesson_number) not in slot_times:
                start_minutes = 8 * 60 + (lesson_number - 1) * 50
                slot_times[(day, lesson_number)] = (
                    _minutes_to_time(start_minutes),
                    _minutes_to_time(start_minutes + 45),
                )

    slot_by_key: dict[tuple[int, int], LessonSlot] = {}
    for (day, lesson_number), (start_t, end_t) in slot_times.items():
        slot = db.scalar(
            select(LessonSlot).where(
                LessonSlot.day_of_week == day,
                LessonSlot.lesson_number == lesson_number,
            )
        )
        if not slot:
            slot = LessonSlot(
                day_of_week=day,
                lesson_number=lesson_number,
                start_time=start_t,
                end_time=end_t,
            )
            db.add(slot)
            db.flush()
        else:
            slot.start_time = start_t
            slot.end_time = end_t
        slot_by_key[(day, lesson_number)] = slot
    return slot_by_key


def _minutes_to_time(total_minutes: int) -> time:
    h, m = divmod(total_minutes, 60)
    return time(hour=h, minute=m)


def run_seed() -> None:
    admin_email = os.environ.get("ATLAS_SEED_ADMIN_EMAIL", "admin@atlas.example.com")
    admin_password = os.environ.get("ATLAS_SEED_ADMIN_PASSWORD", "AtlasSeed!2026")
    manager_email = os.environ.get("ATLAS_SEED_MANAGER_EMAIL", "manager@atlas.example.com")
    manager_password = os.environ.get("ATLAS_SEED_MANAGER_PASSWORD", "AtlasSeed!2026")

    db = SessionLocal()
    try:
        for legacy_email, new_email in (("admin@atlas.local", admin_email), ("manager@atlas.local", manager_email)):
            legacy = db.scalar(select(User).where(User.email == legacy_email))
            if legacy:
                legacy.email = new_email

        from datetime import datetime, timedelta

        from app.models.entities import SchedulePublishState, SchoolPlan

        school = db.scalar(select(School).where(School.name == DEMO_SCHOOL_NAME))
        if not school:
            school = School(name=DEMO_SCHOOL_NAME, address=DEMO_SCHOOL_ADDRESS)
            db.add(school)
            db.flush()
        else:
            school.address = DEMO_SCHOOL_ADDRESS
        school.plan = SchoolPlan.pro
        school.trial_ends_at = datetime.utcnow() + timedelta(days=14)
        school.schedule_publish_state = SchedulePublishState.draft
        prefs = dict(school.scheduling_preferences or {})
        prefs["onboarding_completed"] = True
        school.scheduling_preferences = prefs

        if not db.scalar(select(User).where(User.email == admin_email)):
            db.add(
                User(
                    email=admin_email,
                    full_name="Seed Admin",
                    password_hash=get_password_hash(admin_password),
                    role=UserRole.admin,
                    school_id=None,
                )
            )
        if not db.scalar(select(User).where(User.email == manager_email)):
            db.add(
                User(
                    email=manager_email,
                    full_name="Seed Manager",
                    password_hash=get_password_hash(manager_password),
                    role=UserRole.school_manager,
                    school_id=school.id,
                )
            )

        for name, requires_special, required_specialization in DEMO_SUBJECTS:
            subject = db.scalar(select(Subject).where(Subject.name == name))
            if not subject:
                subject = Subject(name=name)
                db.add(subject)
                db.flush()
            subject.requires_special_room = requires_special
            subject.required_specialization = required_specialization

        _clear_school_data(db, school.id)
        slot_by_day_lesson = _ensure_lesson_slots(db)

        teacher_by_name: dict[str, Teacher] = {}
        for full_name, subjects, weekly_limit, unavailable_names in DEMO_TEACHERS:
            teacher = Teacher(
                full_name=full_name,
                subjects=subjects,
                weekly_load_limit=weekly_limit,
                unavailable_days=_day_nums(unavailable_names),
                school_id=school.id,
            )
            db.add(teacher)
            db.flush()
            teacher_by_name[full_name] = teacher

        classroom_by_number: dict[str, Classroom] = {}
        for room_number, capacity, specialization in DEMO_CLASSROOMS:
            classroom = Classroom(
                room_number=room_number,
                capacity=capacity,
                specialization=specialization,
                school_id=school.id,
            )
            db.add(classroom)
            db.flush()
            classroom_by_number[room_number] = classroom

        class_by_name: dict[str, StudentClass] = {}
        for class_name, students_count in DEMO_CLASSES:
            student_class = StudentClass(
                class_name=class_name,
                students_count=students_count,
                school_id=school.id,
            )
            db.add(student_class)
            db.flush()
            class_by_name[class_name] = student_class

        for flow_name, class_names in DEMO_FLOWS:
            db.add(
                GroupFlow(
                    group_name=flow_name,
                    combined_classes=[class_by_name[n].id for n in class_names],
                    school_id=school.id,
                )
            )
        db.flush()

        subject_by_name = {s.name: s for s in db.scalars(select(Subject))}

        for day_name, lesson_number, *_rest, class_name, subject_name, teacher_name, room_number in DEMO_LESSONS:
            day = DAY_NAME_TO_NUM[day_name.casefold()]
            slot = slot_by_day_lesson[(day, lesson_number)]
            student_class = class_by_name[class_name]
            if student_class.students_count > classroom_by_number[room_number].capacity:
                raise ValueError(
                    f"Capacity: {class_name} ({student_class.students_count}) > room {room_number}"
                )
            db.add(
                ScheduleItem(
                    class_id=student_class.id,
                    subject_id=subject_by_name[subject_name].id,
                    teacher_id=teacher_by_name[teacher_name].id,
                    classroom_id=classroom_by_number[room_number].id,
                    lesson_slot_id=slot.id,
                    is_grouped=False,
                    group_id=None,
                    school_id=school.id,
                )
            )

        for class_name, subject_name, hours in effective_demo_plan_rows():
            db.add(
                ClassSubjectHours(
                    school_id=school.id,
                    class_id=class_by_name[class_name].id,
                    subject_id=subject_by_name[subject_name].id,
                    hours_per_week=hours,
                )
            )

        db.commit()

        issues = validate_schedule(db, school.id, None, check_curriculum_totals=True)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            codes = sorted({i.issue_code for i in errors})
            raise RuntimeError(f"Seed schedule failed validation: {codes}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
