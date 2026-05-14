# Atlas MVP

Atlas is an MVP web platform for manual school schedule management with real-time validation.

## MVP scope

- Manual schedule building only (no auto-generation).
- Real-time validation for schedule conflicts and constraints.
- Visual schedule builder with drag-and-drop.
- Role-based access with JWT authentication.

## Out of scope (MVP)

- Full-school AI / CP-SAT timetable optimization (post-MVP may add heuristics or solvers on top of the same validation layer)
- Telegram bot
- ERP/accounting/payroll
- Mobile app
- Government platform integrations

## Post-MVP scheduling features (current codebase)

- **Curriculum plan**: `class_subject_hours` — weekly hours per class and subject. CRUD: `/class-subject-hours` (see API). School managers edit the plan in the UI at **`/curriculum`**. Seeded to match the demo schedule.
- **Stricter validation**: `CLASS_DOUBLE_BOOKING`, `TEACHER_SUBJECT_MISMATCH`, and plan checks `PLAN_UNDERFILLED` / `PLAN_OVERFLOW`.
- **Constraint weights**: each `ValidationIssue` includes a `weight`; schools may override via `schools.scheduling_preferences.issue_weights` (JSON).
- **Quality score**: `POST /validation` returns `quality` (total penalty and breakdown).
- **Suggestions**: `POST /suggestions/slots` (rank slot + room for a candidate lesson), `POST /suggestions/generate-class` (greedy draft for one class from curriculum). The schedule builder has **Подобрать слот** and **По плану (черновик)** when the grid matches the server (save local edits first — validation and generation use persisted school schedule).
- **Plan coverage (read-only)**: `GET /schedule-plan-status?school_id=…` aggregates `class_subject_hours` vs `schedule_items` (planned vs scheduled hours per row, `fill_rate`, classes with no plan rows). Used by the dashboard overview and curriculum screen.

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

## Future timetable solver (contract; not implemented in MVP)

This describes how a future CP-SAT / LNS / heuristic solver should plug into Atlas without changing the product model.

- **Input**: a consistent DB snapshot (or `school_id` inside a transaction), the set of mutable entities (e.g. schedule items to add/move), optional frozen slots or “do not touch” lessons, and school preferences (`scheduling_preferences`).
- **Oracle**: `validate_schedule(db, school_id, candidate_item_or_none)` — same rules as the live UI and `/validation`.
- **Objective**: minimize `score_validation_issues(issues)` (total penalty and per-code breakdown already returned by `POST /validation`). The solver searches for assignments that reduce penalty while keeping **zero error-severity** issues (or respects school policy such as `plan_compliance: "error"`).
- **Output**: a list of operations compatible with applying changes the way the UI does today — e.g. batch create/update/delete schedule items, or a shape aligned with the frontend’s draft application flow (`applyScheduleDraft`-style). A dedicated batch REST endpoint would be post-MVP.

## Class draft generator limitations (v1)

`generate_draft_for_class` in `backend/app/services/schedule_solver.py` is a **greedy helper**, not a global solver. Limitations (see also the module docstring there):

- Proposed lessons are always **`is_grouped=False`** with `group_id=None` — **grouped flows / shared lessons are not represented** in this autofill path.
- Teacher order is deterministic, not optimized for fairness or preferences.
- Slot/room search is first-fit among combinations that pass the oracle, not cost-optimal across the whole week.
- Post-MVP extensions: grouped lessons, teacher/slot preferences, and a true optimizer on top of the same oracle and scoring.

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

   Also seeds demo school, subjects, and Mon–Fri lesson slots.
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
