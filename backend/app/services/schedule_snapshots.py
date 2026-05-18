"""Immutable schedule snapshots for rollback."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import ScheduleItem, ScheduleSnapshot

MAX_SNAPSHOTS_PER_SCHOOL = 20


def _serialize_schedule_items(db: Session, school_id: int) -> list[dict]:
    items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))
    return [
        {
            "class_id": i.class_id,
            "subject_id": i.subject_id,
            "teacher_id": i.teacher_id,
            "classroom_id": i.classroom_id,
            "lesson_slot_id": i.lesson_slot_id,
            "is_grouped": i.is_grouped,
            "group_id": i.group_id,
            "school_id": i.school_id,
        }
        for i in items
    ]


def create_schedule_snapshot(
    db: Session,
    *,
    school_id: int,
    reason: str,
    label: str = "",
    user_id: int | None = None,
    commit: bool = True,
) -> ScheduleSnapshot:
    items_json = _serialize_schedule_items(db, school_id)
    snap = ScheduleSnapshot(
        school_id=school_id,
        label=label or reason,
        reason=reason,
        items_json=items_json,
        created_by=user_id,
    )
    db.add(snap)
    db.flush()
    _prune_old_snapshots(db, school_id)
    if commit:
        db.commit()
        db.refresh(snap)
    return snap


def _prune_old_snapshots(db: Session, school_id: int) -> None:
    ids = list(
        db.scalars(
            select(ScheduleSnapshot.id)
            .where(ScheduleSnapshot.school_id == school_id)
            .order_by(ScheduleSnapshot.created_at.desc())
        )
    )
    if len(ids) <= MAX_SNAPSHOTS_PER_SCHOOL:
        return
    for old_id in ids[MAX_SNAPSHOTS_PER_SCHOOL:]:
        db.execute(delete(ScheduleSnapshot).where(ScheduleSnapshot.id == old_id))


def restore_schedule_snapshot(
    db: Session,
    *,
    school_id: int,
    snapshot_id: int,
    user_id: int | None = None,
) -> ScheduleSnapshot:
    snap = db.get(ScheduleSnapshot, snapshot_id)
    if snap is None or snap.school_id != school_id:
        raise ValueError("snapshot_not_found")
    create_schedule_snapshot(
        db,
        school_id=school_id,
        reason="pre_restore",
        label=f"Before restore #{snapshot_id}",
        user_id=user_id,
        commit=False,
    )
    db.execute(delete(ScheduleItem).where(ScheduleItem.school_id == school_id))
    for row in snap.items_json:
        db.add(ScheduleItem(**row))
    db.commit()
    db.refresh(snap)
    return snap


def list_snapshots(db: Session, school_id: int) -> list[ScheduleSnapshot]:
    return list(
        db.scalars(
            select(ScheduleSnapshot)
            .where(ScheduleSnapshot.school_id == school_id)
            .order_by(ScheduleSnapshot.created_at.desc())
        )
    )
