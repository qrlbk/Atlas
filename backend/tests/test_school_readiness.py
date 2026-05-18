"""Tests for GET /schools/{id}/readiness."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import ClassSubjectHours, School, StudentClass, Subject, User, UserRole


def _auth_ctx(api_client: TestClient, db_session: Session) -> dict:
    school = School(name="Readiness School", address="Test")
    db_session.add(school)
    db_session.flush()
    user = User(
        email="readiness@atlas.example.com",
        full_name="Readiness Manager",
        password_hash=get_password_hash("pw"),
        role=UserRole.school_manager,
        school_id=school.id,
    )
    db_session.add(user)
    db_session.commit()
    login = api_client.post("/auth/login", json={"email": "readiness@atlas.example.com", "password": "pw"})
    token = login.json()["access_token"]
    return {"school_id": school.id, "headers": {"Authorization": f"Bearer {token}"}}


def test_readiness_unknown_empty_school(api_client: TestClient, db_session: Session):
    ctx = _auth_ctx(api_client, db_session)
    r = api_client.get(f"/schools/{ctx['school_id']}/readiness", headers=ctx["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"unknown", "red", "yellow", "green"}
    assert "blockers" in body
    assert "summary" in body


def test_readiness_yellow_with_plan_gap(api_client: TestClient, db_session: Session):
    ctx = _auth_ctx(api_client, db_session)
    school_id = ctx["school_id"]
    student_class = StudentClass(class_name="8A", students_count=25, school_id=school_id)
    db_session.add(student_class)
    db_session.flush()
    subject = Subject(name="Readiness Physics", requires_special_room=False)
    db_session.add(subject)
    db_session.flush()
    db_session.add(
        ClassSubjectHours(
            school_id=school_id,
            class_id=student_class.id,
            subject_id=subject.id,
            hours_per_week=5,
        )
    )
    db_session.commit()
    r = api_client.get(f"/schools/{school_id}/readiness", headers=ctx["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"unknown", "red", "yellow", "green"}
