import enum
from datetime import datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    school_manager = "school_manager"
    viewer = "viewer"


class ClassroomSpecialization(str, enum.Enum):
    standard = "standard"
    chemistry_lab = "chemistry_lab"
    physics_lab = "physics_lab"
    gym = "gym"
    language_room = "language_room"


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scheduling_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), nullable=True)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subjects: Mapped[list[str]] = mapped_column(JSON, default=list)
    weekly_load_limit: Mapped[int] = mapped_column(Integer, default=0)
    unavailable_days: Mapped[list[int]] = mapped_column(JSON, default=list)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    specialization: Mapped[ClassroomSpecialization] = mapped_column(
        Enum(ClassroomSpecialization), default=ClassroomSpecialization.standard
    )
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)


class StudentClass(Base):
    __tablename__ = "student_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False)
    students_count: Mapped[int] = mapped_column(Integer, nullable=False)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    requires_special_room: Mapped[bool] = mapped_column(Boolean, default=False)
    required_specialization: Mapped[ClassroomSpecialization | None] = mapped_column(
        Enum(ClassroomSpecialization), nullable=True
    )


class LessonSlot(Base):
    __tablename__ = "lesson_slots"
    __table_args__ = (UniqueConstraint("day_of_week", "lesson_number", name="uq_slot_day_lesson"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class GroupFlow(Base):
    __tablename__ = "group_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_name: Mapped[str] = mapped_column(String(100), nullable=False)
    combined_classes: Mapped[list[int]] = mapped_column(JSON, default=list)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)


class ClassSubjectHours(Base):
    """Planned weekly lesson count per class and subject."""

    __tablename__ = "class_subject_hours"
    __table_args__ = (UniqueConstraint("school_id", "class_id", "subject_id", name="uq_class_subject_hours"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("student_classes.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False)


class ScheduleItem(Base):
    __tablename__ = "schedule_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("student_classes.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False, index=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), nullable=False, index=True)
    lesson_slot_id: Mapped[int] = mapped_column(ForeignKey("lesson_slots.id"), nullable=False, index=True)
    is_grouped: Mapped[bool] = mapped_column(Boolean, default=False)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("group_flows.id"), nullable=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)

    lesson_slot: Mapped[LessonSlot] = relationship()
    teacher: Mapped[Teacher] = relationship()
    classroom: Mapped[Classroom] = relationship()
    student_class: Mapped[StudentClass] = relationship()
    subject: Mapped[Subject] = relationship()
