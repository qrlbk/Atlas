from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_scope, get_current_user, require_roles
from app.core.db import get_db
from app.i18n import resolve_locale
from app.models.entities import School, StudentClass, User, UserRole
from app.schemas.suggestions import (
    GenerateClassRequest,
    GenerateClassResponse,
    ScenarioDraftRequest,
    ScenarioDraftResponse,
    ScheduleDraftOperationOut,
    SlotSuggestionOut,
    SuggestSlotsRequest,
    UnplacedSubjectOut,
)
from app.services.entitlements import check_slot_suggestion_allowed, increment_usage, require_capability
from app.services.human_diagnostics import diagnostics_from_unplaced
from app.services.scenario_engine import ScenarioConfig, apply_scenario
from app.services.school_integrity import assert_schedule_payload_consistent
from app.services.schedule_solver import generate_draft_for_class, suggest_slot_combinations

router = APIRouter(prefix="/suggestions", tags=["suggestions"])
suggestions_user = require_roles(UserRole.admin, UserRole.school_manager, UserRole.viewer)


@router.post("/slots", response_model=list[SlotSuggestionOut])
def suggest_slots(
    payload: SuggestSlotsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(suggestions_user),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    school = db.get(School, payload.school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    check_slot_suggestion_allowed(db, school)
    increment_usage(db, payload.school_id, "slot_suggestion")
    db.commit()
    assert_schedule_payload_consistent(db, payload.candidate)
    options = suggest_slot_combinations(db, payload.school_id, payload.candidate, top_n=payload.top_n)
    return [SlotSuggestionOut(**row) for row in options]


@router.post("/generate-class", response_model=GenerateClassResponse)
def generate_class_draft(
    payload: GenerateClassRequest,
    db: Session = Depends(get_db),
    _: User = Depends(suggestions_user),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    school = db.get(School, payload.school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    require_capability(db, school, "generate_class")
    student_class = db.get(StudentClass, payload.class_id)
    if student_class is None or student_class.school_id != payload.school_id:
        raise HTTPException(status_code=400, detail={"key": "errors.classNotFoundInSchool"})
    proposals, unplaced_raw = generate_draft_for_class(db, payload.school_id, payload.class_id)
    unplaced = [UnplacedSubjectOut(**row) for row in unplaced_raw]
    return GenerateClassResponse(proposals=proposals, unplaced=unplaced)


@router.post("/scenario-draft", response_model=ScenarioDraftResponse)
def scenario_draft(
    payload: ScenarioDraftRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(suggestions_user),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    school = db.get(School, payload.school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    require_capability(db, school, "scenario")
    allowed = {
        "teacher_absent",
        "substitute_teacher",
        "shortened_day",
        "room_unavailable",
        "emergency_free",
    }
    if payload.scenario not in allowed:
        raise HTTPException(status_code=400, detail={"key": "errors.requestValidation"})
    config = ScenarioConfig(
        scenario=payload.scenario,
        day_of_week=payload.day_of_week,
        teacher_id=payload.teacher_id,
        substitute_teacher_id=payload.substitute_teacher_id,
        original_teacher_id=payload.original_teacher_id,
        max_lesson_number=payload.max_lesson_number,
        classroom_id=payload.classroom_id,
        class_id=payload.class_id,
        lesson_slot_id=payload.lesson_slot_id,
    )
    operations, issues = apply_scenario(db, payload.school_id, config)
    serialized = [
        ScheduleDraftOperationOut(
            type=op["type"],
            id=op.get("id"),
            payload=op.get("payload"),
        )
        for op in operations
    ]
    return ScenarioDraftResponse(operations=serialized, issues=issues)
