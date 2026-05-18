"""Admin console API tests."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.entities import School, SchoolEvent, SchoolPlan, User, UserRole


def _admin_ctx(api_client: TestClient, db_session: Session) -> dict:
    admin = User(
        email="admin-test@atlas.example.com",
        full_name="Admin",
        password_hash=get_password_hash("adminpw"),
        role=UserRole.admin,
        school_id=None,
    )
    db_session.add(admin)
    db_session.commit()
    login = api_client.post("/auth/login", json={"email": admin.email, "password": "adminpw"})
    return {"headers": {"Authorization": f"Bearer {login.json()['access_token']}"}, "user_id": admin.id}


def _manager_ctx(api_client: TestClient, db_session: Session) -> dict:
    school = School(name="Mgr School", address="Addr")
    db_session.add(school)
    db_session.flush()
    user = User(
        email="mgr-test@atlas.example.com",
        full_name="Manager",
        password_hash=get_password_hash("mgrpw"),
        role=UserRole.school_manager,
        school_id=school.id,
    )
    db_session.add(user)
    db_session.commit()
    login = api_client.post("/auth/login", json={"email": user.email, "password": "mgrpw"})
    return {
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        "school_id": school.id,
    }


def test_auth_me(api_client: TestClient, db_session: Session):
    ctx = _admin_ctx(api_client, db_session)
    r = api_client.get("/auth/me", headers=ctx["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "admin"
    assert data["email"] == "admin-test@atlas.example.com"


def test_manager_forbidden_on_admin_dashboard(api_client: TestClient, db_session: Session):
    ctx = _manager_ctx(api_client, db_session)
    r = api_client.get("/admin/dashboard", headers=ctx["headers"])
    assert r.status_code == 403


def test_admin_dashboard(api_client: TestClient, db_session: Session):
    ctx = _admin_ctx(api_client, db_session)
    school = School(name="Dash School", address="A", plan=SchoolPlan.free)
    db_session.add(school)
    db_session.commit()
    r = api_client.get("/admin/dashboard", headers=ctx["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["total_schools"] >= 1
    assert "attention" in data


def test_create_school_and_event(api_client: TestClient, db_session: Session):
    ctx = _admin_ctx(api_client, db_session)
    r = api_client.post(
        "/admin/schools",
        headers=ctx["headers"],
        json={
            "name": "New Academy",
            "address": "Street 1",
            "manager_email": "new-mgr@school.kz",
            "manager_full_name": "New Manager",
            "trial_days": 14,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["school_id"] > 0
    assert body["manager_password"]
    school_id = body["school_id"]

    user = db_session.query(User).filter(User.email == "new-mgr@school.kz").one()
    assert user.school_id == school_id

    events = list(
        db_session.query(SchoolEvent).filter(
            SchoolEvent.school_id == school_id,
            SchoolEvent.event_type == "admin.school_created",
        )
    )
    assert len(events) == 1
    assert "password" not in str(events[0].payload).lower()


def test_extend_trial_and_activate_pro(api_client: TestClient, db_session: Session):
    ctx = _admin_ctx(api_client, db_session)
    school = School(
        name="Trial School",
        address="B",
        plan=SchoolPlan.free,
        trial_ends_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(school)
    db_session.commit()

    r = api_client.post(
        f"/admin/schools/{school.id}/actions/extend-trial",
        headers=ctx["headers"],
        json={"days": 14},
    )
    assert r.status_code == 200
    db_session.refresh(school)
    assert school.trial_ends_at > datetime.utcnow() + timedelta(days=10)

    until = (datetime.utcnow() + timedelta(days=365)).isoformat()
    r2 = api_client.post(
        f"/admin/schools/{school.id}/actions/activate-pro",
        headers=ctx["headers"],
        json={"until": until, "amount_kzt": 50000, "period_label": "year"},
    )
    assert r2.status_code == 200
    db_session.refresh(school)
    assert school.plan == SchoolPlan.pro
    assert school.subscription_ends_at is not None


def test_list_schools_enriched(api_client: TestClient, db_session: Session):
    ctx = _admin_ctx(api_client, db_session)
    school = School(
        name="List School",
        address="C",
        readiness_status="green",
    )
    db_session.add(school)
    db_session.flush()
    db_session.add(
        SchoolEvent(school_id=school.id, event_type="test.event", payload={})
    )
    db_session.commit()

    r = api_client.get("/admin/schools", headers=ctx["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    item = next(i for i in data["items"] if i["id"] == school.id)
    assert item["readiness_status"] == "green"
    assert item["last_event_at"] is not None
    assert "pro_access" in item
