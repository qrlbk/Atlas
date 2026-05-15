from datetime import time

from pydantic import BaseModel, ConfigDict

from app.models.entities import ClassroomSpecialization


class TeacherIn(BaseModel):
    full_name: str
    subjects: list[str] = []
    weekly_load_limit: int = 0
    unavailable_days: list[int] = []
    school_id: int


class TeacherOut(TeacherIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ClassroomIn(BaseModel):
    room_number: str
    capacity: int
    specialization: ClassroomSpecialization = ClassroomSpecialization.standard
    school_id: int


class ClassroomOut(ClassroomIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


class StudentClassIn(BaseModel):
    class_name: str
    students_count: int
    school_id: int


class StudentClassOut(StudentClassIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


class GroupFlowIn(BaseModel):
    group_name: str
    combined_classes: list[int]
    school_id: int


class GroupFlowOut(GroupFlowIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ClassSubjectHoursIn(BaseModel):
    school_id: int
    class_id: int
    subject_id: int
    hours_per_week: int


class ClassSubjectHoursOut(ClassSubjectHoursIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ScheduleItemIn(BaseModel):
    class_id: int
    subject_id: int
    teacher_id: int
    classroom_id: int
    lesson_slot_id: int
    is_grouped: bool = False
    group_id: int | None = None
    school_id: int


class ScheduleItemOut(ScheduleItemIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


class SubjectOut(BaseModel):
    id: int
    name: str
    requires_special_room: bool
    required_specialization: ClassroomSpecialization | None

    model_config = ConfigDict(from_attributes=True)


class LessonSlotOut(BaseModel):
    id: int
    day_of_week: int
    lesson_number: int
    start_time: time
    end_time: time

    model_config = ConfigDict(from_attributes=True)


class SchoolOut(BaseModel):
    id: int
    name: str
    address: str
    scheduling_preferences: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class SchoolPatch(BaseModel):
    scheduling_preferences: dict | None = None
