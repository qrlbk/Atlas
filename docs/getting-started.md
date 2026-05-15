# Начало работы

Это руководство поможет запустить Atlas локально и войти в демо-школу за несколько минут.

## Требования

- Docker Desktop (или Docker Engine + Compose v2)
- ~4 GB свободной RAM для сборки frontend
- Браузер с поддержкой современного JavaScript

## Запуск через Docker Compose

Из корня репозитория:

```bash
docker compose up --build -d
```

Проверка:

```bash
curl http://localhost:18080/health
# {"status":"ok"}
```

Остановка:

```bash
docker compose down
```

Полная пересборка (после изменений в коде):

```bash
docker compose down
docker compose up --build -d
```

### Порты

| Порт | Сервис |
|------|--------|
| `13000` | Frontend (Next.js) |
| `18080` | Backend (FastAPI) |
| `18090` | Nginx (UI + `/api` → backend) |
| `15432` | PostgreSQL |

### Учётные записи по умолчанию

| Роль | Email | Пароль |
|------|-------|--------|
| Admin | `admin@atlas.example.com` | `AtlasSeed!2026` |
| School Manager | `manager@atlas.example.com` | `AtlasSeed!2026` |

Переопределение — переменные `ATLAS_SEED_*` в `docker-compose.yml`.

## Первый вход

1. Откройте http://localhost:13000 (или http://localhost:18090 через Nginx).
2. Войдите как **School Manager** — откроется демо-школа **Atlas Demo School**.
3. Перейдите в **Расписание** (`/schedule`) — сетка Пн–Пт с уроками.
4. На **главной** — сводка качества и покрытия плана.

## Что делает seed

При каждом старте backend для **Atlas Demo School**:

- Обновляет справочники (учителя, кабинеты, классы, потоки) по скрипту `backend/app/scripts/seed.py`.
- **Пересоздаёт** `schedule_items` и `class_subject_hours`, чтобы демо-сетка была предсказуемой.
- Оставляет несколько намеренно незаполненных часов плана — для кнопок **По плану (черновик)** и CP-SAT.

Профиль демо-генерации: `ATLAS_DEMO_GENERATION_PROFILE=partial` (по умолчанию) или `sparse` (больше «дыр» для тестов solver).

## Конфигурация

Скопируйте [.env.example](../.env.example) в `.env` при локальной разработке без Docker.

| Переменная | Назначение |
|------------|------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT; в `production` нельзя оставлять `change-me` |
| `ENVIRONMENT` | `local` \| `development` \| `production` |
| `CORS_ORIGINS` | Список origin через запятую (опционально) |
| `NEXT_PUBLIC_API_URL` | URL API для браузера (build-time для frontend) |

### Два способа связать UI и API

**Вариант A — прямой доступ (по умолчанию в Compose):**

```text
Браузер → http://localhost:13000  (UI)
Браузер → http://localhost:18080  (API)
```

`NEXT_PUBLIC_API_URL=http://localhost:18080`

**Вариант B — единый origin через Nginx:**

```text
Браузер → http://localhost:18090       (UI)
Браузер → http://localhost:18090/api   (прокси на backend)
```

Пересоберите frontend с `NEXT_PUBLIC_API_URL=http://localhost:18090/api` (см. `infra/nginx/default.conf`).

## Типичные проблемы

### `docker-credential-desktop` not found

Docker не находит credential helper. Варианты:

- Переустановить / перезапустить Docker Desktop.
- Временно убрать `"credsStore": "desktop"` из `~/.docker/config.json`.
- Добавить заглушку `docker-credential-desktop` в `PATH` (для CI/скриптов).

### Backend не отвечает сразу после старта

Подождите 5–10 с: Alembic + seed + Uvicorn. Логи:

```bash
docker compose logs -f backend
```

### CP-SAT недоступен

Если OR-Tools не установлен в образе, whole-school jobs откатываются на greedy. Проверка — в логах job или `backend/tests/test_cp_sat_solver.py` (skip без ortools).

## Дальше

- [Руководство пользователя](user-guide.md) — экраны и рабочие процессы
- [Планирование и solver](scheduling.md) — автогенерация и правила
- [Разработка](development.md) — тесты и E2E
