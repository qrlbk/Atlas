from pydantic import BaseModel, Field

from app.schemas.entities import ScheduleItemIn


class SuggestSlotsRequest(BaseModel):
    school_id: int
    candidate: ScheduleItemIn
    top_n: int = Field(default=8, ge=1, le=100)


class SlotSuggestionOut(BaseModel):
    lesson_slot_id: int
    classroom_id: int
    penalty: float


class GenerateClassRequest(BaseModel):
    school_id: int
    class_id: int


class UnplacedSubjectOut(BaseModel):
    subject_id: int
    subject_name: str | None = None
    class_ids: list[int] = Field(default_factory=list)
    group_id: int | None = None
    hours_missing: int = 1
    blocking_issues: list[str] = Field(default_factory=list)


class GenerateClassResponse(BaseModel):
    proposals: list[ScheduleItemIn]
    unplaced: list[UnplacedSubjectOut]


class ScheduleDraftOperationOut(BaseModel):
    type: str
    id: int | None = None
    payload: ScheduleItemIn | None = None


class ScenarioDraftRequest(BaseModel):
    school_id: int
    scenario: str = Field(
        default="teacher_absent",
        description="teacher_absent | substitute_teacher | shortened_day | room_unavailable | emergency_free",
    )
    teacher_id: int | None = None
    day_of_week: int | None = Field(default=None, ge=1, le=7)
    substitute_teacher_id: int | None = None
    original_teacher_id: int | None = None
    max_lesson_number: int | None = Field(default=None, ge=1, le=12)
    classroom_id: int | None = None
    class_id: int | None = None
    lesson_slot_id: int | None = None


class ScenarioDraftResponse(BaseModel):
    operations: list[ScheduleDraftOperationOut]
    issues: list[str]
