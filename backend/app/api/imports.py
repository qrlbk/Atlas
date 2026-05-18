"""Excel data import endpoints: template, validate (dry-run), commit (apply)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_scope, require_roles
from app.core.db import get_db
from app.models.entities import School, User, UserRole
from app.schemas.imports import (
    ALL_SHEETS,
    SHEET_SCHEDULE,
    CommitResponse,
    ImportIssue,
    ImportMode,
    ImportSummary,
    IssueSeverity,
    SheetStats,
    ValidateResponse,
    allowed_modes_for,
    default_modes,
)
from app.services.entitlements import (
    import_issue_buckets,
    require_capability,
    set_onboarding_completed,
)
from app.services.excel_import import (
    apply_plan,
    build_plan,
    build_template_workbook,
    issue_counts,
    load_workbook_from_bytes,
    plan_to_summary,
)
from app.services.schedule_snapshots import create_schedule_snapshot
from app.services.school_events import log_school_event
from app.services.school_readiness import invalidate_readiness_cache


router = APIRouter(prefix="/imports")
manager_or_admin = require_roles(UserRole.admin, UserRole.school_manager)


XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _parse_modes(raw: str | None) -> dict[str, ImportMode]:
    if not raw:
        return default_modes()
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail={"key": "errors.importInvalidModes"}) from exc
    if not isinstance(loaded, dict):
        raise HTTPException(status_code=400, detail={"key": "errors.importInvalidModes"})
    modes = default_modes()
    for sheet_name, value in loaded.items():
        if sheet_name not in ALL_SHEETS:
            continue
        try:
            mode = ImportMode(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"key": "errors.importInvalidModes"}) from exc
        if mode not in allowed_modes_for(sheet_name):
            raise HTTPException(status_code=400, detail={"key": "errors.importInvalidModes"})
        modes[sheet_name] = mode
    return modes


def _read_upload(file: UploadFile) -> bytes:
    try:
        data = file.file.read()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail={"key": "errors.importReadFailed"}) from exc
    if not data:
        raise HTTPException(status_code=400, detail={"key": "errors.importEmptyFile"})
    return data


def _entity_preview(summary_sheets: list[SheetStats]) -> dict[str, int]:
    preview: dict[str, int] = {}
    for sheet in summary_sheets:
        key = sheet.sheet.lower()
        preview[key] = sheet.rows_to_create + sheet.rows_to_update + sheet.rows_to_replace
    curriculum_hours = 0
    for sheet in summary_sheets:
        if sheet.sheet == "Curriculum":
            curriculum_hours = sheet.rows_to_create + sheet.rows_to_update
    if curriculum_hours:
        preview["curriculum_hours"] = curriculum_hours
    return preview


def _commit_needs_snapshot(modes: dict[str, ImportMode], plan) -> bool:
    risky = {SHEET_SCHEDULE, "Curriculum", "Teachers", "Classes"}
    for sheet_name, mode in modes.items():
        if sheet_name in risky and mode in (ImportMode.replace, ImportMode.upsert):
            sheet_plan = plan.sheets.get(sheet_name)
            if sheet_plan and sheet_plan.operations:
                return True
    return False


@router.get("/template")
def download_template(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_admin),
):
    enforce_school_scope(current_user, school_id)
    _ = school_id
    payload = build_template_workbook()
    return Response(
        content=payload,
        media_type=XLSX_CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="atlas_import_template_school_{school_id}.xlsx"'},
    )


@router.post("/validate", response_model=ValidateResponse)
def validate_workbook(
    school_id: int = Form(...),
    file: UploadFile = File(...),
    modes: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_admin),
) -> ValidateResponse:
    """Dry-run: parses the workbook, builds an import plan, returns issues + summary."""

    enforce_school_scope(current_user, school_id)
    data = _read_upload(file)
    try:
        workbook = load_workbook_from_bytes(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"key": "errors.importInvalidWorkbook"}) from exc

    sheet_modes = _parse_modes(modes)
    plan = build_plan(db, workbook, school_id)
    summary_sheets: list[SheetStats] = plan_to_summary(plan, sheet_modes)
    error_count, warning_count = issue_counts(plan.issues)
    buckets = import_issue_buckets(plan.issues)
    summary = ImportSummary(
        school_id=school_id,
        error_count=error_count,
        warning_count=warning_count,
        sheets=summary_sheets,
        entity_preview=_entity_preview(summary_sheets),
        issue_buckets=buckets,
    )
    log_school_event(
        db,
        school_id=school_id,
        user_id=current_user.id,
        event_type="import.validated",
        payload={"error_count": error_count, "warning_count": warning_count},
        commit=False,
    )
    db.commit()
    return ValidateResponse(
        school_id=school_id,
        summary=summary,
        issues=plan.issues,
        can_commit=error_count == 0,
    )


@router.post("/commit", response_model=CommitResponse)
def commit_workbook(
    school_id: int = Form(...),
    file: UploadFile = File(...),
    modes: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_admin),
) -> CommitResponse:
    """Apply the import plan inside a transaction; rollback on any error."""

    enforce_school_scope(current_user, school_id)
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail={"key": "errors.requestValidation"})

    data = _read_upload(file)
    try:
        workbook = load_workbook_from_bytes(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"key": "errors.importInvalidWorkbook"}) from exc

    sheet_modes = _parse_modes(modes)
    if sheet_modes.get(SHEET_SCHEDULE) != ImportMode.skip:
        require_capability(db, school, "import_schedule")

    plan = build_plan(db, workbook, school_id)
    error_count, _warning_count = issue_counts(plan.issues)
    if error_count > 0:
        return CommitResponse(
            school_id=school_id,
            applied=[],
            issues=plan.issues,
            committed=False,
        )

    if _commit_needs_snapshot(sheet_modes, plan):
        create_schedule_snapshot(
            db,
            school_id=school_id,
            reason="pre_import",
            label="Before Excel import",
            user_id=current_user.id,
            commit=False,
        )

    try:
        applied = apply_plan(db, plan, sheet_modes)
        set_onboarding_completed(db, school)
        log_school_event(
            db,
            school_id=school_id,
            user_id=current_user.id,
            event_type="import.committed",
            payload={"sheets": [a.sheet for a in applied]},
            commit=False,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail={"key": "errors.importCommitFailed"}) from exc

    invalidate_readiness_cache(school_id)
    return CommitResponse(
        school_id=school_id,
        applied=applied,
        issues=plan.issues,
        committed=True,
    )


__all__ = ["router"]

_ = Any
