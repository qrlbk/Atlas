"""Pydantic schemas for the Excel data import flow.

The Excel workbook is the source of truth for users: one sheet per entity,
human-readable columns and natural keys (no DB ids). The validate endpoint
returns a structured report; commit applies the workbook honoring per-sheet
modes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SHEET_TEACHERS = "Teachers"
SHEET_CLASSROOMS = "Classrooms"
SHEET_CLASSES = "Classes"
SHEET_SUBJECTS = "Subjects"
SHEET_LESSON_SLOTS = "LessonSlots"
SHEET_GROUP_FLOWS = "GroupFlows"
SHEET_CURRICULUM = "Curriculum"
SHEET_SCHEDULE = "Schedule"


ALL_SHEETS: tuple[str, ...] = (
    SHEET_SUBJECTS,
    SHEET_LESSON_SLOTS,
    SHEET_CLASSES,
    SHEET_TEACHERS,
    SHEET_CLASSROOMS,
    SHEET_GROUP_FLOWS,
    SHEET_CURRICULUM,
    SHEET_SCHEDULE,
)


class ImportMode(str, Enum):
    """How a single sheet is applied during commit."""

    upsert = "upsert"
    replace = "replace"
    append = "append"
    skip = "skip"


class IssueSeverity(str, Enum):
    error = "error"
    warning = "warning"


class ImportIssue(BaseModel):
    """A single problem detected during validate/commit."""

    sheet: str
    row: int | None = None
    column: str | None = None
    severity: IssueSeverity
    code: str
    message: str

    model_config = ConfigDict(use_enum_values=True)


class SheetStats(BaseModel):
    sheet: str
    rows_total: int = 0
    rows_to_create: int = 0
    rows_to_update: int = 0
    rows_to_replace: int = 0
    rows_to_skip: int = 0
    rows_with_errors: int = 0
    default_mode: ImportMode = ImportMode.upsert
    allowed_modes: list[ImportMode] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


class ImportSummary(BaseModel):
    school_id: int
    error_count: int = 0
    warning_count: int = 0
    sheets: list[SheetStats] = Field(default_factory=list)
    entity_preview: dict[str, int] = Field(default_factory=dict)
    issue_buckets: dict[str, int] = Field(default_factory=dict)


class ValidateResponse(BaseModel):
    school_id: int
    summary: ImportSummary
    issues: list[ImportIssue] = Field(default_factory=list)
    can_commit: bool


class CommitSheetResult(BaseModel):
    sheet: str
    mode: ImportMode
    created: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0

    model_config = ConfigDict(use_enum_values=True)


class CommitResponse(BaseModel):
    school_id: int
    applied: list[CommitSheetResult] = Field(default_factory=list)
    issues: list[ImportIssue] = Field(default_factory=list)
    committed: bool


def default_modes() -> dict[str, ImportMode]:
    """Default per-sheet apply mode: upsert for catalogs, replace for schedule."""

    return {
        SHEET_SUBJECTS: ImportMode.upsert,
        SHEET_LESSON_SLOTS: ImportMode.upsert,
        SHEET_CLASSES: ImportMode.upsert,
        SHEET_TEACHERS: ImportMode.upsert,
        SHEET_CLASSROOMS: ImportMode.upsert,
        SHEET_GROUP_FLOWS: ImportMode.upsert,
        SHEET_CURRICULUM: ImportMode.upsert,
        SHEET_SCHEDULE: ImportMode.replace,
    }


def allowed_modes_for(sheet: str) -> list[ImportMode]:
    """Catalog sheets do not support 'replace' (would wipe other schools too)."""

    if sheet == SHEET_SCHEDULE:
        return [ImportMode.upsert, ImportMode.replace, ImportMode.append, ImportMode.skip]
    if sheet == SHEET_CURRICULUM:
        return [ImportMode.upsert, ImportMode.replace, ImportMode.append, ImportMode.skip]
    return [ImportMode.upsert, ImportMode.append, ImportMode.skip]


__all__ = [
    "ALL_SHEETS",
    "CommitResponse",
    "CommitSheetResult",
    "ImportIssue",
    "ImportMode",
    "ImportSummary",
    "IssueSeverity",
    "SheetStats",
    "ValidateResponse",
    "allowed_modes_for",
    "default_modes",
    "SHEET_CLASSES",
    "SHEET_CLASSROOMS",
    "SHEET_CURRICULUM",
    "SHEET_GROUP_FLOWS",
    "SHEET_LESSON_SLOTS",
    "SHEET_SCHEDULE",
    "SHEET_SUBJECTS",
    "SHEET_TEACHERS",
]


# Re-export for type checkers that don't expand __all__
_ = Any
