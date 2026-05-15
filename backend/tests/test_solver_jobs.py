"""Integration tests for POST /solver-jobs whole-school fill."""

import time
from datetime import time as dt_time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

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


def _seed_two_classes(api_client: TestClient, db_session: Session):
    school = School(name="SolverJob School", address="A")
    db_session.add(school)
    db_session.flush()

    user = User(
        email="solver-jobs@example.com",
        full_name="Manager",
        password_hash=get_password_hash("pw"),
        role=UserRole.school_manager,
        school_id=school.id,
    )
    db_session.add(user)
    db_session.flush()

    math = Subject(name="Mathematics", requires_special_room=False, required_specialization=None)
    db_session.add(math)
    db_session.flush()

    classes = []
    for name in ("9A", "9B"):
        cls = StudentClass(class_name=name, students_count=20, school_id=school.id)
        db_session.add(cls)
        classes.append(cls)
    db_session.flush()

    teacher = Teacher(
        full_name="T Math",
        subjects=["Mathematics"],
        weekly_load_limit=30,
        unavailable_days=[],
        school_id=school.id,
    )
    room = Classroom(
        room_number="101",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    db_session.add_all([teacher, room])
    db_session.flush()

    for day, lesson in ((1, 1), (1, 2), (2, 1), (2, 2)):
        db_session.add(
            LessonSlot(
                day_of_week=day,
                lesson_number=lesson,
                start_time=dt_time(8, 0),
                end_time=dt_time(8, 45),
            )
        )
    db_session.flush()

    for cls in classes:
        db_session.add(
            ClassSubjectHours(
                school_id=school.id,
                class_id=cls.id,
                subject_id=math.id,
                hours_per_week=2,
            )
        )
    db_session.commit()

    login = api_client.post("/auth/login", json={"email": "solver-jobs@example.com", "password": "pw"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "school_id": school.id,
        "class_ids": [c.id for c in classes],
    }


def _poll_job(api_client: TestClient, job_id: str, headers: dict, timeout_s: float = 30.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = api_client.get(f"/solver-jobs/{job_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        if data["status"] in ("completed", "failed", "cancelled"):
            return data
        time.sleep(0.2)
    raise AssertionError("solver job timed out")


def test_whole_school_solver_job_returns_multiple_creates(
    api_client: TestClient, db_session: Session, monkeypatch
):
    session_factory = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
    )
    monkeypatch.setattr("app.core.db.SessionLocal", session_factory)
    ctx = _seed_two_classes(api_client, db_session)
    r = api_client.post(
        "/solver-jobs",
        headers=ctx["headers"],
        json={
            "school_id": ctx["school_id"],
            "class_id": None,
            "strategy": "ga_fallback",
            "deterministic_seed": 7,
            "max_runtime_seconds": 25,
        },
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    result = _poll_job(api_client, job_id, ctx["headers"])
    assert result["status"] == "completed", result.get("error")
    assert len(result["operations"]) >= 3
    assert all(op["type"] == "create" for op in result["operations"])
