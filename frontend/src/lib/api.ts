const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:18080";

const TOKEN_KEY = "atlas_access_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** True in the browser when a JWT is present (avoids API calls before auth UI syncs). */
export function hasAuthToken(): boolean {
  return Boolean(getStoredToken());
}

export function setStoredToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function handleUnauthorizedResponse(response: Response) {
  if (response.status !== 401) return;
  if (typeof window !== "undefined") {
    clearStoredToken();
    window.dispatchEvent(new CustomEvent("atlas-auth-expired"));
  }
}

function authHeaders(): HeadersInit {
  const token = getStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const locale = localStorage.getItem("atlas_locale") ?? "en";
    headers["X-Locale"] = locale;
    headers["Accept-Language"] = locale;
  }
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers as Record<string, string> | undefined) }
  });
  handleUnauthorizedResponse(response);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function requestVoid(path: string, init: RequestInit = {}): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers as Record<string, string> | undefined) }
  });
  handleUnauthorizedResponse(response);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
}

function multipartHeaders(): HeadersInit {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (typeof window !== "undefined") {
    const locale = localStorage.getItem("atlas_locale") ?? "en";
    headers["X-Locale"] = locale;
    headers["Accept-Language"] = locale;
  }
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function requestMultipart<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: multipartHeaders(),
    body
  });
  handleUnauthorizedResponse(response);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: multipartHeaders()
  });
  handleUnauthorizedResponse(response);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.blob();
}

export type Teacher = {
  id: number;
  full_name: string;
  subjects: string[];
  weekly_load_limit: number;
  unavailable_days: number[];
  school_id: number;
};

export type Classroom = {
  id: number;
  room_number: string;
  capacity: number;
  specialization: string;
  school_id: number;
};

export type StudentClass = {
  id: number;
  class_name: string;
  students_count: number;
  school_id: number;
};

export type GroupFlow = {
  id: number;
  group_name: string;
  combined_classes: number[];
  school_id: number;
};

export type ScheduleItem = {
  id?: number;
  class_id: number;
  subject_id: number;
  teacher_id: number;
  classroom_id: number;
  lesson_slot_id: number;
  is_grouped: boolean;
  group_id?: number | null;
  school_id: number;
};

export type ValidationIssue = {
  issue_code: string;
  severity: "error" | "warning";
  message: string;
  entity_refs: Record<string, unknown>;
  slot_ref?: Record<string, unknown>;
  suggested_fix?: string;
  weight?: number;
};

export type ValidationQuality = {
  total_penalty: number;
  breakdown_by_code: Record<string, number>;
  by_severity: Record<string, number>;
  error_count: number;
  warning_count: number;
};

export type TeacherAnalytics = {
  teacher_id: number;
  teacher_name: string;
  current_load: number;
  weekly_limit: number;
  windows: number;
  daily_load?: Record<string, number>;
  max_daily_load?: number;
};

export type RoomAnalytics = {
  room_id: number;
  room_number: string;
  specialization: string;
  lessons_count: number;
  capacity: number;
  max_class_size: number;
  over_capacity_risk: boolean;
};

export type School = {
  id: number;
  name: string;
  address: string;
  scheduling_preferences?: Record<string, unknown> | null;
};

export type Subject = {
  id: number;
  name: string;
  requires_special_room: boolean;
  required_specialization: string | null;
};

export type LessonSlot = {
  id: number;
  day_of_week: number;
  lesson_number: number;
  start_time: string;
  end_time: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
};

export type ScheduleDraftOperation =
  | { type: "create"; payload: ScheduleItem }
  | { type: "update"; id: number; payload: ScheduleItem }
  | { type: "delete"; id: number };

export type ScenarioDraftResponse = {
  operations: ScheduleDraftOperation[];
  issues: string[];
};

export type UnplacedDetail = {
  subject_id: number;
  subject_name?: string | null;
  class_ids?: number[];
  group_id?: number | null;
  hours_missing?: number;
  blocking_issues: string[];
};

export type SolverJobRequest = {
  school_id: number;
  class_id?: number | null;
  strategy?: string;
  regenerate_mode?: "fill_gaps" | "from_plan";
  frozen_lesson_slot_ids?: number[];
  max_runtime_seconds?: number;
  deterministic_seed?: number;
  apply_as_draft?: boolean;
};

