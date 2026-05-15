from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import enforce_school_scope, get_current_user, require_roles
from app.core.db import get_db
from app.models.entities import User, UserRole
from app.schemas.solver_jobs import (
    SolverJobCreateRequest,
    SolverJobCreateResponse,
    SolverJobStatusResponse,
)
from app.schemas.suggestions import ScheduleDraftOperationOut, UnplacedSubjectOut
from app.services.solver_jobs import cancel_solver_job, create_solver_job, get_solver_job

router = APIRouter(prefix="/solver-jobs", tags=["solver-jobs"])
solver_user = require_roles(UserRole.admin, UserRole.school_manager, UserRole.viewer)


@router.post("", response_model=SolverJobCreateResponse)
def create_job(
    payload: SolverJobCreateRequest,
    db=Depends(get_db),
    _: User = Depends(solver_user),
    current_user: User = Depends(get_current_user),
):
    enforce_school_scope(current_user, payload.school_id)
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
    _: User = Depends(solver_user),
    current_user: User = Depends(get_current_user),
):
    job = get_solver_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    enforce_school_scope(current_user, job.school_id)
    operations = [
        ScheduleDraftOperationOut(type=op["type"], id=op.get("id"), payload=op.get("payload"))
        for op in job.operations
    ]
    unplaced = [UnplacedSubjectOut(**row) for row in job.unplaced_details]
    return SolverJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        strategy=job.strategy,
        progress=job.progress,
        error=job.error,
        operations=operations,
        issues=job.issues,
        unplaced_details=unplaced,
        quality=job.quality,
    )


@router.post("/{job_id}/cancel", response_model=SolverJobStatusResponse)
def cancel_job(
    job_id: str,
    _: User = Depends(solver_user),
    current_user: User = Depends(get_current_user),
):
    job = cancel_solver_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})
    enforce_school_scope(current_user, job.school_id)
    operations = [
        ScheduleDraftOperationOut(type=op["type"], id=op.get("id"), payload=op.get("payload"))
        for op in job.operations
    ]
    unplaced = [UnplacedSubjectOut(**row) for row in job.unplaced_details]
    return SolverJobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        strategy=job.strategy,
        progress=job.progress,
        error=job.error,
        operations=operations,
        issues=job.issues,
        unplaced_details=unplaced,
        quality=job.quality,
    )
