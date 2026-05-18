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
from app.services.entitlements import require_capability
from app.services.plan_status import compute_schedule_plan_status
from app.services.schedule_exports import build_schedule_export
from app.services.school_readiness import invalidate_readiness_cache


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
    if current_user.role == UserRole.admin:
        if payload.plan is not None:
            from app.models.entities import SchoolPlan

            school.plan = SchoolPlan(payload.plan)
        if payload.trial_ends_at is not None:
            from datetime import datetime

            school.trial_ends_at = datetime.fromisoformat(payload.trial_ends_at.replace("Z", ""))
        if payload.subscription_ends_at is not None:
            from datetime import datetime

            school.subscription_ends_at = datetime.fromisoformat(payload.subscription_ends_at.replace("Z", ""))
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
    data = compute_schedule_plan_status(db, school_id)
    return SchedulePlanStatusOut(
        rows=data.rows_out,
        classes_without_plan=data.classes_without_plan,
        summary=data.summary,
    )


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
    invalidate_readiness_cache(payload.school_id)
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
    invalidate_readiness_cache(item.school_id)
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
    invalidate_readiness_cache(item.school_id)
    return {"ok": True}


@router.get("/schedule-exports")
def export_schedule(
    school_id: int,
    view: str = "class",
    format: str = "xlsx",
    entity_id: int | None = None,
    simple: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, school_id)
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    if format == "xlsx":
        require_capability(db, school, "export_xlsx")
    elif format == "pdf":
        from app.services.entitlements import has_pro_access

        if not has_pro_access(school) and not simple:
            require_capability(db, school, "export_pdf_full")
        if not has_pro_access(school):
            simple = True
            view = "school"
            entity_id = None
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
            simple=simple,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail={"key": "errors.requestValidation"}) from None
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type=media_type, headers=headers)