export type SolverJobStatus = {
  job_id: string;
  status: string;
  strategy: string;
  progress: number;
  error?: string | null;
  operations: ScheduleDraftOperation[];
  issues: string[];
  unplaced_details?: UnplacedDetail[];
  quality?: ValidationQuality | null;
};

export type ScheduleQualityAnalytics = {
  issue_count: number;
  quality: ValidationQuality;
  breakdown?: Record<string, number>;
  weighted_breakdown?: Record<string, number>;
};

export type TeacherLoadMatrixRow = {
  teacher_id: number;
  teacher_name: string;
  by_day: Record<string, number>;
};

export type DayCongestionAnalytics = {
  by_day_slot: Record<string, Record<string, number>>;
};

export type ClassFatigueAlert = {
  class_id: number;
  class_name: string;
  day_of_week: number;
  subject_id: number;
};

export type ClassSubjectHours = {
  id: number;
  school_id: number;
  class_id: number;
  subject_id: number;
  hours_per_week: number;
};

export type SlotSuggestion = {
  lesson_slot_id: number;
  classroom_id: number;
  penalty: number;
};

export type UnplacedSubject = {
  subject_id: number;
  subject_name: string;
  hours_missing: number;
  blocking_issues?: string[];
};

export type SchedulePlanSummary = {
  plan_row_count: number;
  total_planned_hours: number;
  total_scheduled_hours: number;
  rows_under: number;
  rows_over: number;
  rows_exact: number;
  classes_without_plan_count: number;
  fill_rate: number;
};

export type PlanRowCoverage = {
  plan_id: number;
  class_id: number;
  subject_id: number;
  class_name: string;
  subject_name: string;
  planned_hours: number;
  scheduled_hours: number;
  delta: number;
  under: boolean;
  over: boolean;
};

export type ClassWithoutPlan = {
  class_id: number;
  class_name: string;
};

export type SchedulePlanStatus = {
  rows: PlanRowCoverage[];
  classes_without_plan: ClassWithoutPlan[];
  summary: SchedulePlanSummary;
};

export type GenerateClassDraftResponse = {
  proposals: ScheduleItem[];
  unplaced: UnplacedSubject[];
};

export type ImportMode = "upsert" | "replace" | "append" | "skip";

export type ImportIssue = {
  sheet: string;
  row?: number | null;
  column?: string | null;
  severity: "error" | "warning";
  code: string;
  message: string;
};

export type ImportSheetStats = {
  sheet: string;
  rows_total: number;
  rows_to_create: number;
  rows_to_update: number;
  rows_to_replace: number;
  rows_to_skip: number;
  rows_with_errors: number;
  default_mode: ImportMode;
  allowed_modes: ImportMode[];
};

export type ImportSummary = {
  school_id: number;
  error_count: number;
  warning_count: number;
  sheets: ImportSheetStats[];
};

export type ValidateImportResponse = {
  school_id: number;
  summary: ImportSummary;
  issues: ImportIssue[];
  can_commit: boolean;
};

export type CommitImportSheetResult = {
  sheet: string;
  mode: ImportMode;
  created: number;
  updated: number;
  deleted: number;
  skipped: number;
};

export type CommitImportResponse = {
  school_id: number;
  applied: CommitImportSheetResult[];
  issues: ImportIssue[];
  committed: boolean;
};

export type ScheduleExportView = "class" | "teacher" | "school";
export type ScheduleExportFormat = "xlsx" | "pdf";

