"""Cross-entity checks: schedule rows and group flows must reference resources in the same school."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.entities import Classroom, GroupFlow, LessonSlot, StudentClass, Subject, Teacher
from app.schemas.entities import GroupFlowIn, ScheduleItemIn


def ensure_payload_school_id_matches_entity(*, payload_school_id: int, entity_school_id: int) -> None:
    if payload_school_id != entity_school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"key": "errors.cannotChangeEntitySchool"},
        )


def assert_combined_classes_in_school(db: Session, school_id: int, combined_class_ids: list[int]) -> None:
    for class_id in combined_class_ids:
        row = db.get(StudentClass, class_id)
        if row is None or row.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"key": "errors.classNotFoundInSchool"},
            )


def assert_group_flow_payload_school_integrity(db: Session, payload: GroupFlowIn) -> None:
    assert_combined_classes_in_school(db, payload.school_id, payload.combined_classes)


def assert_schedule_payload_consistent(db: Session, payload: ScheduleItemIn) -> None:
    school_id = payload.school_id

    student_class = db.get(StudentClass, payload.class_id)
    if student_class is None or student_class.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"key": "errors.classNotFoundInSchool"},
        )

    teacher = db.get(Teacher, payload.teacher_id)
    if teacher is None or teacher.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"key": "errors.teacherNotInSchool"},
        )

    classroom = db.get(Classroom, payload.classroom_id)
    if classroom is None or classroom.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"key": "errors.classroomNotInSchool"},
        )

    if db.get(Subject, payload.subject_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"key": "errors.subjectNotFound"},
        )

    if db.get(LessonSlot, payload.lesson_slot_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"key": "errors.lessonSlotNotFound"},
        )

    if payload.is_grouped:
        if payload.group_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"key": "errors.scheduleGroupRequired"},
            )
        flow = db.get(GroupFlow, payload.group_id)
        if flow is None or flow.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"key": "errors.groupFlowNotInSchool"},
            )
    elif payload.group_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"key": "errors.scheduleGroupForbidden"},
        )
