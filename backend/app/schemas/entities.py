from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, field_validator

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


def _serialize_school_scalar(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


class SchoolOut(BaseModel):
    id: int
    name: str
    address: str
    scheduling_preferences: dict | None = None
    plan: str = "free"
    trial_ends_at: str | None = None
    subscription_ends_at: str | None = None
    schedule_publish_state: str = "draft"
    published_at: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("trial_ends_at", "subscription_ends_at", "published_at", mode="before")
    @classmethod
    def _coerce_datetimes(cls, value: object | None) -> str | None:
        return _serialize_school_scalar(value)

    @field_validator("plan", "schedule_publish_state", mode="before")
    @classmethod
    def _coerce_enums(cls, value: object) -> str:
        return _serialize_school_scalar(value) or "free"


class SchoolPatch(BaseModel):
    scheduling_preferences: dict | None = None
    plan: str | None = None
    trial_ends_at: str | None = None
    subscription_ends_at: str | None = None