export const api = {
  login: (email: string, password: string) =>
    requestJson<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    }),

  listSchools: () => requestJson<School[]>("/schools"),
  patchSchool: (schoolId: number, payload: { scheduling_preferences?: Record<string, unknown> | null }) =>
    requestJson<School>(`/schools/${schoolId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  listSubjects: () => requestJson<Subject[]>("/subjects"),
  listLessonSlots: () => requestJson<LessonSlot[]>("/lesson-slots"),

  listTeachers: (schoolId: number) => requestJson<Teacher[]>(`/teachers?school_id=${schoolId}`),
  createTeacher: (payload: Omit<Teacher, "id">) =>
    requestJson<Teacher>("/teachers", { method: "POST", body: JSON.stringify(payload) }),
  updateTeacher: (id: number, payload: Omit<Teacher, "id">) =>
    requestJson<Teacher>(`/teachers/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTeacher: (id: number) => requestVoid(`/teachers/${id}`, { method: "DELETE" }),

  listClassrooms: (schoolId: number) => requestJson<Classroom[]>(`/classrooms?school_id=${schoolId}`),
  createClassroom: (payload: Omit<Classroom, "id">) =>
    requestJson<Classroom>("/classrooms", { method: "POST", body: JSON.stringify(payload) }),
  updateClassroom: (id: number, payload: Omit<Classroom, "id">) =>
    requestJson<Classroom>(`/classrooms/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteClassroom: (id: number) => requestVoid(`/classrooms/${id}`, { method: "DELETE" }),

  listClasses: (schoolId: number) => requestJson<StudentClass[]>(`/classes?school_id=${schoolId}`),
  createClass: (payload: Omit<StudentClass, "id">) =>
    requestJson<StudentClass>("/classes", { method: "POST", body: JSON.stringify(payload) }),
  updateClass: (id: number, payload: Omit<StudentClass, "id">) =>
    requestJson<StudentClass>(`/classes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteClass: (id: number) => requestVoid(`/classes/${id}`, { method: "DELETE" }),

  listFlows: (schoolId: number) => requestJson<GroupFlow[]>(`/grouped-flows?school_id=${schoolId}`),
  createFlow: (payload: Omit<GroupFlow, "id">) =>
    requestJson<GroupFlow>("/grouped-flows", { method: "POST", body: JSON.stringify(payload) }),
  updateFlow: (id: number, payload: Omit<GroupFlow, "id">) =>
    requestJson<GroupFlow>(`/grouped-flows/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteFlow: (id: number) => requestVoid(`/grouped-flows/${id}`, { method: "DELETE" }),

  listSchedule: (schoolId: number) => requestJson<ScheduleItem[]>(`/schedule?school_id=${schoolId}`),
  createScheduleItem: (payload: ScheduleItem) =>
    requestJson<ScheduleItem>("/schedule", { method: "POST", body: JSON.stringify(payload) }),
  updateScheduleItem: (id: number, payload: ScheduleItem) =>
    requestJson<ScheduleItem>(`/schedule/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteScheduleItem: (id: number) => requestVoid(`/schedule/${id}`, { method: "DELETE" }),
  applyScheduleDraft: async (operations: ScheduleDraftOperation[]) => {
    let created = 0;
    let updated = 0;
    let deleted = 0;
    for (const operation of operations) {
      if (operation.type === "create") {
        await requestJson<ScheduleItem>("/schedule", { method: "POST", body: JSON.stringify(operation.payload) });
        created += 1;
      } else if (operation.type === "update") {
        await requestJson<ScheduleItem>(`/schedule/${operation.id}`, {
          method: "PATCH",
          body: JSON.stringify(operation.payload)
        });
        updated += 1;
      } else {
        await requestVoid(`/schedule/${operation.id}`, { method: "DELETE" });
        deleted += 1;
      }
    }
    return { created, updated, deleted, total: operations.length };
  },

  validate: (schoolId: number, candidate?: ScheduleItem) =>
    requestJson<{ status: string; issues: ValidationIssue[]; quality?: ValidationQuality | null }>("/validation", {
      method: "POST",
      body: JSON.stringify({ school_id: schoolId, candidate })
    }),

  listClassSubjectHours: (schoolId: number) =>
    requestJson<ClassSubjectHours[]>(`/class-subject-hours?school_id=${schoolId}`),
  createClassSubjectHours: (payload: Omit<ClassSubjectHours, "id">) =>
    requestJson<ClassSubjectHours>("/class-subject-hours", { method: "POST", body: JSON.stringify(payload) }),
  updateClassSubjectHours: (id: number, payload: Omit<ClassSubjectHours, "id">) =>
    requestJson<ClassSubjectHours>(`/class-subject-hours/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteClassSubjectHours: (id: number) => requestVoid(`/class-subject-hours/${id}`, { method: "DELETE" }),

  schedulePlanStatus: (schoolId: number) =>
    requestJson<SchedulePlanStatus>(`/schedule-plan-status?school_id=${schoolId}`),

  downloadScheduleExport: (
    schoolId: number,
    view: ScheduleExportView,
    format: ScheduleExportFormat,
    entityId?: number
  ) => {
    const params = new URLSearchParams({
      school_id: String(schoolId),
      view,
      format
    });
    if (entityId != null) params.set("entity_id", String(entityId));
    return requestBlob(`/schedule-exports?${params.toString()}`);
  },

  suggestSlots: (schoolId: number, candidate: ScheduleItem, topN = 8) =>
    requestJson<SlotSuggestion[]>("/suggestions/slots", {
      method: "POST",
      body: JSON.stringify({ school_id: schoolId, candidate, top_n: topN })
    }),

  generateClassDraft: (schoolId: number, classId: number) =>
    requestJson<GenerateClassDraftResponse>("/suggestions/generate-class", {
      method: "POST",
      body: JSON.stringify({ school_id: schoolId, class_id: classId })
    }),

  generateTeacherAbsenceDraft: (
    schoolId: number,
    teacherId: number,
    dayOfWeek?: number,
    substituteTeacherId?: number
  ) =>
    requestJson<ScenarioDraftResponse>("/suggestions/scenario-draft", {
      method: "POST",
      body: JSON.stringify({
        school_id: schoolId,
        scenario: "teacher_absent",
        teacher_id: teacherId,
        day_of_week: dayOfWeek ?? null,
        substitute_teacher_id: substituteTeacherId ?? null
      })
    }),

  generateScenarioDraft: (payload: {
    school_id: number;
    scenario: string;
    teacher_id?: number | null;
    day_of_week?: number | null;
    substitute_teacher_id?: number | null;
    original_teacher_id?: number | null;
    max_lesson_number?: number | null;
    classroom_id?: number | null;
    class_id?: number | null;
    lesson_slot_id?: number | null;
  }) =>
    requestJson<ScenarioDraftResponse>("/suggestions/scenario-draft", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  createSolverJob: (payload: SolverJobRequest) =>
    requestJson<{ job_id: string; status: string }>("/solver-jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getSolverJob: (jobId: string) => requestJson<SolverJobStatus>(`/solver-jobs/${jobId}`),
  cancelSolverJob: (jobId: string) =>
    requestJson<SolverJobStatus>(`/solver-jobs/${jobId}/cancel`, { method: "POST" }),

  teacherAnalytics: (schoolId: number) =>
    requestJson<TeacherAnalytics[]>(`/analytics/teachers?school_id=${schoolId}`),
  roomAnalytics: (schoolId: number) =>
    requestJson<RoomAnalytics[]>(`/analytics/rooms?school_id=${schoolId}`),
  scheduleQualityAnalytics: (schoolId: number) =>
    requestJson<ScheduleQualityAnalytics>(`/analytics/schedule-quality?school_id=${schoolId}`),
  teacherLoadMatrix: (schoolId: number) =>
    requestJson<TeacherLoadMatrixRow[]>(`/analytics/teacher-load-matrix?school_id=${schoolId}`),
  dayCongestion: (schoolId: number) =>
    requestJson<DayCongestionAnalytics>(`/analytics/day-congestion?school_id=${schoolId}`),
  classFatigue: (schoolId: number) =>
    requestJson<{ alerts: ClassFatigueAlert[] }>(`/analytics/class-fatigue?school_id=${schoolId}`),

  downloadImportTemplate: (schoolId: number) =>
    requestBlob(`/imports/template?school_id=${schoolId}`),

  validateImport: (schoolId: number, file: File, modes?: Record<string, ImportMode>) => {
    const body = new FormData();
    body.append("school_id", String(schoolId));
    body.append("file", file);
    if (modes) body.append("modes", JSON.stringify(modes));
    return requestMultipart<ValidateImportResponse>("/imports/validate", body);
  },

  commitImport: (schoolId: number, file: File, modes?: Record<string, ImportMode>) => {
    const body = new FormData();
    body.append("school_id", String(schoolId));
    body.append("file", file);
    if (modes) body.append("modes", JSON.stringify(modes));
    return requestMultipart<CommitImportResponse>("/imports/commit", body);
  }
};
