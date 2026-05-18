from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.entities import ClassSubjectHours, ScheduleItem, StudentClass
from app.schemas.entities import ScheduleItemIn
from app.services.schedule_cp_sat import solve_missing_placements_whole_school
from app.services.schedule_quality import score_validation_issues
from app.services.schedule_solver import (
    compute_reoptimize_schedule_updates,
    generate_draft_for_class,
    optimize_proposals_ga_fallback,
    optimize_proposals_local_search,
)
from app.services.validation_engine import validate_schedule


@dataclass
class SolverJobRecord:
    job_id: str
    school_id: int
    class_id: int | None
    strategy: str
    frozen_lesson_slot_ids: set[int]
    max_runtime_seconds: int
    deterministic_seed: int
    regenerate_mode: str = "fill_gaps"
    status: str = "queued"
    progress: float = 0.0
    error: str | None = None
    operations: list[dict] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    unplaced_details: list[dict] = field(default_factory=list)
    quality: dict | None = None
    cancel_requested: bool = False
    apply_as_draft: bool = True


_JOBS: dict[str, SolverJobRecord] = {}
_LOCK = threading.Lock()


def _cp_sat_available() -> bool:
    try:
        from ortools.sat.python import cp_model  # noqa: F401

        return True
    except Exception:
        return False


def create_solver_job(
    db: Session,
    *,
    school_id: int,
    class_id: int | None,
    strategy: str,
    frozen_lesson_slot_ids: list[int],
    max_runtime_seconds: int,
    deterministic_seed: int,
    regenerate_mode: str = "fill_gaps",
    apply_as_draft: bool = True,
) -> SolverJobRecord:
    job = SolverJobRecord(
        job_id=str(uuid.uuid4()),
        school_id=school_id,
        class_id=class_id,
        strategy=strategy,
        frozen_lesson_slot_ids=set(frozen_lesson_slot_ids),
        max_runtime_seconds=max_runtime_seconds,
        deterministic_seed=deterministic_seed,
        regenerate_mode=regenerate_mode,
        apply_as_draft=apply_as_draft,
    )
    with _LOCK:
        _JOBS[job.job_id] = job
    worker = threading.Thread(target=_run_solver_job, args=(job.job_id,), daemon=True)
    worker.start()
    return job


def get_solver_job(job_id: str) -> SolverJobRecord | None:
    with _LOCK:
        return _JOBS.get(job_id)


def cancel_solver_job(job_id: str) -> SolverJobRecord | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job:
            job.cancel_requested = True
        return job


def _set_progress(job_id: str, *, status: str | None = None, progress: float | None = None, error: str | None = None):
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if error is not None:
            job.error = error


