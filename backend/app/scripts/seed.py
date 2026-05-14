"""Idempotent database seed: demo school, admin (and optional manager), subjects, lesson slots."""

from __future__ import annotations

import os
from datetime import time

from sqlalchemy import select

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
        legacy_admin = db.scalar(select(User).where(User.email == "admin@atlas.local"))
        if legacy_admin:
            legacy_admin.email = admin_email
        legacy_manager = db.scalar(select(User).where(User.email == "manager@atlas.local"))
        if legacy_manager:
            legacy_manager.email = manager_email

        school = db.scalar(select(School).where(School.name == "Atlas Demo School"))
        if not school:
            school = School(name="Atlas Demo School", address="1 Seed Street")
            db.add(school)
            db.flush()

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

        subject_specs: list[tuple[str, bool, ClassroomSpecialization | None]] = [
            ("Mathematics", False, None),
            ("Chemistry", True, ClassroomSpecialization.chemistry_lab),
            ("Physics", True, ClassroomSpecialization.physics_lab),
            ("Physical Education", False, None),
        ]
        for name, req, spec in subject_specs:
            if not db.scalar(select(Subject).where(Subject.name == name)):
                db.add(
                    Subject(
                        name=name,
                        requires_special_room=req,
                        required_specialization=spec,
                    )
                )

        for day in range(1, 6):
            for lesson_number in range(1, 8):
                exists = db.scalar(
                    select(LessonSlot).where(
                        LessonSlot.day_of_week == day,
                        LessonSlot.lesson_number == lesson_number,
                    )
                )
                if exists:
                    continue
                start_minutes = 8 * 60 + (lesson_number - 1) * 45
                end_minutes = start_minutes + 45
                db.add(
                    LessonSlot(
                        day_of_week=day,
                        lesson_number=lesson_number,
                        start_time=_minutes_to_time(start_minutes),
                        end_time=_minutes_to_time(end_minutes),
                    )
                )

        # Demo core entities for quick UI/API testing.
        teacher_specs = [
            ("Aigerim K.", ["Mathematics"], 24, [5]),
            ("Nurlan P.", ["Physics"], 20, [3]),
            ("Dana S.", ["Chemistry"], 22, [2]),
            ("Marat A.", ["Physical Education"], 18, []),
        ]
        teacher_by_name: dict[str, Teacher] = {}
        for full_name, subjects, weekly_limit, unavailable_days in teacher_specs:
            teacher = db.scalar(
                select(Teacher).where(Teacher.school_id == school.id, Teacher.full_name == full_name)
            )
            if not teacher:
                teacher = Teacher(
                    full_name=full_name,
                    subjects=subjects,
                    weekly_load_limit=weekly_limit,
                    unavailable_days=unavailable_days,
                    school_id=school.id,
                )
                db.add(teacher)
                db.flush()
            teacher_by_name[full_name] = teacher

        # Lab capacity must fit largest class (10B=27) for chemistry/physics validation.
        classroom_specs = [
            ("101", 30, ClassroomSpecialization.standard),
            ("Lab-C1", 35, ClassroomSpecialization.chemistry_lab),
            ("Lab-P1", 35, ClassroomSpecialization.physics_lab),
            ("Gym-1", 40, ClassroomSpecialization.gym),
        ]
        classroom_by_number: dict[str, Classroom] = {}
        for room_number, capacity, specialization in classroom_specs:
            classroom = db.scalar(
                select(Classroom).where(Classroom.school_id == school.id, Classroom.room_number == room_number)
            )
            if not classroom:
                classroom = Classroom(
                    room_number=room_number,
                    capacity=capacity,
                    specialization=specialization,
                    school_id=school.id,
                )
                db.add(classroom)
                db.flush()
            classroom_by_number[room_number] = classroom

        class_specs = [("10A", 26), ("10B", 27), ("11A", 24), ("11B", 23)]
        class_by_name: dict[str, StudentClass] = {}
        for class_name, students_count in class_specs:
            student_class = db.scalar(
                select(StudentClass).where(StudentClass.school_id == school.id, StudentClass.class_name == class_name)
            )
            if not student_class:
                student_class = StudentClass(
                    class_name=class_name,
                    students_count=students_count,
                    school_id=school.id,
                )
                db.add(student_class)
                db.flush()
            class_by_name[class_name] = student_class

        flow_specs = [
            ("Science stream", ["10A", "10B"]),
            ("Senior track", ["11A", "11B"]),
        ]
        flow_by_name: dict[str, GroupFlow] = {}
        for group_name, class_names in flow_specs:
            combined_classes = [class_by_name[name].id for name in class_names]
            flow = db.scalar(select(GroupFlow).where(GroupFlow.school_id == school.id, GroupFlow.group_name == group_name))
            if not flow:
                flow = GroupFlow(group_name=group_name, combined_classes=combined_classes, school_id=school.id)
                db.add(flow)
                db.flush()
            flow_by_name[group_name] = flow

        subject_by_name = {subject.name: subject for subject in db.scalars(select(Subject))}
        slot_by_day_lesson = {
            (slot.day_of_week, slot.lesson_number): slot for slot in db.scalars(select(LessonSlot))
        }

        schedule_specs = [
            # class_name, subject_name, teacher_name, room_number, day, lesson, is_grouped, group_name
            ("10A", "Mathematics", "Aigerim K.", "101", 1, 1, False, None),
            ("10B", "Physics", "Nurlan P.", "Lab-P1", 1, 2, False, None),
            ("11A", "Chemistry", "Dana S.", "Lab-C1", 2, 3, False, None),
            ("11B", "Physical Education", "Marat A.", "Gym-1", 3, 4, False, None),
            ("10A", "Physics", "Nurlan P.", "Lab-P1", 4, 2, True, "Science stream"),
            ("11A", "Chemistry", "Dana S.", "Lab-C1", 5, 1, True, "Senior track"),
        ]
        for class_name, subject_name, teacher_name, room_number, day, lesson, is_grouped, group_name in schedule_specs:
            class_id = class_by_name[class_name].id
            subject_id = subject_by_name[subject_name].id
            teacher_id = teacher_by_name[teacher_name].id
            classroom_id = classroom_by_number[room_number].id
            lesson_slot_id = slot_by_day_lesson[(day, lesson)].id
            group_id = flow_by_name[group_name].id if group_name else None

            exists = db.scalar(
                select(ScheduleItem).where(
                    ScheduleItem.school_id == school.id,
                    ScheduleItem.class_id == class_id,
                    ScheduleItem.subject_id == subject_id,
                    ScheduleItem.teacher_id == teacher_id,
                    ScheduleItem.classroom_id == classroom_id,
                    ScheduleItem.lesson_slot_id == lesson_slot_id,
                )
            )
            if exists:
                continue
            db.add(
                ScheduleItem(
                    class_id=class_id,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    classroom_id=classroom_id,
                    lesson_slot_id=lesson_slot_id,
                    is_grouped=is_grouped,
                    group_id=group_id,
                    school_id=school.id,
                )
            )

        # Curriculum plan: match seeded schedule counts (one row per class/subject).
        curriculum_specs = [
            ("10A", "Mathematics", 1),
            ("10A", "Physics", 1),
            ("10B", "Physics", 1),
            ("11A", "Chemistry", 2),
            ("11B", "Physical Education", 1),
        ]
        for class_name, subject_name, hours in curriculum_specs:
            cid = class_by_name[class_name].id
            sid = subject_by_name[subject_name].id
            existing = db.scalar(
                select(ClassSubjectHours).where(
                    ClassSubjectHours.school_id == school.id,
                    ClassSubjectHours.class_id == cid,
                    ClassSubjectHours.subject_id == sid,
                )
            )
            if not existing:
                db.add(
                    ClassSubjectHours(
                        school_id=school.id,
                        class_id=cid,
                        subject_id=sid,
                        hours_per_week=hours,
                    )
                )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
