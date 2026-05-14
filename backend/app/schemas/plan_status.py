from pydantic import BaseModel, Field


class PlanRowCoverageOut(BaseModel):
    plan_id: int
    class_id: int
    subject_id: int
    class_name: str = ""
    subject_name: str = ""
    planned_hours: int = Field(ge=0)
    scheduled_hours: int = Field(ge=0)
    delta: int
    under: bool
    over: bool


class ClassWithoutPlanOut(BaseModel):
    class_id: int
    class_name: str


class SchedulePlanSummaryOut(BaseModel):
    """Aggregates for dashboards and future solver loops."""

    plan_row_count: int
    total_planned_hours: int
    total_scheduled_hours: int
    rows_under: int
    rows_over: int
    rows_exact: int
    classes_without_plan_count: int
    fill_rate: float = Field(
        description="Sum of min(planned, scheduled) per plan row / total planned hours (1.0 if no plan)."
    )


class SchedulePlanStatusOut(BaseModel):
    rows: list[PlanRowCoverageOut]
    classes_without_plan: list[ClassWithoutPlanOut]
    summary: SchedulePlanSummaryOut
