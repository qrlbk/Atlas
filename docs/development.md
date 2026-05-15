# Разработка

## Локальная среда

### Вариант 1: Docker (рекомендуется)

```bash
docker compose up --build
```

Backend с hot-reload в Docker **не** настроен — для активной разработки Python используйте вариант 2.

### Вариант 2: Гибрид

1. `docker compose up -d db` (только Postgres).
2. Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://atlas:atlas@localhost:15432/atlas
export SECRET_KEY=dev-local-secret
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

3. Frontend:

```bash
cd frontend
npm ci
export NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

UI: http://localhost:3000

## Структура тестов

### Backend (`pytest`)

```bash
cd backend
pytest
pytest tests/test_cp_sat_solver.py -v
```

| Каталог / файл | Назначение |
|----------------|------------|
| `test_validation_engine.py` | Правила oracle |
| `test_cp_sat_solver.py` | CP-SAT (skip без ortools) |
| `test_solver_jobs.py` | Async jobs |
| `test_scenario_engine.py` | Сценарии |
| `test_mvp_acceptance.py` | Сквозные сценарии MVP |
| `test_imports.py` | Excel import |

### Frontend

```bash
cd frontend
npm run lint
npx vitest run src
npm run build
npx tsc --noEmit
```

### E2E (Playwright)

Стек должен быть запущен:

```bash
docker compose up -d
cd frontend
npm install
npx playwright install chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:13000 \
PLAYWRIGHT_API_URL=http://127.0.0.1:18080 \
npm run test:e2e
```

## CI

GitHub Actions (`.github/workflows/ci.yml`):

| Job | Шаги |
|-----|------|
| `backend` | `pip install`, `pytest` |
| `frontend` | `npm ci`, lint, vitest, `npm run build` |
| `e2e` | Compose + Playwright (после backend/frontend) |

## Миграции БД

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

В Docker миграции выполняет `docker-entrypoint.sh` при старте.

## Добавление правила валидации

1. Код в `validation_engine.py`.
2. Запись в `constraint_catalog.py` (weight + kind).
3. Ключи i18n в `backend/app/i18n/core.py`.
4. Сообщения UI в `frontend/messages/*.json` (`validation.*`).
5. Тест в `test_validation_engine.py`.

## Добавление эндпоинта

1. Схема в `app/schemas/`.
2. Роутер в `app/api/`.
3. Подключение в `app/main.py` (если новый router).
4. Тест + обновление `frontend/src/lib/api.ts`.

## OR-Tools

CP-SAT опционален на dev-машине без Docker:

```bash
pip install ortools
```

В `requirements.txt` пакет указан — образ backend включает его.

## Seed и демо-данные

```bash
cd backend
python -m app.scripts.seed
```

Или автоматически при старте контейнера. Профиль: `ATLAS_DEMO_GENERATION_PROFILE`.

## Полезные команды

```bash
# Логи
docker compose logs -f backend

# Shell в backend
docker compose exec backend bash

# Postgres
docker compose exec db psql -U atlas -d atlas
```

## Стиль кода

- Python: следовать существующим модулям `services/`, type hints, без лишних абстракций.
- TypeScript/React: компоненты в `src/components/`, страницы тонкие.
- Не коммитить `.env`, секреты, `node_modules`, `.next`.

См. [архитектуру](architecture.md) и [API](api.md).
