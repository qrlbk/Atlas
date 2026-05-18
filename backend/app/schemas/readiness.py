from pydantic import BaseModel, Field


class ReadinessBlockerOut(BaseModel):
    title: str
    detail: str = ""
    action_hint: str = ""
    severity: str = "warning"


class SchoolReadinessOut(BaseModel):
    status: str
    blockers: list[ReadinessBlockerOut] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


class ScheduleSnapshotOut(BaseModel):
    id: int
    school_id: int
    label: str
    reason: str
    created_at: str
    item_count: int


class HumanDiagnosticOut(BaseModel):
    title: str
    detail: str
    severity: str = "error"
