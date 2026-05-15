from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models.entities import GroupFlow, School, StudentClass
from app.scripts.seed import DEMO_CLASSES, DEMO_SCHOOL_NAME, run_seed
from app.services.schedule_cp_sat import missing_hours_count
from app.services.validation_engine import validate_schedule


def test_demo_seed_has_no_error_level_validation_issues(db_session, monkeypatch):
    session_factory = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
    )
    monkeypatch.setattr("app.scripts.seed.SessionLocal", session_factory)

    run_seed()

    school = db_session.scalar(select(School).where(School.name == DEMO_SCHOOL_NAME))
    assert school is not None

    issues = validate_schedule(db_session, school.id, None, check_curriculum_totals=True)
    errors = [issue for issue in issues if issue.severity == "error"]
    assert errors == []

    class_ids = list(
        db_session.scalars(
            select(StudentClass.id).where(StudentClass.school_id == school.id)
        )
    )
    assert missing_hours_count(db_session, school_id=school.id, class_ids=class_ids) > 0

    class_names = list(
        db_session.scalars(
            select(StudentClass.class_name).where(StudentClass.school_id == school.id)
        )
    )
    assert sorted(class_names) == sorted(name for name, _ in DEMO_CLASSES)

    flows = list(
        db_session.scalars(select(GroupFlow).where(GroupFlow.school_id == school.id))
    )
    assert len(flows) == 3


def test_sparse_demo_profile_has_more_missing_hours(db_session, monkeypatch):
    monkeypatch.setenv("ATLAS_DEMO_GENERATION_PROFILE", "sparse")
    session_factory = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
    )
    monkeypatch.setattr("app.scripts.seed.SessionLocal", session_factory)

    run_seed()

    school = db_session.scalar(select(School).where(School.name == DEMO_SCHOOL_NAME))
    assert school is not None
    class_ids = list(
        db_session.scalars(select(StudentClass.id).where(StudentClass.school_id == school.id))
    )
    missing = missing_hours_count(db_session, school_id=school.id, class_ids=class_ids)
    assert missing >= 15
