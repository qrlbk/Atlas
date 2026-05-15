# Atlas MVP

Atlas is an MVP web platform for manual school schedule management with real-time validation.

## MVP scope

- Manual schedule building only (no auto-generation).
- Real-time validation for schedule conflicts and constraints.
- Visual schedule builder with drag-and-drop.
- Role-based access with JWT authentication.

## Out of scope (MVP)

- Fully automated long-horizon optimization (multi-week objectives, advanced LNS, fairness tuning beyond hard constraints)
- Telegram bot
- ERP/accounting/payroll
- Mobile app
- Government platform integrations

## Post-MVP scheduling features (current codebase)

- **Curriculum plan**: `class_subject_hours` — weekly hours per class and subject. CRUD: `/class-subject-hours` (see API). School managers edit the plan in the UI at **`/curriculum`**. Seeded to match the demo schedule.
- **Stricter validation**: `CLASS_DOUBLE_BOOKING`, `TEACHER_SUBJECT_MISMATCH`, and plan checks `PLAN_UNDERFILLED` / `PLAN_OVERFLOW`. Grouped flow rows that share teacher/room in one slot are allowed (joint booking).
- **Constraint weights**: each `ValidationIssue` includes a `weight`; schools may override via `schools.scheduling_preferences.issue_weights` (JSON). Dashboard includes a **Scheduling preferences** JSON editor (`PATCH /schools/{id}`).
- **Quality score**: `POST /validation` returns `quality` (total penalty and breakdown).
- **Suggestions**: `POST /suggestions/slots` (rank slot + room for a candidate lesson), `POST /suggestions/generate-class` (greedy draft for one class from curriculum). The schedule builder has **Pick slot** and **By plan (draft)** when the grid matches the server (save local edits first).
- **Plan coverage (read-only)**: `GET /schedule-plan-status?school_id=…` aggregates planned vs scheduled hours. Used by the dashboard and curriculum screen.
- **Async solver jobs**: `POST /solver-jobs` + `GET /solver-jobs/{id}`.
  - **Scope**: `class_id` omitted = whole school; UI toggle **Selected class** | **Whole school**.
  - **`regenerate_mode`**: `fill_gaps` (default) adds missing plan hours only; `from_plan` clears schedule in scope then rebuilds.
  - **`strategy`**: `cp_sat` (whole-school CP-SAT when OR-Tools is installed), `ga_fallback`, `reoptimize` (local-search `update` operations).
  - **`frozen_lesson_slot_ids`**: pinned slots are skipped; pin from the lesson detail panel.
- **Demo seed profiles**: `ATLAS_DEMO_GENERATION_PROFILE=partial` (default, ~few gaps) or `sparse` (+2 planned hours per row, ~15+ missing for solver/E2E).
- **What-if sandbox**: named draft snapshots in browser `localStorage` from the schedule toolbar.

## School `scheduling_preferences` (JSON on `schools`)

Optional keys (unknown keys are ignored):

- **`plan_compliance`**: `"warn"` (default) or `"error"`. When `"error"`, curriculum mismatches `PLAN_UNDERFILLED` / `PLAN_OVERFLOW` are emitted with **error** severity (and affect validation status the same way as other errors). When omitted or `"warn"`, they stay warnings as before.
- **`issue_weights`**: per-code numeric weights for `score_validation_issues` (see constraint catalog).

Example:

```json
{
  "plan_compliance": "warn",
  "issue_weights": {
    "TEACHER_DOUBLE_BOOKING": 10
  }
}
```

## Timetable solver contract (current + next steps)

- **Input**: a consistent DB snapshot (or `school_id` inside a transaction), the set of mutable entities (e.g. schedule items to add/move), optional frozen slots or “do not touch” lessons, and school preferences (`scheduling_preferences`).
- **Current `cp_sat` scope**: fill missing `class_subject_hours` with hard constraints for class/teacher/room slot conflicts, teacher qualification, teacher unavailable days, room specialization/capacity, and grouped flow capacity. Output is `create` draft operations.
- **Current `ga_fallback` scope**: optional optimizer over already generated greedy proposals (does not create new units when the proposal list is empty).
- **Oracle**: `validate_schedule(db, school_id, candidate_item_or_none)` remains the source of truth for post-generation scoring and user-visible errors.
- **Output**: operations compatible with the existing draft application flow in the schedule UI.

