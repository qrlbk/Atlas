# ТЗ: Панель управления Atlas (Admin Console)

**Версия:** 1.0  
**Дата:** 2026-05-18  
**Статус:** Черновик к реализации  
**Связанные документы:** [Архитектура](architecture.md), [API](api.md), [Развёртывание](deployment.md), [README — тарифы](README.md)

---

## 1. Назначение

### 1.1. Проблема

После внедрения Free/Pro, trial, readiness и event log операции владельца продукта выполняются вручную:

- `PATCH /schools/{id}` через Postman;
- прямые запросы к PostgreSQL;
- нет единого места для support, биллинга и обзора школ.

### 1.2. Цель

Создать **внутреннюю панель управления** (Admin Console) для роли `admin`, отделённую от школьного приложения Atlas.

**Результат для владельца продукта:**

- видеть все школы и их статус (тариф, health, активность);
- включать Pro / продлевать trial без Postman;
- разбирать обращения в support по логу событий;
- создавать новые школы и первого завуча;
- фиксировать оплату (manual billing v1).

### 1.3. Не является целью

- Замена школьного UI (`/schedule`, `/curriculum`, …).
- Полноценный CRM, ERP, биллинг со Stripe (отдельная итерация).
- District / white-label / мультирегион (Tier B).
- Редактирование расписания из админки.

---

## 2. Пользователи и роли

| Роль | Доступ к Admin Console | Доступ к школьному Atlas |
|------|------------------------|---------------------------|
| `admin` | Полный | Все школы (как сейчас в API) |
| `school_manager` | **Нет** | Только своя школа |
| `viewer` | **Нет** | Только просмотр своей школы |

**Операторы v1:** разработчик / основатель продукта, позже — support (отдельные admin-аккаунты).

**Аутентификация:** тот же JWT (`POST /auth/login`), что и у школ. После входа frontend проверяет `role === admin`; иначе редирект на `/` с сообщением «Недостаточно прав».

---

## 3. Размещение в продукте

### 3.1. URL

**Вариант A (рекомендуется для v1):** тот же frontend, префикс маршрутов:

```text
/admin              — дашборд
/admin/schools      — список школ
/admin/schools/[id] — карточка школы
/admin/schools/new  — создание школы
```

**Вариант B (production):** поддомен `admin.atlas.example.com` — тот же Next.js build, env `ADMIN_HOST`.

### 3.2. UI

- Отдельный layout: без школьного sidebar (Schedule, Curriculum, …).
- Sidebar админки: Dashboard, Schools, (позже) Users, (позже) Metrics.
- Язык интерфейса v1: **русский** (опционально en для внутренней команды).

---

## 4. Функциональные требования

### 4.1. Дашборд (`/admin`)

**FR-ADM-01.** Сводные KPI (карточки):

| Метрика | Источник |
|---------|----------|
| Всего школ | `COUNT(schools)` |
| Free / Pro | `schools.plan` |
| Trial активен | `trial_ends_at > now()` |
| Readiness RED | агрегация `GET readiness` или кэш |
| Событий за 24 ч | `school_events` |

**FR-ADM-02.** Таблица «Требуют внимания» (топ 10):

- школы со `readiness.status = red`;
- или trial истекает в ближайшие 7 дней;
- или нет событий > 30 дней (неактивные).

**FR-ADM-03.** Быстрые действия: ссылка «Все школы», «Создать школу».

---

### 4.2. Список школ (`/admin/schools`)

**FR-ADM-10.** Таблица с колонками:

| Колонка | Описание |
|---------|----------|
| ID | `school.id` |
| Название | `school.name` |
| План | `free` / `pro` + бейдж «trial» если активен |
| Pro доступ | да/нет (`has_pro_access`) |
| Health | `green` / `yellow` / `red` / `unknown` |
| Publish | `schedule_publish_state` |
| Trial до | `trial_ends_at` |
| Подписка до | `subscription_ends_at` |
| Последняя активность | `MAX(school_events.created_at)` |
| Создана | `school.created_at` |

**FR-ADM-11.** Фильтры:

- план (free/pro);
- health status;
- только trial;
- поиск по названию (substring).

**FR-ADM-12.** Сортировка по: названию, последней активности, health, trial_ends_at.

**FR-ADM-13.** Пагинация: 25 / 50 на страницу.

**FR-ADM-14.** Клик по строке → карточка школы.

---

