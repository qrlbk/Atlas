"""Tests for GET /schedule-plan-status."""

from datetime import time

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.entities import (
    ClassSubjectHours,
    Classroom,
    ClassroomSpecialization,
    LessonSlot,
    ScheduleItem,
    School,
    StudentClass,
    Subject,
    Teacher,
    User,
    UserRole,
)


def _seed(api_client: TestClient, db_session):
    school = School(name="S", address="A")
    db_session.add(school)
    db_session.flush()

    admin = User(
        email="admin-plan@example.com",
        full_name="Admin",
        password_hash=get_password_hash("pw"),
        role=UserRole.admin,
        school_id=None,
    )
    db_session.add(admin)
    db_session.flush()

    subj = Subject(name="Math", requires_special_room=False, required_specialization=None)
    db_session.add(subj)
    db_session.flush()

    cls = StudentClass(class_name="9A", students_count=20, school_id=school.id)
    cls2 = StudentClass(class_name="9B", students_count=20, school_id=school.id)
    db_session.add_all([cls, cls2])
    db_session.flush()

    t = Teacher(
        full_name="T",
        subjects=["Math"],
        weekly_load_limit=0,
        unavailable_days=[],
        school_id=school.id,
    )
    room = Classroom(
        room_number="101",
        capacity=30,
        specialization=ClassroomSpecialization.standard,
        school_id=school.id,
    )
    slot = LessonSlot(day_of_week=1, lesson_number=1, start_time=time(8, 0), end_time=time(8, 45))
    db_session.add_all([t, room, slot])
    db_session.flush()

    plan = ClassSubjectHours(school_id=school.id, class_id=cls.id, subject_id=subj.id, hours_per_week=3)
    db_session.add(plan)
    db_session.add(
        ScheduleItem(
            class_id=cls.id,
            subject_id=subj.id,
            teacher_id=t.id,
            classroom_id=room.id,
            lesson_slot_id=slot.id,
            is_grouped=False,
            group_id=None,
            school_id=school.id,
        )
    )
    db_session.commit()

    login = api_client.post("/auth/login", json={"email": "admin-plan@example.com", "password": "pw"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "school_id": school.id,
        "class_id": cls.id,
        "class2_id": cls2.id,
        "subject_id": subj.id,
        "planned": 3,
        "scheduled": 1,
    }


def test_schedule_plan_status_counts(api_client: TestClient, db_session):
    ctx = _seed(api_client, db_session)
    r = api_client.get(f"/schedule-plan-status?school_id={ctx['school_id']}", headers=ctx["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["plan_row_count"] == 1
    assert data["summary"]["total_planned_hours"] == 3
    assert data["summary"]["total_scheduled_hours"] == 1
    assert data["summary"]["rows_under"] == 1
    assert data["summary"]["rows_over"] == 0
    assert data["summary"]["rows_exact"] == 0
    assert data["summary"]["fill_rate"] == round(1 / 3, 4)
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["planned_hours"] == 3
    assert row["scheduled_hours"] == 1
    assert row["delta"] == -2
    assert row["under"] is True
    assert row["over"] is False
    assert row["class_name"] == "9A"
    assert row["subject_name"] == "Math"


def test_classes_without_plan(api_client: TestClient, db_session):
    ctx = _seed(api_client, db_session)
    r = api_client.get(f"/schedule-plan-status?school_id={ctx['school_id']}", headers=ctx["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["classes_without_plan_count"] == 1
    names = {x["class_name"] for x in data["classes_without_plan"]}
    assert names == {"9B"}
