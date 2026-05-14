"""
Full Docker E2E remains optional; use `frontend` Playwright against a running stack.

Unit coverage for scheduling logic lives in `test_validation_engine.py`, `test_solver.py`, etc.
"""

import pytest


@pytest.mark.skip(reason="Requires running API + DB stack (see README E2E Playwright)")
def test_mvp_smoke_flow():
    """
    E2E smoke flow:
    1. Login as school manager.
    2. Create teacher/classroom/class/group flow.
    3. Create schedule item and call /validation.
    4. Verify conflicts are returned before save.
    """
    assert True
