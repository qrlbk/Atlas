# Atlas MVP Release Plan

## Iteration A (Foundation)

- Docker Compose stack (`db`, `backend`, `frontend`, `nginx`)
- Core data model + Alembic migration
- JWT auth + role enforcement
- CRUD endpoints for key entities

## Iteration B (Core Value)

- Visual schedule grid in Next.js
- Drag-and-drop lesson movement with React DnD
- Real-time `/validation` API call on every move
- Critical rules 1-4 enforced and visualized

## Iteration C (MVP Completion)

- Grouped flow capacity validation (rule 5)
- Teacher windows detection (rule 6)
- Teacher analytics endpoint + UI widget
- Test coverage and acceptance smoke flow

## Deployment instructions

1. Build and run services:
   - `docker compose up --build`
2. Run backend migrations from backend container:
   - `alembic upgrade head`
3. Open UI:
   - `http://localhost:13000` (Next.js) or `http://localhost:18090` (Nginx)
4. API health:
   - `http://localhost:18080/health`
