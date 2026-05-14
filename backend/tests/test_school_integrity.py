"""API-level checks for school-scoped FK integrity (TestClient + in-memory SQLite)."""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import (
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


def _seed_two_schools(db: Session) -> dict:
    s1 = School(name="School A", address="A St")
    s2 = School(name="School B", address="B St")
    db.add_all([s1, s2])
    db.flush()

    mgr_a = User(
        email="mgr-a@example.com",
        full_name="Manager A",
        password_hash=get_password_hash("password-a"),
        role=UserRole.school_manager,
        school_id=s1.id,
    )
    mgr_b = User(
        email="mgr-b@example.com",
        full_name="Manager B",
        password_hash=get_password_hash("password-b"),
        role=UserRole.school_manager,
        school_id=s2.id,
    )
    db.add_all([mgr_a, mgr_b])
    db.flush()

    subj = Subject(name="Math", requires_special_room=False, required_specialization=None)
    db.add(subj)
    db.flush()

    slot = LessonSlot(day_of_week=1, lesson_number=1, start_time=time(8, 0), end_time=time(8, 45))
    db.add(slot)
    db.flush()

    t_a = Teacher(
        full_name="Teacher A",
        subjects=["Math"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=s1.id,
    )
    t_b = Teacher(
        full_name="Teacher B",
        subjects=["Math"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=s2.id,
    )
    db.add_all([t_a, t_b])
    db.flush()

    c_a = StudentClass(class_name="1A", students_count=20, school_id=s1.id)
    c_b = StudentClass(class_name="1B", students_count=20, school_id=s2.id)
    db.add_all([c_a, c_b])
    db.flush()

    r_a = Classroom(
        room_number="R-A",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=s1.id,
    )
    r_b = Classroom(
        room_number="R-B",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=s2.id,
    )
    db.add_all([r_a, r_b])
    db.flush()

    db.commit()

    return {
        "school_a": s1,
        "school_b": s2,
        "mgr_a": mgr_a,
        "mgr_b": mgr_b,
        "subject": subj,
        "slot": slot,
        "t_a": t_a,
        "t_b": t_b,
        "c_a": c_a,
        "c_b": c_b,
        "r_a": r_a,
        "r_b": r_b,
    }


def _token(api_client, email: str, password: str) -> str:
    r = api_client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_schedule_post_rejects_teacher_from_other_school(api_client, db_session: Session):
    s = _seed_two_schools(db_session)
    token = _token(api_client, "mgr-a@example.com", "password-a")
    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "class_id": s["c_a"].id,
        "subject_id": s["subject"].id,
        "teacher_id": s["t_b"].id,
        "classroom_id": s["r_a"].id,
        "lesson_slot_id": s["slot"].id,
        "is_grouped": False,
        "group_id": None,
        "school_id": s["school_a"].id,
    }
    r = api_client.post("/schedule", json=body, headers=headers)
    assert r.status_code == 400
    assert r.json().get("code") == "errors.teacherNotInSchool"


def test_schedule_post_rejects_classroom_from_other_school(api_client, db_session: Session):
    s = _seed_two_schools(db_session)
    token = _token(api_client, "mgr-a@example.com", "password-a")
    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "class_id": s["c_a"].id,
        "subject_id": s["subject"].id,
        "teacher_id": s["t_a"].id,
        "classroom_id": s["r_b"].id,
        "lesson_slot_id": s["slot"].id,
        "is_grouped": False,
        "group_id": None,
        "school_id": s["school_a"].id,
    }
    r = api_client.post("/schedule", json=body, headers=headers)
    assert r.status_code == 400
    assert r.json().get("code") == "errors.classroomNotInSchool"


def test_grouped_flow_rejects_foreign_class(api_client, db_session: Session):
    s = _seed_two_schools(db_session)
    token = _token(api_client, "mgr-a@example.com", "password-a")
    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "group_name": "Bad",
        "combined_classes": [s["c_b"].id],
        "school_id": s["school_a"].id,
    }
    r = api_client.post("/grouped-flows", json=body, headers=headers)
    assert r.status_code == 400
    assert r.json().get("code") == "errors.classNotFoundInSchool"


def test_patch_teacher_rejects_school_id_change(api_client, db_session: Session):
    s = _seed_two_schools(db_session)
    token = _token(api_client, "mgr-a@example.com", "password-a")
    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "full_name": "Renamed",
        "subjects": ["Math"],
        "weekly_load_limit": 0,
        "unavailable_days": [],
        "school_id": s["school_b"].id,
    }
    r = api_client.patch(f"/teachers/{s['t_a'].id}", json=body, headers=headers)
    assert r.status_code == 400
    assert r.json().get("code") == "errors.cannotChangeEntitySchool"


def test_validation_with_candidate_rejects_cross_school_teacher(api_client, db_session: Session):
    s = _seed_two_schools(db_session)
    token = _token(api_client, "mgr-a@example.com", "password-a")
    headers = {"Authorization": f"Bearer {token}"}
    candidate = {
        "class_id": s["c_a"].id,
        "subject_id": s["subject"].id,
        "teacher_id": s["t_b"].id,
        "classroom_id": s["r_a"].id,
        "lesson_slot_id": s["slot"].id,
        "is_grouped": False,
        "group_id": None,
        "school_id": s["school_a"].id,
    }
    r = api_client.post("/validation", json={"school_id": s["school_a"].id, "candidate": candidate}, headers=headers)
    assert r.status_code == 400
    assert r.json().get("code") == "errors.teacherNotInSchool"


def test_suggestions_slots_rejects_cross_school_candidate(api_client, db_session: Session):
    s = _seed_two_schools(db_session)
    token = _token(api_client, "mgr-a@example.com", "password-a")
    headers = {"Authorization": f"Bearer {token}"}
    candidate = {
        "class_id": s["c_a"].id,
        "subject_id": s["subject"].id,
        "teacher_id": s["t_b"].id,
        "classroom_id": s["r_a"].id,
        "lesson_slot_id": s["slot"].id,
        "is_grouped": False,
        "group_id": None,
        "school_id": s["school_a"].id,
    }
    r = api_client.post("/suggestions/slots", json={"school_id": s["school_a"].id, "candidate": candidate}, headers=headers)
    assert r.status_code == 400
    assert r.json().get("code") == "errors.teacherNotInSchool"
