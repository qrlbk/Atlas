from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_scope, get_current_user
from app.core.db import get_db
from app.models.entities import Classroom, LessonSlot, ScheduleItem, StudentClass, Teacher, User
from app.services.schedule_quality import score_validation_issues
from app.services.validation_engine import validate_schedule


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/teachers")
def teacher_analytics(
    school_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    enforce_school_scope(current_user, school_id)
    teachers = list(db.scalars(select(Teacher).where(Teacher.school_id == school_id)))
    items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))
    slots = {slot.id: slot for slot in db.scalars(select(LessonSlot))}

    counts = defaultdict(int)
    windows = defaultdict(int)
    teacher_day = defaultdict(list)
    daily_load = defaultdict(lambda: defaultdict(int))

    for item in items:
        counts[item.teacher_id] += 1
        slot = slots.get(item.lesson_slot_id)
        if slot:
            teacher_day[(item.teacher_id, slot.day_of_week)].append(slot.lesson_number)
            daily_load[item.teacher_id][slot.day_of_week] += 1

    for (teacher_id, _), lessons in teacher_day.items():
        uniq = sorted(set(lessons))
        for i in range(1, len(uniq)):
            if uniq[i] - uniq[i - 1] > 1:
                windows[teacher_id] += 1

    return [
        {
            "teacher_id": t.id,
            "teacher_name": t.full_name,
            "current_load": counts[t.id],
            "weekly_limit": t.weekly_load_limit,
            "windows": windows[t.id],
            "daily_load": dict(sorted(daily_load[t.id].items())),
            "max_daily_load": max(daily_load[t.id].values()) if daily_load[t.id] else 0,
        }
        for t in teachers
    ]


@router.get("/rooms")
def room_analytics(
    school_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    enforce_school_scope(current_user, school_id)
    rooms = list(db.scalars(select(Classroom).where(Classroom.school_id == school_id)))
    items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))
    classes = {c.id: c.students_count for c in db.scalars(select(StudentClass).where(StudentClass.school_id == school_id))}

    by_room = defaultdict(int)
    max_class_size = defaultdict(int)
    for item in items:
        by_room[item.classroom_id] += 1
        max_class_size[item.classroom_id] = max(max_class_size[item.classroom_id], classes.get(item.class_id, 0))

    return [
        {
            "room_id": room.id,
            "room_number": room.room_number,
            "specialization": room.specialization.value,
            "lessons_count": by_room[room.id],
            "capacity": room.capacity,
            "max_class_size": max_class_size[room.id],
            "over_capacity_risk": max_class_size[room.id] > room.capacity,
        }
        for room in rooms
    ]


@router.get("/schedule-quality")
def schedule_quality_analytics(
    school_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    enforce_school_scope(current_user, school_id)
    issues = validate_schedule(db, school_id)
    quality = score_validation_issues(issues)
    return {
        "issue_count": len(issues),
        "quality": quality,
    }
