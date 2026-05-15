from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_scope, get_current_user, require_roles
from app.core.db import get_db
from app.models.entities import (
    ClassSubjectHours,
    Classroom,
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
from app.schemas.entities import (
    ClassSubjectHoursIn,
    ClassSubjectHoursOut,
    ClassroomIn,
    ClassroomOut,
    GroupFlowIn,
    GroupFlowOut,
    LessonSlotOut,
    ScheduleItemIn,
    ScheduleItemOut,
    SchoolOut,
    SchoolPatch,
    StudentClassIn,
    StudentClassOut,
    SubjectOut,
    TeacherIn,
    TeacherOut,
)
from app.schemas.plan_status import (
    ClassWithoutPlanOut,
    PlanRowCoverageOut,
    SchedulePlanStatusOut,
    SchedulePlanSummaryOut,
)
from app.services.school_integrity import (
    assert_group_flow_payload_school_integrity,
    assert_schedule_payload_consistent,
    ensure_payload_school_id_matches_entity,
)
from app.services.schedule_exports import build_schedule_export


router = APIRouter()
manager_or_admin = require_roles(UserRole.admin, UserRole.school_manager)


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.admin:
        return list(db.scalars(select(School)))
    if current_user.school_id is not None:
        school = db.get(School, current_user.school_id)
        return [school] if school else []
    return []


@router.patch("/schools/{school_id}", response_model=SchoolOut)
def patch_school(
    school_id: int,
    payload: SchoolPatch,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    if payload.scheduling_preferences is not None:
        school.scheduling_preferences = payload.scheduling_preferences
    db.commit()
    db.refresh(school)
    return school


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ = current_user
    return list(db.scalars(select(Subject)))


@router.get("/lesson-slots", response_model=list[LessonSlotOut])
def list_lesson_slots(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ = current_user
    return list(db.scalars(select(LessonSlot)))


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    return list(db.scalars(select(Teacher).where(Teacher.school_id == school_id)))


@router.post("/teachers", response_model=TeacherOut)
def create_teacher(
    payload: TeacherIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    teacher = Teacher(**payload.model_dump())
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.patch("/teachers/{teacher_id}", response_model=TeacherOut)
def update_teacher(
    teacher_id: int,
    payload: TeacherIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail={"key": "errors.teacherNotFound"})
    enforce_school_scope(current_user, teacher.school_id)
    ensure_payload_school_id_matches_entity(payload_school_id=payload.school_id, entity_school_id=teacher.school_id)
    for key, value in payload.model_dump().items():
        setattr(teacher, key, value)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.delete("/teachers/{teacher_id}")
def delete_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail={"key": "errors.teacherNotFound"})
    enforce_school_scope(current_user, teacher.school_id)
    db.delete(teacher)
    db.commit()
    return {"ok": True}


@router.get("/classrooms", response_model=list[ClassroomOut])
def list_classrooms(school_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    enforce_school_scope(current_user, school_id)
    return list(db.scalars(select(Classroom).where(Classroom.school_id == school_id)))


@router.post("/classrooms", response_model=ClassroomOut)
def create_classroom(
    payload: ClassroomIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    classroom = Classroom(**payload.model_dump())
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


@router.patch("/classrooms/{classroom_id}", response_model=ClassroomOut)
def update_classroom(
    classroom_id: int,
    payload: ClassroomIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    classroom = db.get(Classroom, classroom_id)
    if not classroom:
        raise HTTPException(status_code=404, detail={"key": "errors.classroomNotFound"})
    enforce_school_scope(current_user, classroom.school_id)
    ensure_payload_school_id_matches_entity(payload_school_id=payload.school_id, entity_school_id=classroom.school_id)
    for key, value in payload.model_dump().items():
        setattr(classroom, key, value)
    db.commit()
    db.refresh(classroom)
    return classroom


@router.delete("/classrooms/{classroom_id}")
def delete_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    classroom = db.get(Classroom, classroom_id)
    if not classroom:
        raise HTTPException(status_code=404, detail={"key": "errors.classroomNotFound"})
    enforce_school_scope(current_user, classroom.school_id)
    db.delete(classroom)
    db.commit()
    return {"ok": True}


@router.get("/classes", response_model=list[StudentClassOut])
def list_classes(school_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    enforce_school_scope(current_user, school_id)
    return list(db.scalars(select(StudentClass).where(StudentClass.school_id == school_id)))


@router.post("/classes", response_model=StudentClassOut)
def create_class(
    payload: StudentClassIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    student_class = StudentClass(**payload.model_dump())
    db.add(student_class)
    db.commit()
    db.refresh(student_class)
    return student_class


@router.patch("/classes/{class_id}", response_model=StudentClassOut)
def update_class(
    class_id: int,
    payload: StudentClassIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    student_class = db.get(StudentClass, class_id)
    if not student_class:
        raise HTTPException(status_code=404, detail={"key": "errors.classNotFound"})
    enforce_school_scope(current_user, student_class.school_id)
    ensure_payload_school_id_matches_entity(
        payload_school_id=payload.school_id, entity_school_id=student_class.school_id
    )
    for key, value in payload.model_dump().items():
        setattr(student_class, key, value)
    db.commit()
    db.refresh(student_class)
    return student_class


@router.delete("/classes/{class_id}")
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    student_class = db.get(StudentClass, class_id)
    if not student_class:
        raise HTTPException(status_code=404, detail={"key": "errors.classNotFound"})
    enforce_school_scope(current_user, student_class.school_id)
    db.delete(student_class)
    db.commit()
    return {"ok": True}


@router.get("/grouped-flows", response_model=list[GroupFlowOut])
def list_grouped_flows(
    school_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    enforce_school_scope(current_user, school_id)
    return list(db.scalars(select(GroupFlow).where(GroupFlow.school_id == school_id)))


@router.post("/grouped-flows", response_model=GroupFlowOut)
def create_grouped_flow(
    payload: GroupFlowIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    assert_group_flow_payload_school_integrity(db, payload)
    flow = GroupFlow(**payload.model_dump())
    db.add(flow)
    db.commit()
    db.refresh(flow)
    return flow


@router.patch("/grouped-flows/{flow_id}", response_model=GroupFlowOut)
def update_grouped_flow(
    flow_id: int,
    payload: GroupFlowIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    flow = db.get(GroupFlow, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail={"key": "errors.groupedFlowNotFound"})
    enforce_school_scope(current_user, flow.school_id)
    ensure_payload_school_id_matches_entity(payload_school_id=payload.school_id, entity_school_id=flow.school_id)
    assert_group_flow_payload_school_integrity(db, payload)
    for key, value in payload.model_dump().items():
        setattr(flow, key, value)
    db.commit()
    db.refresh(flow)
    return flow


@router.delete("/grouped-flows/{flow_id}")
def delete_grouped_flow(
    flow_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    flow = db.get(GroupFlow, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail={"key": "errors.groupedFlowNotFound"})
    enforce_school_scope(current_user, flow.school_id)
    db.delete(flow)
    db.commit()
    return {"ok": True}


@router.get("/class-subject-hours", response_model=list[ClassSubjectHoursOut])
def list_class_subject_hours(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    return list(
        db.scalars(select(ClassSubjectHours).where(ClassSubjectHours.school_id == school_id).order_by(ClassSubjectHours.id))
    )


@router.post("/class-subject-hours", response_model=ClassSubjectHoursOut)
def create_class_subject_hours(
    payload: ClassSubjectHoursIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    student_class = db.get(StudentClass, payload.class_id)
    if not student_class or student_class.school_id != payload.school_id:
        raise HTTPException(status_code=400, detail={"key": "errors.classNotFoundInSchool"})
    if not db.get(Subject, payload.subject_id):
        raise HTTPException(status_code=400, detail={"key": "errors.subjectNotFound"})
    row = ClassSubjectHours(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/class-subject-hours/{row_id}", response_model=ClassSubjectHoursOut)
def update_class_subject_hours(
    row_id: int,
    payload: ClassSubjectHoursIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    row = db.get(ClassSubjectHours, row_id)
    if not row:
        raise HTTPException(status_code=404, detail={"key": "errors.curriculumRowNotFound"})
    enforce_school_scope(current_user, row.school_id)
    enforce_school_scope(current_user, payload.school_id)
    if row.school_id != payload.school_id:
        raise HTTPException(status_code=400, detail={"key": "errors.cannotChangeCurriculumSchool"})
    student_class = db.get(StudentClass, payload.class_id)
    if not student_class or student_class.school_id != payload.school_id:
        raise HTTPException(status_code=400, detail={"key": "errors.classNotFoundInSchool"})
    if not db.get(Subject, payload.subject_id):
        raise HTTPException(status_code=400, detail={"key": "errors.subjectNotFound"})
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/class-subject-hours/{row_id}")
def delete_class_subject_hours(
    row_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    row = db.get(ClassSubjectHours, row_id)
    if not row:
        raise HTTPException(status_code=404, detail={"key": "errors.curriculumRowNotFound"})
    enforce_school_scope(current_user, row.school_id)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/schedule-plan-status", response_model=SchedulePlanStatusOut)
def schedule_plan_status(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Planned vs actual lesson counts per curriculum row; classes with no plan rows."""
    enforce_school_scope(current_user, school_id)
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
    return SchedulePlanStatusOut(rows=rows_out, classes_without_plan=without_plan, summary=summary)


@router.get("/schedule", response_model=list[ScheduleItemOut])
def list_schedule(
    school_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    enforce_school_scope(current_user, school_id)
    return list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))


@router.post("/schedule", response_model=ScheduleItemOut)
def create_schedule_item(
    payload: ScheduleItemIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    assert_schedule_payload_consistent(db, payload)
    item = ScheduleItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/schedule/{item_id}", response_model=ScheduleItemOut)
def update_schedule_item(
    item_id: int,
    payload: ScheduleItemIn,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    item = db.get(ScheduleItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail={"key": "errors.scheduleItemNotFound"})
    enforce_school_scope(current_user, item.school_id)
    ensure_payload_school_id_matches_entity(payload_school_id=payload.school_id, entity_school_id=item.school_id)
    assert_schedule_payload_consistent(db, payload)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/schedule/{item_id}")
def delete_schedule_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
    current_user: User = Depends(get_current_user),
):
    item = db.get(ScheduleItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail={"key": "errors.scheduleItemNotFound"})
    enforce_school_scope(current_user, item.school_id)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/schedule-exports")
def export_schedule(
    school_id: int,
    view: str = "class",
    format: str = "xlsx",
    entity_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    if view not in {"class", "teacher", "school"}:
        raise HTTPException(status_code=400, detail={"key": "errors.requestValidation"})
    if format not in {"xlsx", "pdf"}:
        raise HTTPException(status_code=400, detail={"key": "errors.requestValidation"})
    try:
        payload, media_type, filename = build_schedule_export(
            db,
            school_id,
            view=view,  # type: ignore[arg-type]
            fmt=format,  # type: ignore[arg-type]
            entity_id=entity_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail={"key": "errors.requestValidation"}) from None
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type=media_type, headers=headers)