### 4.3. Карточка школы (`/admin/schools/{id}`)

#### Блок A — Реквизиты

**FR-ADM-20.** Просмотр и редактирование:

- название, адрес (если добавить в PATCH — сейчас только preferences/plan);
- `plan`: select `free` | `pro`;
- `trial_ends_at`: date picker;
- `subscription_ends_at`: date picker;
- флаг **manual Pro**: `scheduling_preferences.manual_pro` (checkbox);
- **admin notes**: `scheduling_preferences.admin_notes` (textarea, только для админки).

**FR-ADM-21.** Кнопки действий:

| Кнопка | Действие |
|--------|----------|
| Сохранить | `PATCH /admin/schools/{id}` |
| Продлить trial +14 дней | `trial_ends_at = now + 14d` |
| Включить Pro на год | `plan=pro`, `subscription_ends_at = now + 1y` |
| Сбросить onboarding | `onboarding_completed = false` |

**FR-ADM-22.** Read-only блок **Health** (вызов существующего readiness):

- статус GREEN/YELLOW/RED/UNKNOWN;
- 3 blocker + recommendations;
- ссылка «Открыть школьный дашборд» (`/` с контекстом школы — см. impersonation, фаза 2).

#### Блок B — Пользователи школы

**FR-ADM-30.** Таблица пользователей с `school_id = id`:

- email, full_name, role;
- действия v1: только просмотр.

**FR-ADM-31.** (Фаза 2) Создать manager, сброс пароля.

#### Блок C — События (audit)

**FR-ADM-40.** Лента `school_events` (последние 50, пагинация):

| Поле | Описание |
|------|----------|
| Время | `created_at` |
| Тип | `event_type` |
| User | `user_id` → email |
| Payload | JSON collapse (кратко: error_count, strategy, snapshot_id) |

Фильтр по `event_type`: import.*, solver.*, schedule.published, readiness.checked.

#### Блок D — Usage (монетизация)

**FR-ADM-41.** Текущий месяц из `usage_counters`:

- `solver_job` — count;
- `slot_suggestion` — count.

#### Блок E — Snapshots

**FR-ADM-42.** Список `schedule_snapshots` (read-only v1):

- label, reason, created_at, item_count;
- (Фаза 2) кнопка Restore с подтверждением.

#### Блок F — Billing note (manual v1)

**FR-ADM-43.** Форма «Оплата» (сохраняется в `scheduling_preferences` или отдельная таблица фазы 2):

```json
{
  "billing_status": "pending | paid | invoice_sent",
  "billing_amount_kzt": 250000,
  "billing_period": "2026-2027",
  "billing_paid_at": "2026-08-15",
  "billing_contact": "ТОО ..., БИН ..."
}
```

При статусе `paid` — опционально автоматически выставить `plan=pro` и `subscription_ends_at`.

---

### 4.4. Создание школы (`/admin/schools/new`)

**FR-ADM-50.** Форма:

| Поле | Обязательно |
|------|-------------|
| Название школы | да |
| Адрес | да |
| Email первого manager | да |
| ФИО manager | да |
| Временный пароль | да (или auto-generate + показать один раз) |
| План по умолчанию | free |
| Trial 14 дней | checkbox, default on |

**FR-ADM-51.** Backend атомарно:

1. `INSERT school` + `trial_ends_at` если trial;
2. `INSERT user` role=`school_manager`, `school_id`;
3. `log_school_event` type=`admin.school_created`;
4. ответ: `school_id`, credentials (пароль только в ответе create, не в логах).

---

### 4.5. Impersonation (фаза 2, опционально в ТЗ)

**FR-ADM-60.** Кнопка «Войти как завуч этой школы»:

- выдача short-lived JWT с `school_id` и role=school_manager, claim `impersonated_by=admin_id`;
- баннер в школьном UI: «Режим поддержки»;
- все действия пишутся в `school_events` с `impersonated_by`.

**Не в MVP** — высокий риск безопасности, требует отдельного review.

---

## 5. Backend API (новое)

Префикс: `/admin`  
Guard: `require_roles(UserRole.admin)` на всех эндпоинтах.

### 5.1. Эндпоинты MVP

