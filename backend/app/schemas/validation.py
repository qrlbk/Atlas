from pydantic import BaseModel

from app.schemas.entities import ScheduleItemIn


class ValidationIssue(BaseModel):
    issue_code: str
    severity: str
    message: str
    message_params: dict | None = None
    entity_refs: dict
    slot_ref: dict | None = None
    suggested_fix: str | None = None
    weight: float = 0.0


class ValidationRequest(BaseModel):
    school_id: int
    candidate: ScheduleItemIn | None = None


class ValidationResponse(BaseModel):
    status: str
    issues: list[ValidationIssue]
    quality: dict | None = None