## Class draft generator limitations (v1)

`generate_draft_for_class` in `backend/app/services/schedule_solver.py` is a **greedy helper**, not a global solver. Limitations (see also the module docstring there):

- Each placement step calls `validate_schedule(..., pending=proposals, check_curriculum_totals=False)` so earlier proposals in the same run participate in conflict checks (teacher/room/class double-booking), and aggregate plan rows do not block incremental placement.
- Curriculum rows are processed with **non-specialized subjects first** (standard rooms) so partial drafts still appear when lab capacity or specialization blocks chemistry/physics for a large class.
- **Teacher ↔ subject** uses shared matching with validation: case-insensitive names and aliases (`PE` ↔ `Physical Education`, `Math` ↔ `Mathematics`, `Chem`/`химия` ↔ `Chemistry`, `Phys`/`физика` ↔ `Physics`) so the generator and `TEACHER_SUBJECT_MISMATCH` stay consistent.
- Slot/room search is first-fit among combinations that pass the oracle, not cost-optimal across the whole week.
- When a curriculum row cannot be placed, the API includes **`blocking_issues`**: error codes from the **first** `(teacher, slot, room)` attempt in the same order as the greedy search (not a mix of many cells).

## Roles

- `Admin`: manages schools and appoints school managers.
- `School Manager`: manages timetable, teachers, classrooms, classes, grouped flows, analytics.
- `Viewer`: read-only access to schedules.

## Definition of done

- School manager can create all core entities and build schedules via UI.
- Critical conflicts are detected and displayed before save.
- Required REST endpoints are available and secured by role and school scope.
- App runs through Docker Compose.

## KPI targets

- Faster timetable composition for school managers.
- Fewer scheduling conflicts.
- Faster schedule changes and replacements.
- Actual operational usage by schools.

## Local run

1. Start stack:
   - `docker compose up --build`
2. Migrations and seed run automatically on backend container start (`docker-entrypoint.sh`).

   Default seeded accounts (override via env in `docker-compose.yml`):

   - Admin: `admin@atlas.example.com` / `AtlasSeed!2026`
   - Manager: `manager@atlas.example.com` / `AtlasSeed!2026`

   Also seeds demo school, subjects, and Mon–Fri lesson slots. On each backend start the seed **replaces** `schedule_items` and `class_subject_hours` for **Atlas Demo School** only so the sample grid matches `app/scripts/seed.py` (teachers, rooms, classes, and flows are updated in place when their specs change).
   Demo invariants:
   - No error-level issues on full-school validation (`validate_schedule(..., candidate=None)`).
   - Plan rows stay coherent with schedule (`scheduled <= planned` per class+subject).
   - A small number of plan rows stay intentionally underfilled so **By plan (draft)** and **CP-SAT draft** have missing hours to place.
3. Open app:
   - UI (direct Next.js): `http://localhost:13000`
   - Via Nginx reverse proxy: `http://localhost:18090`
   - API health: `http://localhost:18080/health`
   - Postgres on host (optional): `localhost:15432`

## Configuration

- Copy [.env.example](.env.example) to `.env` for local overrides (optional when using Docker Compose env vars).
- **Backend**: `ENVIRONMENT` is `local`, `development`, or `production`. In `production`, `SECRET_KEY` must not be the default `change-me`. Compose sets `ENVIRONMENT=local` and a dev-only `SECRET_KEY` for the backend service.
- **CORS**: optional `CORS_ORIGINS` (comma-separated). If unset, the API allows the built-in localhost origins used in this repo.
- **Frontend / API URL**: Docker Compose sets `NEXT_PUBLIC_API_URL=http://localhost:18080` so a browser on the host talking to the UI at `http://localhost:13000` can reach the API. If you use **only** Nginx at `http://localhost:18090`, you can point the UI at the same origin API prefix instead, for example `NEXT_PUBLIC_API_URL=http://localhost:18090/api` (see `infra/nginx/default.conf`), and rebuild the frontend image with that build arg.

## E2E tests (Playwright)

With the stack running (`docker compose up -d`):

```bash
cd frontend
npm install
npx playwright install chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:13000 PLAYWRIGHT_API_URL=http://127.0.0.1:18080 npm run test:e2e
```
