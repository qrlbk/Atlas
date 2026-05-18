"""Tests for plan entitlements (402 on solver for free schools)."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import School, SchoolPlan, User, UserRole


def _ctx(api_client: TestClient, db_session: Session, *, pro: bool = False) -> dict:
    school = School(
        name="Entitlement School",
        address="Test",
        plan=SchoolPlan.pro if pro else SchoolPlan.free,
        trial_ends_at=None if pro else datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(school)
    db_session.flush()
    user = User(
        email=f"ent-{pro}@atlas.example.com",
        full_name="Ent Manager",
        password_hash=get_password_hash("pw"),
        role=UserRole.school_manager,
        school_id=school.id,
    )
    db_session.add(user)
    db_session.commit()
    login = api_client.post("/auth/login", json={"email": user.email, "password": "pw"})
    return {
        "school_id": school.id,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


def test_solver_blocked_on_free_plan(api_client: TestClient, db_session: Session):
    ctx = _ctx(api_client, db_session, pro=False)
    r = api_client.post(
        "/solver-jobs",
        headers=ctx["headers"],
        json={"school_id": ctx["school_id"], "strategy": "greedy"},
    )
    assert r.status_code == 402


def test_solver_allowed_on_pro_plan(api_client: TestClient, db_session: Session):
    ctx = _ctx(api_client, db_session, pro=True)
    r = api_client.post(
        "/solver-jobs",
        headers=ctx["headers"],
        json={"school_id": ctx["school_id"], "strategy": "greedy", "class_id": 1},
    )
    assert r.status_code in {200, 400}
