"""Tests for GET /schools response serialization."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import School, SchoolPlan, User, UserRole


def test_list_schools_serializes_datetime_fields(api_client: TestClient, db_session: Session):
    school = School(
        name="Serialize School",
        address="Addr",
        plan=SchoolPlan.pro,
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
        subscription_ends_at=datetime.utcnow() + timedelta(days=365),
    )
    db_session.add(school)
    db_session.flush()
    user = User(
        email="mgr-serialize@atlas.example.com",
        full_name="Mgr",
        password_hash=get_password_hash("pw"),
        role=UserRole.school_manager,
        school_id=school.id,
    )
    db_session.add(user)
    db_session.commit()

    login = api_client.post("/auth/login", json={"email": user.email, "password": "pw"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = api_client.get("/schools", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert isinstance(body[0]["trial_ends_at"], str)
    assert isinstance(body[0]["subscription_ends_at"], str)
