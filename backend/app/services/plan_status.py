"""Shared curriculum plan vs schedule coverage calculation."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import ClassSubjectHours, ScheduleItem, StudentClass, Subject


@dataclass
class PlanStatusData:
    rows_out: list
    classes_without_plan: list
    summary: dict
    lesson_count: int


def compute_schedule_plan_status(db: Session, school_id: int) -> PlanStatusData:
    from app.schemas.plan_status import (
        ClassWithoutPlanOut,
        PlanRowCoverageOut,
        SchedulePlanSummaryOut,
    )

    plan_rows = list(
        db.scalars(
            select(ClassSubjectHours).where(ClassSubjectHours.school_id == school_id).order_by(ClassSubjectHours.id)
        )
    )
    student_classes = list(db.scalars(select(StudentClass).where(StudentClass.school_id == school_id)))
    class_names = {c.id: c.class_name for c in student_classes}
    subject_names = {s.id: s.name for s in db.scalars(select(Subject))}

    count_rows = db.execute(
        select(ScheduleItem.class_id, ScheduleItem.subject_id, func.count(ScheduleItem.id))
        .where(ScheduleItem.school_id == school_id)
        .group_by(ScheduleItem.class_id, ScheduleItem.subject_id)
    ).all()
    counts: dict[tuple[int, int], int] = {(int(r[0]), int(r[1])): int(r[2]) for r in count_rows}

    lesson_count = int(
        db.scalar(select(func.count(ScheduleItem.id)).where(ScheduleItem.school_id == school_id)) or 0
    )

    rows_out: list[PlanRowCoverageOut] = []
    rows_under = 0
    rows_over = 0
    rows_exact = 0
    total_planned = 0
    total_matched = 0
    total_scheduled_on_plan = 0

    for plan in plan_rows:
        scheduled = counts.get((plan.class_id, plan.subject_id), 0)
        planned = plan.hours_per_week
        delta = scheduled - planned
        under = scheduled < planned
        over = scheduled > planned
        if under:
            rows_under += 1
        elif over:
            rows_over += 1
        else:
            rows_exact += 1
        total_planned += planned
        total_scheduled_on_plan += scheduled
        total_matched += min(scheduled, planned)
        rows_out.append(
            PlanRowCoverageOut(
                plan_id=plan.id,
                class_id=plan.class_id,
                subject_id=plan.subject_id,
                class_name=class_names.get(plan.class_id, ""),
                subject_name=subject_names.get(plan.subject_id, ""),
                planned_hours=planned,
                scheduled_hours=scheduled,
                delta=delta,
                under=under,
                over=over,
            )
        )

    classes_with_plan = {p.class_id for p in plan_rows}
    without_plan = [
        ClassWithoutPlanOut(class_id=c.id, class_name=c.class_name)
        for c in student_classes
        if c.id not in classes_with_plan
    ]

    fill_rate = 1.0 if total_planned <= 0 else round(total_matched / total_planned, 4)

    summary = SchedulePlanSummaryOut(
        plan_row_count=len(plan_rows),
        total_planned_hours=total_planned,
        total_scheduled_hours=total_scheduled_on_plan,
        rows_under=rows_under,
        rows_over=rows_over,
        rows_exact=rows_exact,
        classes_without_plan_count=len(without_plan),
        fill_rate=fill_rate,
    )
    return PlanStatusData(
        rows_out=rows_out,
        classes_without_plan=without_plan,
        summary=summary,
        lesson_count=lesson_count,
    )
