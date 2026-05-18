"""Append-only audit log for school operations."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import SchoolEvent


def log_school_event(
    db: Session,
    *,
    school_id: int,
    event_type: str,
    user_id: int | None = None,
    payload: dict | None = None,
    commit: bool = False,
) -> SchoolEvent:
    row = SchoolEvent(
        school_id=school_id,
        user_id=user_id,
        event_type=event_type,
        payload=payload or {},
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row