| Method | Path | Описание |
|--------|------|----------|
| GET | `/admin/dashboard` | KPI + attention list |
| GET | `/admin/schools` | Список с фильтрами, пагинация |
| GET | `/admin/schools/{id}` | Полная карточка (school + users + events + usage + snapshots summary) |
| PATCH | `/admin/schools/{id}` | Расширенный patch (name, address, plan, trial, subscription, preferences) |
| POST | `/admin/schools` | Создание школы + manager |
| GET | `/admin/schools/{id}/events` | Пагинация school_events |
| POST | `/admin/schools/{id}/actions/extend-trial` | `days=14` |
| POST | `/admin/schools/{id}/actions/activate-pro` | body: `until`, optional `amount_kzt` для notes |

### 5.2. Схемы (Pydantic)

```text
AdminSchoolListItem
  - все поля SchoolOut
  - readiness_status: str
  - last_event_at: datetime | null
  - pro_access: bool
  - manager_count: int

AdminSchoolDetail
  - school: SchoolOut
  - readiness: SchoolReadinessOut
  - users: list[UserOut]
  - usage: dict[str, int]
  - snapshots: list[ScheduleSnapshotOut]  # last 10

AdminSchoolCreate
  - name, address
  - manager_email, manager_full_name, manager_password
  - start_trial: bool = true
  - plan: str = "free"

AdminDashboardOut
  - totals: dict
  - attention: list[AdminSchoolListItem]
```

### 5.3. Отличие от существующих API

| Существует | Admin |
|------------|-------|
| `GET /schools` (admin sees all) | Обогащён readiness + last_event |
| `PATCH /schools/{id}` (plan только admin) | + name, address, admin_notes, presets |
| `GET /schools/{id}/readiness` | Включено в detail |
| — | `GET .../events`, `POST /admin/schools` |

**Правило:** школьные эндпоинты не менять контракт; admin — отдельный router `backend/app/api/admin.py`.

---

## 6. Frontend

### 6.1. Структура файлов

```text
frontend/src/app/admin/
  layout.tsx          # проверка role admin
  page.tsx            # dashboard
  schools/
    page.tsx          # list
    new/page.tsx      # create
    [id]/page.tsx     # detail

frontend/src/components/admin/
  AdminShell.tsx
  SchoolsTable.tsx
  SchoolDetailForm.tsx
  SchoolEventsList.tsx
  BillingNoteForm.tsx
```

### 6.2. Защита маршрутов

- `AdminLayout`: если нет token → login; если role !== admin → redirect `/` + toast.
- Не показывать пункт Admin в школьном sidebar для manager.

### 6.3. API client

Расширить `frontend/src/lib/api.ts`:

```text
adminDashboard()
adminListSchools(params)
adminGetSchool(id)
adminPatchSchool(id, body)
adminCreateSchool(body)
adminSchoolEvents(id, page)
adminExtendTrial(id, days)
adminActivatePro(id, until)
```

---

## 7. Безопасность

| ID | Требование |
|----|------------|
| SEC-01 | Все `/admin/*` только для JWT с `role=admin` |
| SEC-02 | Admin routes не попадают в публичную документацию для школ без пометки «internal» |
| SEC-03 | Пароль нового manager возвращается один раз; не логировать в `school_events.payload` |
| SEC-04 | Rate limit на `POST /admin/schools` (опционально) |
| SEC-05 | CORS: admin UI только с доверенных origin |
| SEC-06 | Audit: каждое действие admin → `school_events` тип `admin.*` с `user_id=admin` |

**Типы событий admin (добавить):**

- `admin.school_created`
- `admin.plan_changed`
- `admin.trial_extended`
- `admin.pro_activated`
- `admin.notes_updated`

---

## 8. Данные и миграции

### 8.1. MVP — без новых таблиц

Использовать:

- `schools` (plan, trial, subscription, publish_state);
- `users`;
- `school_events`;
- `usage_counters`;
- `schedule_snapshots`;
- `scheduling_preferences` для `admin_notes`, `manual_pro`, `billing_*`.

### 8.2. Фаза 2 (опционально)

Таблица `billing_records`:

```text
id, school_id, amount_kzt, period_label, status, paid_at, invoice_ref, created_by, created_at
```

---

## 9. Нефункциональные требования

| ID | Требование |
|----|------------|
| NFR-01 | Список школ: ответ < 2 с при до 500 школах |
| NFR-02 | Readiness на списке: batch или кэш 60 с (не N вызовов validate на каждую строку) |
| NFR-03 | Mobile: read-only допустим; основной UX — desktop |
| NFR-04 | Доступность: таблицы с keyboard navigation (базово) |

