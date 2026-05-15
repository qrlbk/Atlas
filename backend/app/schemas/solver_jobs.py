from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.suggestions import ScheduleDraftOperationOut


class SolverJobCreateRequest(BaseModel):
    school_id: int
    class_id: int | None = None
    strategy: str = Field(default="cp_sat")
    frozen_lesson_slot_ids: list[int] = Field(default_factory=list)
    max_runtime_seconds: int = Field(default=20, ge=5, le=300)
    deterministic_seed: int = Field(default=42, ge=0, le=2_147_483_647)
    regenerate_mode: str = Field(default="fill_gaps", description="fill_gaps | from_plan")


class SolverJobCreateResponse(BaseModel):
    job_id: str
    status: str


class SolverJobStatusResponse(BaseModel):
    job_id: str
    status: str
    strategy: str
    progress: float
    error: str | None = None
    operations: list[ScheduleDraftOperationOut] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    quality: dict | None = None
