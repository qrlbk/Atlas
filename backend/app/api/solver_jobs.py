from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import enforce_school_scope, get_current_user, require_roles
from app.core.db import get_db
from app.i18n import resolve_locale
from app.models.entities import School, User, UserRole
from app.schemas.readiness import HumanDiagnosticOut
from app.schemas.solver_jobs import (
    SolverJobCreateRequest,
    SolverJobCreateResponse,
    SolverJobStatusResponse,
)
from app.schemas.suggestions import ScheduleDraftOperationOut, UnplacedSubjectOut
from app.services.entitlements import increment_usage, require_capability
from app.services.human_diagnostics import diagnostics_from_unplaced
from app.services.school_events import log_school_event
from app.services.solver_jobs import cancel_solver_job, create_solver_job, get_solver_job

router = APIRouter(prefix="/solver-jobs", tags=["solver-jobs"])
solver_user = require_roles(UserRole.admin, UserRole.school_manager, UserRole.viewer)


def _job_response(job, locale: str) -> SolverJobStatusResponse:
    operations = [
        ScheduleDraftOperationOut(type=op["type"], id=op.get("id"), payload=op.get("payload"))
        for op in job.operations
    ]
    unplaced = [UnplacedSubjectOut(**row) for row in job.unplaced_details]
    diag_rows = diagnostics_from_unplaced(job.unplaced_details, locale, limit=10)
    diagnostics = [HumanDiagnosticOut(**row) for row in diag_rows]
    return SolverJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        strategy=job.strategy,
        progress=job.progress,
        error=job.error,
        operations=operations,
        issues=job.issues,
        unplaced_details=unplaced,
        diagnostics=diagnostics,
        quality=job.quality,
    )


@router.post("", response_model=SolverJobCreateResponse)
def create_job(
    payload: SolverJobCreateRequest,
    db=Depends(get_db),
    _: User = Depends(solver_user),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
    school = db.get(School, payload.school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    require_capability(db, school, "solver")
    increment_usage(db, payload.school_id, "solver_job")
    log_school_event(
        db,
        school_id=payload.school_id,
        user_id=current_user.id,
        event_type="solver.started",
        payload={"strategy": payload.strategy},
        commit=False,
    )
    db.commit()
    job = create_solver_job(
        db,
        school_id=payload.school_id,
        class_id=payload.class_id,
        strategy=payload.strategy,
        frozen_lesson_slot_ids=payload.frozen_lesson_slot_ids,
        max_runtime_seconds=payload.max_runtime_seconds,
        deterministic_seed=payload.deterministic_seed,
        regenerate_mode=payload.regenerate_mode,
        apply_as_draft=payload.apply_as_draft,
    )
    return SolverJobCreateResponse(job_id=job.job_id, status=job.status)


@router.get("/{job_id}", response_model=SolverJobStatusResponse)
def get_job_status(
    job_id: str,
    request: Request,
    _: User = Depends(solver_user),
    current_user: User = Depends(get_current_user),
):
    job = get_solver_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    enforce_school_scope(current_user, job.school_id)
    locale = resolve_locale(request)
    return _job_response(job, locale)


@router.post("/{job_id}/cancel", response_model=SolverJobStatusResponse)
def cancel_job(
    job_id: str,
    request: Request,
    _: User = Depends(solver_user),
    current_user: User = Depends(get_current_user),
):
    job = cancel_solver_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    enforce_school_scope(current_user, job.school_id)
    locale = resolve_locale(request)
    return _job_response(job, locale)