**Кэш readiness для списка (рекомендация):**

- поле `schools.readiness_status` + `readiness_checked_at` обновлять при `readiness.checked` event;
- или материализованный job раз в час.

---

## 10. Этапы реализации

### Этап 1 — MVP (1–2 недели)

- [ ] Backend: `admin.py` router, dashboard, schools list/detail, patch, create school
- [ ] Backend: `GET .../events`
- [ ] Backend: admin.* event types
- [ ] Frontend: AdminShell + dashboard + schools list + school detail (plan/trial/pro/notes)
- [ ] Frontend: create school
- [ ] Тесты: 403 для manager на `/admin/*`
- [ ] Документация: раздел в [api.md](api.md)

**Критерий приёмки MVP:** без Postman можно создать школу, включить Pro, увидеть events по школе.

### Этап 2 — Support (1 неделя)

- [ ] Usage counters на карточке
- [ ] Snapshots list
- [ ] Billing note form + preset «оплачено → Pro»
- [ ] Фильтры и поиск в списке

### Этап 3 — Growth (позже)

- [ ] Impersonation
- [ ] Сброс пароля / invite manager
- [ ] Metrics dashboard (графики)
- [ ] Stripe webhook → auto `plan=pro`
- [ ] Email notifications

---

## 11. Вне скоупа (явно)

- Telegram-бот админки
- Мобильное приложение admin
- Редактирование расписания
- Управление глобальными subjects / lesson_slots (остаётся seed/миграции)
- Мультиязычность admin UI (кроме ru опционально en)

---

## 12. Зависимости от текущего кода

| Компонент | Статус |
|-----------|--------|
| `School.plan`, trial, subscription | Есть (миграция 0004) |
| `school_events` | Есть, нужен read API |
| `usage_counters` | Есть, нужен read в admin detail |
| `schedule_snapshots` | Есть list API на school scope |
| `school_readiness` service | Есть, переиспользовать |
| `entitlements.has_pro_access` | Есть, показывать в UI |
| `PATCH /schools` plan (admin) | Есть, расширить |
| Admin UI | **Нет** |

---

## 13. Критерии приёмки (сводка)

1. Пользователь с `role=admin` открывает `/admin` и видит сводку по школам.
2. В списке школ отображаются plan, trial, health, last activity.
3. В карточке школы можно выставить Pro, продлить trial, записать admin note.
4. Видна лента `school_events` по школе.
5. Можно создать новую школу с первым manager; trial 14 дней по умолчанию.
6. `school_manager` получает 403 на любой `/admin/*`.
7. Backend tests покрывают guard и create school.

---

## 14. Открытые вопросы

| # | Вопрос | Решение по умолчанию |
|---|--------|----------------------|
| 1 | Отдельный поддомен admin? | Нет в MVP, только `/admin` |
| 2 | Редактировать name/address школы? | Да в admin PATCH |
| 3 | Хранить billing в JSON или таблице? | JSON в MVP |
| 4 | Readiness на списке — live или кэш? | Кэш / упрощённый статус в MVP |
| 5 | Несколько admin-аккаунтов? | Да, любой user с role=admin |

---

## 15. Ссылки на макеты (текстовый wireframe)

### Дашборд

```text
+--------------------------------------------------+
| Atlas Admin                    [admin@...] [Out]|
+--------------------------------------------------+
| [48 школ] [32 free] [16 pro] [5 trial] [12 RED]  |
+--------------------------------------------------+
| Требуют внимания                                  |
| * Школа №12 — RED — trial истёк 2 дня назад      |
| * Лицей Абай — unknown — нет onboarding           |
+--------------------------------------------------+
| [Все школы]  [+ Создать школу]                    |
+--------------------------------------------------+
```

### Карточка школы

```text
+--------------------------------------------------+
| ← Школы    Гимназия №1 (#3)          [Сохранить] |
+--------------------------------------------------+
| План [Pro v]  Trial до [2026-06-01]  Sub до [...] |
| [x] manual Pro   Health: YELLOW                   |
| Admin notes: ________________________________   |
| [+14 trial] [Pro на год] [Сбросить onboarding]  |
+--------------------------------------------------+
| Health: ...blockers...                            |
| Users: manager@school.kz (school_manager)         |
| Events: import.committed 2026-05-17 14:32 ...     |
| Usage: solver 3, slots 12                         |
+--------------------------------------------------+
```

---

*Конец документа.*
