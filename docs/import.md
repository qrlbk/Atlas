# Excel data import

The Atlas backend exposes a three-step Excel import that lets a school manager
seed or update school data without filling forms one by one. The flow is:

1. `GET /imports/template?school_id=<id>` — download a pre-formatted `.xlsx`
   workbook with one sheet per entity.
2. Each data sheet is laid out as: **row 1** — machine column names (dark header);
   **row 2** — hints (light blue, every cell starts with `# ` and is **ignored** on
   import); **row 3** — green banner row (also `# …`, ignored); **row 4+** — your
   data. Empty rows are skipped.
3. `POST /imports/validate` (multipart) — dry-run: returns ordered issues
   (errors + warnings) and a per-sheet summary, no database writes.
4. `POST /imports/commit` (multipart) — applies the workbook inside a single
   transaction. Rolls back on any error.

Both POST endpoints accept:

- `school_id` (form field, required)
- `file` (multipart, required) — the workbook bytes
- `modes` (optional JSON, e.g. `{"Schedule": "replace", "Teachers": "upsert"}`)

Supported modes per sheet:

- `upsert` — update matching rows by natural key + insert new ones (default for
  catalog sheets).
- `replace` — wipe this school's rows in that sheet and recreate from the
  workbook (default for `Schedule`; allowed for `Curriculum` too).
- `append` — only insert new rows. Rows matching an existing natural key are
  reported as `skipped`.
- `skip` — ignore the sheet entirely.

## Workbook structure

| Sheet         | Natural key                       | Columns                                                                                          |
|---------------|-----------------------------------|---------------------------------------------------------------------------------------------------|
| `Subjects`    | `name` (global)                   | `name`, `requires_special_room`, `required_specialization`                                        |
| `LessonSlots` | `day_of_week + lesson_number`     | `day_of_week`, `lesson_number`, `start_time`, `end_time`                                          |
| `Classes`     | `class_name` (per school)         | `class_name`, `students_count`                                                                    |
| `Teachers`    | `full_name` (per school)          | `full_name`, `subjects` (comma-sep), `weekly_load_limit`, `unavailable_days` (comma-sep `1..7`)   |
| `Classrooms`  | `room_number` (per school)        | `room_number`, `capacity`, `specialization`                                                       |
| `GroupFlows`  | `group_name` (per school)         | `group_name`, `combined_classes` (comma-sep class_name values)                                    |
| `Curriculum`  | `class_name + subject_name`       | `class_name`, `subject_name`, `hours_per_week`                                                    |
| `Schedule`    | `class_name + day + lesson`       | `class_name`, `subject_name`, `teacher_full_name`, `room_number`, `day_of_week`, `lesson_number`, `is_grouped`, `group_name` |

Notes:

- Booleans accept `true/false`, `yes/no`, `1/0`, `да/иә`.
- Empty rows are ignored. Row 2 (the hint row) is detected as data and
  validated — leave it untouched only if it is a string starting with `#`,
  otherwise remove it before upload.
- Dependent sheets can reference natural keys introduced earlier in the same
  workbook: e.g. `Schedule` can use a teacher created on the `Teachers` sheet.

## Permissions

- Only `admin` and `school_manager` can call the import endpoints (`viewer`
  receives `403 errors.insufficientPermissions`).
- Non-admin users can only import into their own school
  (`403 errors.crossSchoolAccessDenied`).

## Error codes

The validate response returns an `issues[]` array. Each issue includes
`sheet`, optional `row`/`column`, `severity` (`error`/`warning`), a stable
`code` and a human message. Common codes:

- `missing_column`, `required`, `duplicate`
- `invalid_int`, `invalid_time`, `invalid_day`, `invalid_enum`
- `unknown_class`, `unknown_subject`, `unknown_teacher`, `unknown_room`,
  `unknown_slot`, `unknown_flow`
- `group_ignored` (warning) when `group_name` is set but `is_grouped` is false

The commit endpoint refuses to write anything if `issues` contain any `error`
severity entry; the response will have `committed: false` and `applied: []`.

## Frontend

The UI lives in `frontend/src/app/import/page.tsx` and reuses the
`ImportWizard` component (`frontend/src/components/import/ImportWizard.tsx`).
The wizard:

1. Calls `GET /imports/template` to download the file.
2. Sends the user-uploaded workbook to `POST /imports/validate`.
3. Renders the preview table with per-sheet mode selectors.
4. On confirm, sends the same workbook + selected modes to `POST /imports/commit`.
