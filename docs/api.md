# Справочник API

Базовый URL (локально): **http://localhost:18080**

Интерактивная документация: **http://localhost:18080/docs** (Swagger UI)

Через Nginx: **http://localhost:18090/api/** (префикс `/api` снимается прокси)

## Авторизация

```http
POST /auth/login
Content-Type: application/json

{ "email": "manager@atlas.example.com", "password": "AtlasSeed!2026" }
```

Ответ: `{ "access_token": "...", "token_type": "bearer" }`

Текущий пользователь (роль для UI guard):

```http
GET /auth/me
Authorization: Bearer <access_token>
→ { "id", "email", "full_name", "role", "school_id" }
```

Дальнейшие запросы:

```http
Authorization: Bearer <access_token>
X-Locale: ru
```

## Локализация ошибок

- Заголовок `X-Locale`: `en` | `ru` | `kk`
- Или `Accept-Language`
- Ответ: `Content-Language` + тело `{ "detail": "...", "code": "errors.*" }`

См. [i18n.md](i18n.md).

## Health

```http
GET /health
→ { "status": "ok" }
```

## Ресурсы школы

Префиксы без `/api` в прямом доступе к backend.

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/schools` | Список школ |
| PATCH | `/schools/{id}` | Обновление, в т.ч. `scheduling_preferences` |
| GET | `/subjects` | Предметы |
| GET | `/lesson-slots` | Слоты сетки |
| GET/POST/PATCH/DELETE | `/teachers` | Учителя |
| GET/POST/PATCH/DELETE | `/classrooms` | Кабинеты |
| GET/POST/PATCH/DELETE | `/classes` | Классы |
| GET/POST/PATCH/DELETE | `/grouped-flows` | Групповые потоки |
| GET/POST/PATCH/DELETE | `/class-subject-hours` | Учебный план |
| GET | `/schedule-plan-status?school_id=` | План vs факт |
| GET/POST/PATCH/DELETE | `/schedule` | Элементы расписания |
| GET | `/schedule-exports?school_id=&scope=&format=` | XLSX / PDF |

Все мутации требуют роли `admin` или `school_manager` (кроме чтения для `viewer` где разрешено).

## Валидация

```http
POST /validation
```

Тело: `school_id`, опционально `candidate` (гипотетический `ScheduleItemIn`).

Ответ: `issues[]` (code, severity, weight, message), `quality`.

## Подсказки и черновики

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/suggestions/slots` | Лучшие слот + кабинет |
| POST | `/suggestions/generate-class` | Greedy draft для класса |
| POST | `/suggestions/scenario-draft` | What-if сценарий |

### Пример: generate-class

```http
POST /suggestions/generate-class
{ "school_id": 1, "class_id": 3 }
```

```json
{
  "proposals": [ { "class_id": 3, "subject_id": 1, ... } ],
  "unplaced": [
    {
      "subject_id": 5,
      "subject_name": "Chemistry",
      "hours_missing": 1,
      "blocking_issues": ["SPECIAL_ROOM_MISMATCH"]
    }
  ]
}
```

## Solver jobs

| Метод | Путь |
|-------|------|
| POST | `/solver-jobs` |
| GET | `/solver-jobs/{job_id}` |
| POST | `/solver-jobs/{job_id}/cancel` |

Схема создания — [scheduling.md](scheduling.md#solver-jobs-async).

## Аналитика

| GET | Путь |
|-----|------|
| `/analytics/teachers` | Нагрузка по учителям |
| `/analytics/rooms` | Использование кабинетов |
| `/analytics/schedule-quality` | Сводка качества |
| `/analytics/teacher-load-matrix` | Матрица для heatmap |
| `/analytics/day-congestion` | Загрузка по дням |
| `/analytics/class-fatigue` | Метрика «усталости» класса |

Query: `school_id` (обязателен).

## Импорт

| Метод | Путь |
|-------|------|
| GET | `/imports/template?school_id=` |
| POST | `/imports/validate` | multipart |
| POST | `/imports/commit` | multipart |

Подробно: [import.md](import.md).

## Коды ответов

| Код | Ситуация |
|-----|----------|
| 200 | Успех |
| 401 | Нет или неверный JWT |
| 403 | Недостаточно прав / чужая школа |
| 404 | Сущность не найдена |
| 422 | Ошибка валидации Pydantic |
| 500 | Внутренняя ошибка |

## Draft operations (общий формат)

Solver и сценарии возвращают:

```json
{
  "type": "create",
  "id": null,
  "payload": {
    "school_id": 1,
    "class_id": 3,
    "subject_id": 2,
    "teacher_id": 7,
    "classroom_id": 4,
    "lesson_slot_id": 10,
    "is_grouped": false,
    "group_id": null
  }
}
```

`update` — с `id` существующего item; `delete` — с `id`, `payload` может быть null.

Frontend применяет их к локальному состоянию сетки, затем пользователь сохраняет.

## Admin API (internal, `role=admin` only)

Префикс `/admin`. Школьный `PATCH /schools/{id}` не меняет `name`/`address` — только через admin.

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/admin/dashboard` | KPI + attention (top 10) |
| GET | `/admin/schools` | Список школ (query: `plan`, `health`, `q`, `sort`, `page`, `page_size`) |
| POST | `/admin/schools` | Создать школу + manager; пароль менеджера только в ответе |
| GET | `/admin/schools/{id}` | Карточка: readiness, users, usage, snapshots |
| PATCH | `/admin/schools/{id}` | name, address, plan, trial, subscription, admin_notes, manual_pro, billing |
| GET | `/admin/schools/{id}/events` | Лента `school_events` |
| POST | `/admin/schools/{id}/actions/extend-trial` | `{ "days": 14 }` |
| POST | `/admin/schools/{id}/actions/activate-pro` | `{ "until", "amount_kzt?", "period_label?" }` |

Список школ использует кэш `schools.readiness_status` / `readiness_checked_at` (миграция `0005_readiness_cache`).

### Smoke checklist (MVP)

1. Войти как admin → открыть `/admin`, KPI и attention.
2. `/admin/schools` — фильтры plan/health, поиск.
3. Создать школу → скопировать пароль → карточка школы.
4. Extend trial, Activate Pro, сохранить admin notes.
5. Лента событий: `admin.school_created`, `admin.trial_extended`, `admin.pro_activated`.
6. `school_manager` → `403` на `/admin/dashboard`.

## OpenAPI и типы

Pydantic-схемы: `backend/app/schemas/`. Для frontend — зеркало в `frontend/src/lib/api.ts`.

При изменении API обновляйте оба места и тесты в `backend/tests/`.
