from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_scope, get_current_user
from app.core.db import get_db
from app.models.entities import LessonSlot, ScheduleItem, Teacher, User


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

    for item in items:
        counts[item.teacher_id] += 1
        slot = slots.get(item.lesson_slot_id)
        if slot:
            teacher_day[(item.teacher_id, slot.day_of_week)].append(slot.lesson_number)

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
        }
        for t in teachers
    ]
