"""Lightweight checks that new API routes are registered (no DB)."""


def test_suggestion_and_curriculum_routes_exist():
    from app.main import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/suggestions/slots" in paths
    assert "/suggestions/generate-class" in paths
    assert "/class-subject-hours" in paths
    assert "/schedule-plan-status" in paths


def test_import_routes_exist():
    from app.main import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/imports/template" in paths
    assert "/imports/validate" in paths
    assert "/imports/commit" in paths