def _run_solver_job(job_id: str):
    from app.core.db import SessionLocal

    db: Session = SessionLocal()
    start = time.monotonic()
    try:
        job = get_solver_job(job_id)
        if not job:
            return
        _set_progress(job_id, status="running", progress=0.05)

        classes = []
        if job.class_id is not None:
            row = db.get(StudentClass, job.class_id)
            if row and row.school_id == job.school_id:
                classes = [row]
        else:
            classes = list(db.scalars(select(StudentClass).where(StudentClass.school_id == job.school_id)))
        if not classes:
            _set_progress(job_id, status="failed", error="NO_CLASSES_FOR_SOLVER")
            return

        operations: list[dict] = []
        all_issues: list[str] = []
        unplaced_details: list[dict] = []
        pending: list[ScheduleItemIn] = []
        engine_tag = job.strategy

        if job.class_id is None:
            for student_class in classes:
                plan_count = int(
                    db.scalar(
                        select(func.count())
                        .select_from(ClassSubjectHours)
                        .where(
                            ClassSubjectHours.school_id == job.school_id,
                            ClassSubjectHours.class_id == student_class.id,
                        )
                    )
                    or 0
                )
                if plan_count == 0:
                    all_issues.append("NO_CURRICULUM_FOR_CLASS")

        def _append_proposals(proposals: list[ScheduleItemIn], current: SolverJobRecord) -> None:
            for proposal in proposals:
                if proposal.lesson_slot_id in current.frozen_lesson_slot_ids:
                    all_issues.append("FROZEN_SLOT_SKIPPED")
                    continue
                operations.append({"type": "create", "payload": proposal})
                pending.append(proposal)

        if job.regenerate_mode == "from_plan":
            del_stmt = delete(ScheduleItem).where(ScheduleItem.school_id == job.school_id)
            if job.class_id is not None:
                del_stmt = del_stmt.where(ScheduleItem.class_id == job.class_id)
            db.execute(del_stmt)
            db.commit()

        if job.strategy == "reoptimize":
            current = get_solver_job(job_id)
            if current is None:
                return
            if current.cancel_requested:
                _set_progress(job_id, status="cancelled", progress=current.progress)
                return
            class_ids_scope = [c.id for c in classes] if job.class_id is not None else None
            upd_ops, notes = compute_reoptimize_schedule_updates(
                db,
                current.school_id,
                class_ids_scope=class_ids_scope,
                frozen_lesson_slot_ids=current.frozen_lesson_slot_ids,
                max_passes=min(48, max(4, current.max_runtime_seconds)),
                seed=current.deterministic_seed,
            )
            operations.extend(upd_ops)
            all_issues.extend(notes)
            engine_tag = "reoptimize"
            _set_progress(job_id, progress=0.95)
        elif job.strategy == "cp_sat" and _cp_sat_available():
            current = get_solver_job(job_id)
            if current is None:
                return
            if current.cancel_requested:
                _set_progress(job_id, status="cancelled", progress=current.progress)
                return
            if time.monotonic() - start > current.max_runtime_seconds:
                _set_progress(job_id, status="failed", error="SOLVER_TIMEOUT")
                return

            class_ids = [c.id for c in classes]
            budget = max(1, int(current.max_runtime_seconds - (time.monotonic() - start)))
            proposals, unplaced = solve_missing_placements_whole_school(
                db,
                school_id=current.school_id,
                class_ids=class_ids,
                frozen_lesson_slot_ids=current.frozen_lesson_slot_ids,
                max_runtime_seconds=budget,
            )
            for row in unplaced:
                all_issues.extend(row.get("blocking_issues", []))
                unplaced_details.append(row)
            _append_proposals(proposals, current)
            _set_progress(job_id, progress=0.95)
            if not proposals:
                engine_tag = "cp_sat_fallback"
                total = max(1, len(classes))
                for idx, student_class in enumerate(classes):
                    current = get_solver_job(job_id)
                    if current is None:
                        return
                    if current.cancel_requested:
                        _set_progress(job_id, status="cancelled", progress=current.progress)
                        return
                    if time.monotonic() - start > current.max_runtime_seconds:
                        _set_progress(job_id, status="failed", error="SOLVER_TIMEOUT")
                        return
                    fb_proposals, fb_unplaced = generate_draft_for_class(
                        db, current.school_id, student_class.id
                    )
                    for row in fb_unplaced:
                        all_issues.extend(row.get("blocking_issues", []))
                        unplaced_details.append(row)
                    _append_proposals(fb_proposals, current)
                    _set_progress(job_id, progress=min(0.95, (idx + 1) / total))
        else:
            if job.strategy == "cp_sat":
                engine_tag = "cp_sat_fallback"
            total = max(1, len(classes))
            for idx, student_class in enumerate(classes):
                current = get_solver_job(job_id)
                if current is None:
                    return
                if current.cancel_requested:
                    _set_progress(job_id, status="cancelled", progress=current.progress)
                    return
                if time.monotonic() - start > current.max_runtime_seconds:
                    _set_progress(job_id, status="failed", error="SOLVER_TIMEOUT")
                    return

                proposals, unplaced = generate_draft_for_class(db, current.school_id, student_class.id)
                if current.strategy == "local_search":
                    proposals = optimize_proposals_local_search(
                        db,
                        current.school_id,
                        proposals,
                        iterations=30,
                        seed=current.deterministic_seed + idx,
                    )
                elif current.strategy == "ga_fallback" and proposals:
                    proposals = optimize_proposals_ga_fallback(
                        db,
                        current.school_id,
                        proposals,
                        generations=16,
                        population_size=6,
                        mutation_rate=0.3,
                        seed=current.deterministic_seed + idx,
                    )
                for row in unplaced:
                    all_issues.extend(row.get("blocking_issues", []))
                    unplaced_details.append(row)
                _append_proposals(proposals, current)
                _set_progress(job_id, progress=min(0.95, (idx + 1) / total))

        if not operations and not all_issues:
            for student_class in classes:
                plan_count = int(
                    db.scalar(
                        select(func.count())
                        .select_from(ClassSubjectHours)
                        .where(
                            ClassSubjectHours.school_id == job.school_id,
                            ClassSubjectHours.class_id == student_class.id,
                        )
                    )
                    or 0
                )
                all_issues.append(
                    "NO_CURRICULUM_FOR_CLASS" if plan_count == 0 else "SOLVER_NO_MISSING_HOURS"
                )

        # Re-score: created lessons as incremental candidates; updates as replacement_batch.
        issues: list = []
        seen: set[str] = set()
        update_ops = [op for op in operations if op["type"] == "update"]
        if update_ops:
            batch_pairs: list[tuple[int, ScheduleItemIn]] = []
            for op in update_ops:
                raw = op["payload"]
                pl = raw if isinstance(raw, ScheduleItemIn) else ScheduleItemIn(**raw)
                batch_pairs.append((op["id"], pl))
            for issue in validate_schedule(
                db,
                job.school_id,
                None,
                check_curriculum_totals=True,
                replacement_batch=batch_pairs,
            ):
                key = f"{issue.issue_code}|{issue.severity}|{issue.slot_ref}|{issue.entity_refs}"
                if key in seen:
                    continue
                seen.add(key)
                issues.append(issue)
        for candidate in pending:
            for issue in validate_schedule(db, job.school_id, candidate, check_curriculum_totals=True):
                key = f"{issue.issue_code}|{issue.severity}|{issue.slot_ref}|{issue.entity_refs}"
                if key in seen:
                    continue
                seen.add(key)
                issues.append(issue)
        quality = score_validation_issues(issues)

        with _LOCK:
            done = _JOBS.get(job_id)
            if not done:
                return
            done.operations = operations
            done.issues = sorted(set(all_issues))
            done.unplaced_details = unplaced_details
            done.quality = quality
            done.status = "completed"
            done.progress = 1.0
            done.strategy = engine_tag
    except Exception as exc:  # pragma: no cover - defensive
        _set_progress(job_id, status="failed", error=f"SOLVER_JOB_ERROR: {exc}")
    finally:
        db.close()
