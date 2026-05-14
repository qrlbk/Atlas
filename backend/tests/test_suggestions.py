"""Auth and scope for read-only suggestion endpoints."""

from __future__ import annotations

from datetime import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    ClassroomSpecialization,
    LessonSlot,
    School,
    StudentClass,
    Subject,
    Teacher,
    User,
    UserRole,
)


def _token(api_client: TestClient, email: str) -> dict:
    r = api_client.post("/auth/login", json={"email": email, "password": "password"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_minimal_for_generate(db_session: Session) -> dict:
    school = School(name="S", address="a")
    db_session.add(school)
    db_session.flush()

    viewer = User(
        email="viewer@example.com",
        full_name="Viewer",
        password_hash=get_password_hash("password"),
        role=UserRole.viewer,
        school_id=school.id,
    )
    db_session.add(viewer)

    subj = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    db_session.add(subj)
    db_session.flush()

    cls = StudentClass(class_name="10A", students_count=20, school_id=school.id)
    db_session.add(cls)
    db_session.flush()

    t = Teacher(
        full_name="T",
        subjects=["Mathematics"],
        weekly_load_limit=24,
        unavailable_days=[],
        school_id=school.id,
    )
    db_session.add(t)
    room = Classroom(
        room_number="101",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add(room)
    slot = LessonSlot(day_of_week=1, lesson_number=1, start_time=time(8, 0), end_time=time(8, 45))
    db_session.add(slot)
    db_session.flush()

    db_session.add(
        ClassSubjectHours(school_id=school.id, class_id=cls.id, subject_id=subj.id, hours_per_week=1)
    )
    db_session.commit()

    return {"school_id": school.id, "class_id": cls.id}


def test_generate_class_allowed_for_viewer(api_client: TestClient, db_session: Session):
    ctx = _seed_minimal_for_generate(db_session)
    headers = _token(api_client, "viewer@example.com")
    r = api_client.post(
        "/suggestions/generate-class",
        json={"school_id": ctx["school_id"], "class_id": ctx["class_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["proposals"]) >= 1
    assert body["unplaced"] == []
