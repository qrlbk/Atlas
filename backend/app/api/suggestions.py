from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_scope, get_current_user, require_roles
from app.core.db import get_db
from app.models.entities import StudentClass, User, UserRole
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
from app.services.school_integrity import assert_schedule_payload_consistent
from app.services.schedule_solver import draft_teacher_absence, generate_draft_for_class, suggest_slot_combinations

router = APIRouter(prefix="/suggestions", tags=["suggestions"])
# Draft suggestions do not mutate the database; viewers may use them like /validation.
suggestions_user = require_roles(UserRole.admin, UserRole.school_manager, UserRole.viewer)


@router.post("/slots", response_model=list[SlotSuggestionOut])
def suggest_slots(
    payload: SuggestSlotsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(suggestions_user),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
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
    student_class = db.get(StudentClass, payload.class_id)
    if student_class is None or student_class.school_id != payload.school_id:
        raise HTTPException(status_code=400, detail={"key": "errors.classNotFoundInSchool"})
    proposals, unplaced_raw = generate_draft_for_class(db, payload.school_id, payload.class_id)
    unplaced = [UnplacedSubjectOut(**row) for row in unplaced_raw]
    return GenerateClassResponse(proposals=proposals, unplaced=unplaced)


@router.post("/scenario-draft", response_model=ScenarioDraftResponse)
def scenario_draft(
    payload: ScenarioDraftRequest,
    db: Session = Depends(get_db),
    _: User = Depends(suggestions_user),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    if payload.scenario != "teacher_absent":
        raise HTTPException(status_code=400, detail={"key": "errors.requestValidation"})
    operations, issues = draft_teacher_absence(
        db,
        payload.school_id,
        payload.teacher_id,
        day_of_week=payload.day_of_week,
        substitute_teacher_id=payload.substitute_teacher_id,
    )
    serialized = [
        ScheduleDraftOperationOut(
            type=op["type"],
            id=op.get("id"),
            payload=op.get("payload"),
        )
        for op in operations
    ]
    return ScenarioDraftResponse(operations=serialized, issues=issues)
