"use client";

import { Fragment, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { DndProvider, useDrag, useDrop } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import {useTranslations} from "next-intl";
import { api, Classroom, hasAuthToken, ScheduleDraftOperation, ScheduleItem, Subject, Teacher, ValidationIssue } from "@/lib/api";
import { filterGroupedJointBookingIssues } from "@/lib/scheduleValidation";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const LESSONS = [1, 2, 3, 4, 5, 6, 7];

type SlotKey = `${number}-${number}`;
type LessonCard = {
  id: string;
  title: string;
  teacherName: string;
  subjectName: string;
  preferredRoom?: string;
  lesson: ScheduleItem;
};
type SaveStatus = "saved" | "dirty" | "saving" | "error";
type ViewMode = "full" | "compact";
type PoolTab = "subjects" | "teachers" | "rooms";
type HistoryEntry = { draftCards: Record<SlotKey, LessonCard> };
type LessonDragItem = LessonCard & { originSlot?: SlotKey };
type CardEditDraft = { subject_id: number; teacher_id: number; classroom_id: number };

function slotToneClass(issues: ValidationIssue[]) {
  if (issues.some((i) => i.severity === "error")) return "slot-tone--error";
  if (issues.some((i) => i.severity === "warning")) return "slot-tone--warn";
  return "slot-tone--ok";
}

function slotKeyToLessonSlotId(slotKey: SlotKey) {
  const [day, lesson] = slotKey.split("-").map(Number);
  return (day - 1) * 7 + lesson;
}

function lessonSlotIdToSlotKey(lessonSlotId?: number | null): SlotKey | null {
  if (!lessonSlotId || lessonSlotId < 1) return null;
  const day = Math.floor((lessonSlotId - 1) / 7) + 1;
  const lesson = ((lessonSlotId - 1) % 7) + 1;
  return `${Math.min(day, 5)}-${lesson}` as SlotKey;
}

function withSlot(card: LessonCard, slotKey: SlotKey): LessonCard {
  return {
    ...card,
    lesson: { ...card.lesson, lesson_slot_id: slotKeyToLessonSlotId(slotKey) }
  };
}

function hydrateCard(lesson: ScheduleItem, subjects: Subject[], teachers: Teacher[], classrooms: Classroom[]): LessonCard {
  const subjectName = subjects.find((s) => s.id === lesson.subject_id)?.name ?? `Subject ${lesson.subject_id}`;
  const teacherName = teachers.find((t) => t.id === lesson.teacher_id)?.full_name ?? `Teacher ${lesson.teacher_id}`;
  const roomName = classrooms.find((r) => r.id === lesson.classroom_id)?.room_number;
  return {
    id: lesson.id ? `item-${lesson.id}` : `draft-${lesson.class_id}-${lesson.lesson_slot_id}-${lesson.subject_id}-${lesson.teacher_id}`,
    title: `${subjectName} · ${teacherName}`,
    teacherName,
    subjectName,
    preferredRoom: roomName,
    lesson
  };
}

function issueKey(issue: ValidationIssue, index: number, slotKey?: SlotKey) {
  const slot = Number(issue.slot_ref?.lesson_slot_id ?? "na");
  return `${slotKey ?? "global"}-${slot}-${issue.issue_code}-${index}`;
}

function issueDedupKey(issue: ValidationIssue) {
  return `${issue.issue_code}|${issue.severity}|${JSON.stringify(issue.slot_ref)}|${JSON.stringify(issue.entity_refs)}`;
}

function issuesBySlotFromList(issues: ValidationIssue[]): Record<SlotKey, ValidationIssue[]> {
  const bySlot: Record<SlotKey, ValidationIssue[]> = {};
  for (const issue of issues) {
    const lid = issue.slot_ref?.lesson_slot_id;
    if (lid == null) continue;
    const n = typeof lid === "number" ? lid : Number(lid);
    if (Number.isNaN(n)) continue;
    const sk = lessonSlotIdToSlotKey(n);
    if (!sk) continue;
    if (!bySlot[sk]) bySlot[sk] = [];
    bySlot[sk].push(issue);
  }
  return bySlot;
}

function refNum(v: unknown): number | null {
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Issues that should paint the timetable for this class only (not other classes' slots). */
function filterIssuesForClassGrid(
  issues: ValidationIssue[],
  classId: number,
  draftBySlot: Record<SlotKey, LessonCard>
): ValidationIssue[] {
  return issues.filter((issue) => issueAppliesToClassGrid(issue, classId, draftBySlot));
}

function issueAppliesToClassGrid(
  issue: ValidationIssue,
  classId: number,
  draftBySlot: Record<SlotKey, LessonCard>
): boolean {
  const refs = issue.entity_refs ?? {};
  const lid = issue.slot_ref?.lesson_slot_id;
  if (lid == null) return false;
  const slotId = refNum(lid);
  if (slotId == null) return false;
  const sk = lessonSlotIdToSlotKey(slotId);
  if (!sk) return false;
  const card = draftBySlot[sk];
  if (!card || card.lesson.class_id !== classId) return false;

  const cid = refNum(refs.class_id);
  if (cid != null && cid !== classId) return false;

  const tid = refNum(refs.teacher_id);
  if (tid != null && tid === card.lesson.teacher_id) return true;
  const rid = refNum(refs.classroom_id);
  if (rid != null && rid === card.lesson.classroom_id) return true;
  const sid = refNum(refs.subject_id);
  if (sid != null && sid === card.lesson.subject_id) return true;
  const gid = refNum(refs.group_id);
  if (gid != null && card.lesson.group_id != null && gid === card.lesson.group_id) return true;

  const hasEntityPin =
    tid != null || rid != null || sid != null || gid != null;
  if (cid === classId && !hasEntityPin) return true;

  return false;
}

/** Errors that should block saving this class's draft (not unrelated school-wide issues). */
function issueBlocksSaveForClass(issue: ValidationIssue, classId: number, draftBySlot: Record<SlotKey, LessonCard>): boolean {
  if (issue.severity !== "error") return false;
  if (issueAppliesToClassGrid(issue, classId, draftBySlot)) return true;
  const cid = refNum(issue.entity_refs?.class_id);
  const lid = issue.slot_ref?.lesson_slot_id;
  const hasSlot = lid != null && !Number.isNaN(Number(lid));
  if (cid === classId && !hasSlot) return true;
  return false;
}

/** Issues to list in the bottom panel when scoped to the class being edited (not unrelated classes' plan rows). */
function issueRelevantToConflictPanel(
  issue: ValidationIssue,
  classId: number,
  draftBySlot: Record<SlotKey, LessonCard>
): boolean {
  if (issueAppliesToClassGrid(issue, classId, draftBySlot)) return true;
  const cid = refNum(issue.entity_refs?.class_id);
  if (cid === classId) return true;
  if (cid != null && cid !== classId) return false;

  const cards = Object.values(draftBySlot).filter((c) => c.lesson.class_id === classId);
  if (cards.length === 0) return false;

  const refs = issue.entity_refs ?? {};
  const tid = refNum(refs.teacher_id);
  if (tid != null && cards.some((c) => c.lesson.teacher_id === tid)) return true;
  const rid = refNum(refs.classroom_id);
  if (rid != null && cards.some((c) => c.lesson.classroom_id === rid)) return true;
  const sid = refNum(refs.subject_id);
  if (sid != null && cards.some((c) => c.lesson.subject_id === sid)) return true;
  const gid = refNum(refs.group_id);
  if (gid != null && cards.some((c) => c.lesson.group_id != null && c.lesson.group_id === gid)) return true;

  return false;
}

function issueTargetClassId(issue: ValidationIssue): number | null {
  return refNum(issue.entity_refs?.class_id);
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

type SandboxSnapshot = {
  name: string;
  savedAt: string;
  cards: Record<SlotKey, LessonCard>;
  penalty: number;
};

function formatSolverBreakdown(
  operations: ScheduleDraftOperation[],
  classNameById: Record<number, string>
): string {
  const counts: Record<number, number> = {};
  for (const op of operations) {
    if (op.type === "create" && op.payload) {
      counts[op.payload.class_id] = (counts[op.payload.class_id] ?? 0) + 1;
    } else if (op.type === "update" && op.payload) {
      counts[op.payload.class_id] = (counts[op.payload.class_id] ?? 0) + 1;
    }
  }
  return Object.entries(counts)
    .map(([id, n]) => `${classNameById[Number(id)] ?? id}: +${n}`)
    .join(", ");
}

function sameLesson(a: ScheduleItem, b: ScheduleItem) {
  return (
    a.class_id === b.class_id &&
    a.subject_id === b.subject_id &&
    a.teacher_id === b.teacher_id &&
    a.classroom_id === b.classroom_id &&
    a.lesson_slot_id === b.lesson_slot_id &&
    a.group_id === b.group_id &&
    a.is_grouped === b.is_grouped &&
    a.school_id === b.school_id
  );
}

function makePool(
  subjects: Subject[],
  teachers: Teacher[],
  classrooms: Classroom[],
  schoolId: number,
  selectedClassId: number
) {
  const pool: LessonCard[] = [];
  for (const teacher of teachers) {
    const teacherSubjects = new Set(teacher.subjects ?? []);
    const matchingSubjects = subjects.filter((subject) => teacherSubjects.has(subject.name));
    for (const subject of matchingSubjects) {
      const preferredClassroom =
        classrooms.find((room) => !subject.requires_special_room || room.specialization === subject.required_specialization) ??
        classrooms[0];
      if (!preferredClassroom) continue;
      pool.push({
        id: `pool-${selectedClassId}-${teacher.id}-${subject.id}-${preferredClassroom.id}`,
        title: `${subject.name} · ${teacher.full_name}`,
        teacherName: teacher.full_name,
        subjectName: subject.name,
        preferredRoom: preferredClassroom.room_number,
        lesson: {
          class_id: selectedClassId,
          subject_id: subject.id,
          teacher_id: teacher.id,
          classroom_id: preferredClassroom.id,
          lesson_slot_id: 1,
          is_grouped: false,
          group_id: null,
          school_id: schoolId
        }
      });
    }
  }
  return pool;
}

function DraggableCard({
  card,
  onRemove,
  onQuickMove,
  onEdit,
  originSlot,
  compact = false
}: {
  card: LessonCard;
  onRemove?: () => void;
  onQuickMove?: () => void;
  onEdit?: () => void;
  originSlot?: SlotKey;
  compact?: boolean;
}) {
  const t = useTranslations("schedule");
  const [{ isDragging }, drag] = useDrag(() => ({
    type: "lesson",
    item: { ...card, originSlot } as LessonDragItem,
    collect: (monitor) => ({ isDragging: monitor.isDragging() })
  }));
  return (
    <div
      ref={(node) => {
        drag(node);
      }}
      className={`interactive-card draggable-card cursor-move ${isDragging ? "opacity-50 is-dragging" : "opacity-100"}`}
      tabIndex={0}
    >
      <div className={`lesson-tile ${compact ? "lesson-tile-compact" : ""}`}>
        <div className="lesson-tile-content">
          <div className="lesson-main">
            <p className="drag-handle" aria-label="Drag handle">
              :: drag
            </p>
            <p className="lesson-title">{card.subjectName}</p>
            <p className="lesson-meta">{card.teacherName}</p>
            <p className="lesson-meta">{card.preferredRoom ? `Room ${card.preferredRoom}` : `Room #${card.lesson.classroom_id}`}</p>
          </div>
          <div className={`action-cluster ${compact ? "action-cluster-compact" : ""}`}>
            {onQuickMove ? (
              <button
                type="button"
                className={`btn-schedule-ghost focus-ring-strong ${compact ? "card-action-btn" : ""}`}
                onClick={onQuickMove}
                aria-label="quick-move-lesson"
              >
                {compact ? t("moveShort") : t("quickMove")}
              </button>
            ) : null}
            {onEdit ? (
              <button
                type="button"
                className={`btn-schedule-ghost focus-ring-strong ${compact ? "card-action-btn" : ""}`}
                onClick={onEdit}
                aria-label="edit-lesson"
              >
                {t("edit")}
              </button>
            ) : null}
            {onRemove ? (
              <button
                type="button"
                className={`btn-danger focus-ring-strong ${compact ? "card-action-btn" : ""}`}
                onClick={onRemove}
                aria-label="remove-lesson"
              >
                {compact ? t("clear") : t("remove")}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function getSummary(cards: Record<SlotKey, LessonCard>, issues: ValidationIssue[]) {
  const lessons = Object.keys(cards).length;
  const warnings = issues.filter((i) => i.severity === "warning").length;
  const conflicts = issues.filter((i) => i.severity === "error").length;
  const windows = Math.max(0, Math.floor(lessons / 7) - 1);
  return { lessons, warnings, conflicts, windows };
}

function DetailPanel({
  card,
  issueCount,
  frozen,
  onToggleFrozen
}: {
  card?: LessonCard;
  issueCount: number;
  frozen?: boolean;
  onToggleFrozen?: () => void;
}) {
  const t = useTranslations("schedule");
  return (
    <aside className="reference-panel schedule-detail-compact">
      <div className="reference-panel-header">
        <strong className="text-sm">{t("lessonInfo")}</strong>
        <span className="info-badge info-badge--neutral">{t("lesson")}</span>
      </div>
      <div className="reference-panel-body space-y-3 text-sm text-slate-700">
        {card ? (
          <>
            {onToggleFrozen ? (
              <button
                type="button"
                className={`btn-schedule-ghost focus-ring-strong ${frozen ? "info-badge--warn" : ""}`}
                onClick={onToggleFrozen}
                data-testid="toggle-frozen-slot"
              >
                {frozen ? t("frozenOn") : t("frozenOff")}
              </button>
            ) : null}
            <div>
              <p className="text-xs text-slate-500">{t("subject")}</p>
              <p className="font-semibold">{card.subjectName}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">{t("teacher")}</p>
              <p>{card.teacherName}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">{t("classroom")}</p>
              <p>{card.preferredRoom ? `Room ${card.preferredRoom}` : `#${card.lesson.classroom_id}`}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">{t("classOrFlow")}</p>
              <p>{card.lesson.class_id}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">{t("status")}</p>
              <span className={`info-badge ${issueCount > 0 ? "info-badge--warn" : "info-badge--ok"}`}>
                {issueCount > 0 ? t("hasRemarks") : t("validState")}
              </span>
            </div>
          </>
        ) : (
          <p className="empty-note">{t("pickLessonCard")}</p>
        )}
      </div>
    </aside>
  );
}

function Slot({
  slotKey,
  card,
  issues,
  onDrop,
  onRemoveCard,
  onQuickMoveCard,
  onSelect,
  selected,
  isDirty,
  dragLocked,
  slotRef,
  quickPickEnabled,
  quickPickOpen,
  quickPickCardId,
  quickPickOptions,
  onQuickPickChange,
  onQuickPickApply,
  onQuickPickClose,
  onOpenCardEdit,
  cardEditOpen,
  cardEditDraft,
  subjects,
  teachers,
  classrooms,
  onCardEditDraftChange,
  onCardEditApply,
  onCardEditClose
}: {
  slotKey: SlotKey;
  card?: LessonCard;
  issues: ValidationIssue[];
  onDrop: (slotKey: SlotKey, card: LessonDragItem) => void;
  onRemoveCard: (slotKey: SlotKey) => void;
  onQuickMoveCard: (slotKey: SlotKey) => void;
  onSelect: () => void;
  selected: boolean;
  isDirty: boolean;
  dragLocked: boolean;
  slotRef: (node: HTMLDivElement | null) => void;
  quickPickEnabled: boolean;
  quickPickOpen: boolean;
  quickPickCardId: string;
  quickPickOptions: LessonCard[];
  onQuickPickChange: (value: string) => void;
  onQuickPickApply: () => void;
  onQuickPickClose: () => void;
  onOpenCardEdit: () => void;
  cardEditOpen: boolean;
  cardEditDraft: CardEditDraft | null;
  subjects: Subject[];
  teachers: Teacher[];
  classrooms: Classroom[];
  onCardEditDraftChange: (draft: CardEditDraft) => void;
  onCardEditApply: () => void;
  onCardEditClose: () => void;
}) {
  const t = useTranslations("schedule");
  const [{ isOver, canDrop }, drop] = useDrop(() => ({
    accept: "lesson",
    canDrop: (item: LessonDragItem) => !dragLocked && item.originSlot !== slotKey,
    drop: (item: LessonDragItem) => onDrop(slotKey, item),
    collect: (monitor) => ({
      isOver: monitor.isOver(),
      canDrop: monitor.canDrop()
    })
  }));
  return (
    <div
      ref={(node) => {
        drop(node);
        slotRef(node);
      }}
      className={`lesson-tile slot-tile ${slotToneClass(issues)} ${canDrop && !isOver ? "is-drop-ready" : ""} ${isOver && canDrop ? "is-drop-active" : ""} ${isOver && !canDrop ? "is-drop-forbidden" : ""} ${selected ? "slot-selected" : ""} ${isDirty ? "dirty-slot" : ""}`}
      tabIndex={0}
      aria-label={`slot-${slotKey}`}
      onClick={() => onSelect()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
    >
      {card ? (
        <DraggableCard
          card={card}
          onRemove={() => onRemoveCard(slotKey)}
          onQuickMove={() => onQuickMoveCard(slotKey)}
          onEdit={onOpenCardEdit}
          originSlot={slotKey}
          compact
        />
      ) : (
        <div>
          <p className="lesson-title">Окно</p>
          <p className="lesson-meta">{t("dropLesson")}</p>
        </div>
      )}
      {issues.map((issue, index) => (
        <div key={issueKey(issue, index, slotKey)}>
          <p className="lesson-meta text-red-700">{issue.message}</p>
        </div>
      ))}
      {quickPickEnabled && quickPickOpen ? (
        <div className="quick-pick-popover" onClick={(event) => event.stopPropagation()}>
          <select
            value={quickPickCardId}
            onChange={(event) => onQuickPickChange(event.target.value)}
            className="focus-ring-strong"
            aria-label={`quick-lesson-picker-${slotKey}`}
          >
            <option value="">{t("pickLesson")}</option>
            {quickPickOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.subjectName} · {option.teacherName}
              </option>
            ))}
          </select>
          <div className="quick-pick-actions">
            <button type="button" className="btn-primary focus-ring-strong" onClick={onQuickPickApply} disabled={!quickPickCardId}>
              OK
            </button>
            <button type="button" className="btn-secondary focus-ring-strong" onClick={onQuickPickClose}>
              ✕
            </button>
          </div>
        </div>
      ) : null}
      {cardEditOpen && cardEditDraft ? (
        <div className="quick-pick-popover card-edit-popover" onClick={(event) => event.stopPropagation()}>
          <select
            value={cardEditDraft.subject_id}
            onChange={(event) =>
              onCardEditDraftChange({ ...cardEditDraft, subject_id: Number(event.target.value) })
            }
            className="focus-ring-strong"
            aria-label={`edit-subject-${slotKey}`}
          >
            {subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))}
          </select>
          <select
            value={cardEditDraft.teacher_id}
            onChange={(event) =>
              onCardEditDraftChange({ ...cardEditDraft, teacher_id: Number(event.target.value) })
            }
            className="focus-ring-strong"
            aria-label={`edit-teacher-${slotKey}`}
          >
            {teachers.map((teacher) => (
              <option key={teacher.id} value={teacher.id}>
                {teacher.full_name}
              </option>
            ))}
          </select>
          <select
            value={cardEditDraft.classroom_id}
            onChange={(event) =>
              onCardEditDraftChange({ ...cardEditDraft, classroom_id: Number(event.target.value) })
            }
            className="focus-ring-strong"
            aria-label={`edit-classroom-${slotKey}`}
          >
            {classrooms.map((room) => (
              <option key={room.id} value={room.id}>
                Room {room.room_number}
              </option>
            ))}
          </select>
          <div className="quick-pick-actions">
            <button type="button" className="btn-primary focus-ring-strong" onClick={onCardEditApply}>
              {t("save")}
            </button>
            <button type="button" className="btn-secondary focus-ring-strong" onClick={onCardEditClose}>
              ✕
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function ScheduleBuilder({
  schoolId,
  selectedClassId,
  selectedClassLabel,
  onDirtyChange,
  filterSlot,
  schoolLabel,
  classNameById,
  pendingSlotFocus,
  onPendingSlotFocusConsumed,
  onNavigateToClassAndSlot
}: {
  schoolId: number;
  selectedClassId: number;
  selectedClassLabel: string;
  onDirtyChange?: (dirty: boolean) => void;
  filterSlot: ReactNode;
  schoolLabel: string;
  classNameById: Record<number, string>;
  pendingSlotFocus?: string | null;
  onPendingSlotFocusConsumed?: () => void;
  onNavigateToClassAndSlot?: (classId: number, slotKey: SlotKey) => void;
}) {
  const t = useTranslations("schedule");
  const [serverSnapshot, setServerSnapshot] = useState<Record<SlotKey, LessonCard>>({});
  const [draftCards, setDraftCards] = useState<Record<SlotKey, LessonCard>>({});
  const [basePool, setBasePool] = useState<LessonCard[]>([]);
  const [subjectFilters, setSubjectFilters] = useState<Set<string>>(new Set());
  const [allIssues, setAllIssues] = useState<ValidationIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<SlotKey | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("saved");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("full");
  const [poolTab, setPoolTab] = useState<PoolTab>("subjects");
  const [quickPickCardId, setQuickPickCardId] = useState<string>("");
  const [editingSlot, setEditingSlot] = useState<SlotKey | null>(null);
  const [cardEditDraft, setCardEditDraft] = useState<CardEditDraft | null>(null);
  const [subjectsCatalog, setSubjectsCatalog] = useState<Subject[]>([]);
  const [teachersCatalog, setTeachersCatalog] = useState<Teacher[]>([]);
  const [classroomsCatalog, setClassroomsCatalog] = useState<Classroom[]>([]);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [fillFromPlanLoading, setFillFromPlanLoading] = useState(false);
  const [showWholeSchoolIssues, setShowWholeSchoolIssues] = useState(false);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [solverRunning, setSolverRunning] = useState(false);
  const [solverScope, setSolverScope] = useState<"class" | "school">("class");
  const [solverPollHint, setSolverPollHint] = useState<string | null>(null);
  const [schoolSolverDraftOnly, setSchoolSolverDraftOnly] = useState(true);
  const frozenStorageKey = `atlas_frozen_slots_${schoolId}_${selectedClassId}`;
  const [frozenLessonSlotIds, setFrozenLessonSlotIds] = useState<number[]>([]);
  const sandboxStorageKey = `atlas_sandbox_${schoolId}`;
  const [sandboxSnapshots, setSandboxSnapshots] = useState<SandboxSnapshot[]>([]);
  const [sandboxComparePenalty, setSandboxComparePenalty] = useState<number | null>(null);
  const slotRefs = useRef<Partial<Record<SlotKey, HTMLDivElement | null>>>({});

  useEffect(() => {
    setShowWholeSchoolIssues(false);
  }, [selectedClassId]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(frozenStorageKey);
      setFrozenLessonSlotIds(raw ? (JSON.parse(raw) as number[]) : []);
    } catch {
      setFrozenLessonSlotIds([]);
    }
  }, [frozenStorageKey]);

  useEffect(() => {
    localStorage.setItem(frozenStorageKey, JSON.stringify(frozenLessonSlotIds));
  }, [frozenStorageKey, frozenLessonSlotIds]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(sandboxStorageKey);
      setSandboxSnapshots(raw ? (JSON.parse(raw) as SandboxSnapshot[]) : []);
    } catch {
      setSandboxSnapshots([]);
    }
  }, [sandboxStorageKey]);
  const subjectOptions = useMemo(
    () => Array.from(new Set(basePool.map((card) => card.subjectName))).sort((a, b) => a.localeCompare(b)),
    [basePool]
  );
  const poolByTeacher = useMemo(() => {
    const m = new Map<string, LessonCard[]>();
    for (const card of basePool) {
      const key = card.teacherName;
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(card);
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [basePool]);
  const poolByRoom = useMemo(() => {
    const m = new Map<string, LessonCard[]>();
    for (const card of basePool) {
      const key =
        card.preferredRoom != null && String(card.preferredRoom).trim() !== ""
          ? String(card.preferredRoom)
          : `#${card.lesson.classroom_id}`;
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(card);
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true }));
  }, [basePool]);
  const visiblePool = useMemo(() => {
    if (subjectFilters.size === 0) return basePool;
    return basePool.filter((card) => subjectFilters.has(card.subjectName));
  }, [basePool, subjectFilters]);

  useEffect(() => {
    if (!hasAuthToken()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    void Promise.all([
      api.listSchedule(schoolId),
      api.listSubjects(),
      api.listTeachers(schoolId),
      api.listClassrooms(schoolId)
    ])
      .then(([items, subjects, teachers, classrooms]) => {
        setSubjectsCatalog(subjects);
        setTeachersCatalog(teachers);
        setClassroomsCatalog(classrooms);
        const next: Record<SlotKey, LessonCard> = {};
        items
          .filter((item) => item.class_id === selectedClassId)
          .forEach((item) => {
          const slot = `${Math.ceil(item.lesson_slot_id / 7)}-${((item.lesson_slot_id - 1) % 7) + 1}` as SlotKey;
          next[slot] = hydrateCard(item, subjects, teachers, classrooms);
        });
        setServerSnapshot(next);
        setDraftCards(next);
        setBasePool(makePool(subjects, teachers, classrooms, schoolId, selectedClassId));
        setSubjectFilters(new Set());
        setHistory([]);
        setSaveStatus("saved");
        setSaveMessage(null);
      })
      .catch(() => {
        setServerSnapshot({});
        setDraftCards({});
        setBasePool([]);
        setSubjectFilters(new Set());
        setError(t("loadError"));
      })
      .finally(() => setLoading(false));
  }, [schoolId, selectedClassId]);

  // Recompute validation for the whole draft (server DB + each lesson as candidate).
  useEffect(() => {
    if (!hasAuthToken() || loading || error) return;

    let cancelled = false;
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const cards = Object.values(draftCards);
          let merged: ValidationIssue[] = [];
          if (cards.length === 0) {
            const v = await api.validate(schoolId);
            merged = v.issues;
          } else {
            const raw: ValidationIssue[] = [];
            for (const card of cards) {
              const v = await api.validate(schoolId, card.lesson);
              raw.push(...v.issues);
            }
            const seen = new Set<string>();
            for (const issue of raw) {
              const k = issueDedupKey(issue);
              if (seen.has(k)) continue;
              seen.add(k);
              merged.push(issue);
            }
            merged = filterGroupedJointBookingIssues(
              merged,
              cards.map((c) => c.lesson)
            );
          }
          if (cancelled) return;
          setAllIssues(merged);
        } catch {
          if (cancelled) return;
        }
      })();
    }, 350);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [draftCards, schoolId, loading, error]);

  useEffect(() => {
    if (!pendingSlotFocus || loading) return;
    const m = /^([1-5])-([1-7])$/.exec(pendingSlotFocus.trim());
    if (!m) {
      onPendingSlotFocusConsumed?.();
      return;
    }
    const sk = `${Number(m[1])}-${Number(m[2])}` as SlotKey;
    setSelectedSlot(sk);
    requestAnimationFrame(() => {
      slotRefs.current[sk]?.focus();
      onPendingSlotFocusConsumed?.();
    });
  }, [loading, pendingSlotFocus, onPendingSlotFocusConsumed]);

  const issuesBySlotGrid = useMemo(
    () => issuesBySlotFromList(filterIssuesForClassGrid(allIssues, selectedClassId, draftCards)),
    [allIssues, selectedClassId, draftCards]
  );

  const metrics = useMemo(() => {
    const errorsBlockingSave = allIssues.filter((i) => issueBlocksSaveForClass(i, selectedClassId, draftCards)).length;
    const warnings = allIssues.filter((i) => i.severity === "warning").length;
    const validSlots = DAYS.length * LESSONS.length - Object.keys(issuesBySlotGrid).length;
    return { errorsBlockingSave, warnings, validSlots };
  }, [allIssues, selectedClassId, draftCards, issuesBySlotGrid]);

  const panelIssues = useMemo(() => {
    if (showWholeSchoolIssues) return allIssues;
    return allIssues.filter((i) => issueRelevantToConflictPanel(i, selectedClassId, draftCards));
  }, [showWholeSchoolIssues, allIssues, selectedClassId, draftCards]);

  const summary = useMemo(() => getSummary(draftCards, allIssues), [draftCards, allIssues]);
  const selectedCard = selectedSlot ? draftCards[selectedSlot] : undefined;

  const dirtySlots = useMemo(() => {
    const keys = new Set<SlotKey>([
      ...(Object.keys(serverSnapshot) as SlotKey[]),
      ...(Object.keys(draftCards) as SlotKey[])
    ]);
    return [...keys].filter((key) => {
      const a = serverSnapshot[key];
      const b = draftCards[key];
      if (!a && !b) return false;
      if (!a || !b) return true;
      if ((a.lesson.id ?? null) !== (b.lesson.id ?? null)) return true;
      return !sameLesson(a.lesson, b.lesson);
    });
  }, [draftCards, serverSnapshot]);

  const isDirty = dirtySlots.length > 0;
  const saveDisabledReason =
    saveStatus === "saving"
      ? t("saving")
      : !isDirty
        ? t("noUnsaved")
        : metrics.errorsBlockingSave > 0
          ? t("hasValidationErrors")
          : null;
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  useEffect(() => {
    if (saveStatus !== "saving") {
      setSaveStatus(isDirty ? "dirty" : "saved");
    }
  }, [isDirty, saveStatus]);

  async function handleDrop(slotKey: SlotKey, dragCard: LessonDragItem) {
    const normalizedCard: LessonDragItem = {
      ...dragCard,
      lesson: { ...dragCard.lesson, class_id: selectedClassId, school_id: schoolId }
    };
    const candidate = withSlot(normalizedCard, slotKey);
    try {
      await api.validate(schoolId, candidate.lesson);
    } catch {
      setSaveMessage(t("dropValidateFailed"));
      return;
    }
    setHistory((prev) => [...prev.slice(-19), { draftCards }]);
    setDraftCards((prev) => {
      const next = { ...prev };
      if (dragCard.originSlot) delete next[dragCard.originSlot];
      next[slotKey] = candidate;
      return next;
    });
    setSelectedSlot(slotKey);
    if (editingSlot === slotKey) setEditingSlot(null);
    requestAnimationFrame(() => slotRefs.current[slotKey]?.focus());
  }

  function handleRemoveCard(slotKey: SlotKey) {
    setHistory((prev) => [...prev.slice(-19), { draftCards }]);
    setDraftCards((prev) => {
      const next = { ...prev };
      delete next[slotKey];
      return next;
    });
    if (selectedSlot === slotKey) setSelectedSlot(null);
    if (editingSlot === slotKey) setEditingSlot(null);
  }

  async function applyDraftChanges() {
    setSaveStatus("saving");
    setSaveMessage(null);
    try {
      const snapshotById = new Map<number, LessonCard>();
      Object.values(serverSnapshot).forEach((card) => {
        if (card.lesson.id) snapshotById.set(card.lesson.id, card);
      });
      const draftById = new Map<number, LessonCard>();
      Object.values(draftCards).forEach((card) => {
        if (card.lesson.id) draftById.set(card.lesson.id, card);
      });

      const operations: ScheduleDraftOperation[] = [];
      for (const [id] of snapshotById) {
        if (!draftById.has(id)) operations.push({ type: "delete", id });
      }
      for (const [id, draftCard] of draftById) {
        const snap = snapshotById.get(id);
        if (!snap) continue;
        if (!sameLesson(snap.lesson, draftCard.lesson)) {
          operations.push({ type: "update", id, payload: { ...draftCard.lesson, id: undefined } });
        }
      }
      for (const draftCard of Object.values(draftCards)) {
        if (!draftCard.lesson.id) operations.push({ type: "create", payload: draftCard.lesson });
      }
      const result = await api.applyScheduleDraft(operations);

      const [items, subjects, teachers, classrooms] = await Promise.all([
        api.listSchedule(schoolId),
        api.listSubjects(),
        api.listTeachers(schoolId),
        api.listClassrooms(schoolId)
      ]);
      setSubjectsCatalog(subjects);
      setTeachersCatalog(teachers);
      setClassroomsCatalog(classrooms);
      const refreshed: Record<SlotKey, LessonCard> = {};
      items
        .filter((item) => item.class_id === selectedClassId)
        .forEach((item) => {
        const slot = `${Math.ceil(item.lesson_slot_id / 7)}-${((item.lesson_slot_id - 1) % 7) + 1}` as SlotKey;
        refreshed[slot] = hydrateCard(item, subjects, teachers, classrooms);
      });
      setServerSnapshot(refreshed);
      setDraftCards(refreshed);
      setSaveStatus("saved");
      setSaveMessage(t("savedDiff", {created: result.created, updated: result.updated, deleted: result.deleted}));
      setEditingSlot(null);
    } catch {
      setSaveStatus("error");
      setSaveMessage(t("saveFailedDraftPreserved"));
    }
  }

  function resetDraft() {
    setHistory((prev) => [...prev.slice(-19), { draftCards }]);
    setDraftCards(serverSnapshot);
    setSelectedSlot(null);
    setEditingSlot(null);
    setCardEditDraft(null);
    setSaveStatus("saved");
    setSaveMessage(t("restored"));
  }

  function quickMoveFromSlot(originSlot: SlotKey) {
    const card = draftCards[originSlot];
    if (!card) return;
    const [day, lesson] = originSlot.split("-").map(Number);
    const nextLesson = lesson < 7 ? lesson + 1 : 1;
    const nextDay = lesson < 7 ? day : Math.min(day + 1, 5);
    const target = `${nextDay}-${nextLesson}` as SlotKey;
    void handleDrop(target, { ...card, originSlot });
  }

  function quickMoveSelected() {
    if (!selectedSlot) return;
    quickMoveFromSlot(selectedSlot);
  }

  function applyQuickPick() {
    if (!selectedSlot || !quickPickCardId) return;
    const card = visiblePool.find((item) => item.id === quickPickCardId);
    if (!card) return;
    void handleDrop(selectedSlot, card);
    setQuickPickCardId("");
  }

  async function applyCardEdit() {
    if (!editingSlot || !cardEditDraft) return;
    const existing = draftCards[editingSlot];
    if (!existing) return;
    const candidateLesson: ScheduleItem = {
      ...existing.lesson,
      subject_id: cardEditDraft.subject_id,
      teacher_id: cardEditDraft.teacher_id,
      classroom_id: cardEditDraft.classroom_id
    };
    const candidate = hydrateCard(candidateLesson, subjectsCatalog, teachersCatalog, classroomsCatalog);
    await api.validate(schoolId, candidate.lesson);
    setHistory((prev) => [...prev.slice(-19), { draftCards }]);
    setDraftCards((prev) => ({ ...prev, [editingSlot]: candidate }));
    setSaveMessage(t("cardUpdated"));
    setEditingSlot(null);
  }

  async function applyBestSuggestedSlot() {
    if (!selectedSlot || !draftCards[selectedSlot] || isDirty) return;
    const card = draftCards[selectedSlot];
    setSuggestLoading(true);
    setSaveMessage(null);
    try {
      const suggestions = await api.suggestSlots(schoolId, card.lesson, 8);
      if (suggestions.length === 0) {
        setSaveMessage(t("noSuggestion"));
        return;
      }
      const best = suggestions[0];
      const newLesson: ScheduleItem = {
        ...card.lesson,
        lesson_slot_id: best.lesson_slot_id,
        classroom_id: best.classroom_id
      };
      const moved = hydrateCard(newLesson, subjectsCatalog, teachersCatalog, classroomsCatalog);
      const targetKey = lessonSlotIdToSlotKey(best.lesson_slot_id);
      if (!targetKey) {
        setSaveMessage(t("cannotResolveSlot"));
        return;
      }
      await api.validate(schoolId, moved.lesson);
      setHistory((prev) => [...prev.slice(-19), { draftCards }]);
      setDraftCards((prev) => {
        const next = { ...prev };
        if (selectedSlot !== targetKey) delete next[selectedSlot];
        next[targetKey] = moved;
        return next;
      });
      setSelectedSlot(targetKey);
      setSaveMessage(t("slotSuggested", {penalty: best.penalty.toFixed(0)}));
    } catch {
      setSaveMessage(t("suggestFailed"));
    } finally {
      setSuggestLoading(false);
    }
  }

  async function fillDraftFromCurriculumPlan() {
    if (isDirty) {
      setSaveMessage(t("saveBeforeGenerate"));
      return;
    }
    const ok = window.confirm(
      t("confirmGenerate")
    );
    if (!ok) return;
    setFillFromPlanLoading(true);
    setSaveMessage(null);
    try {
      const res = await api.generateClassDraft(schoolId, selectedClassId);
      let added = 0;
      setHistory((prev) => [...prev.slice(-19), { draftCards }]);
      setDraftCards((prev) => {
        const next = { ...prev };
        for (const p of res.proposals) {
          const slotKey = lessonSlotIdToSlotKey(p.lesson_slot_id);
          if (!slotKey || next[slotKey]) continue;
          next[slotKey] = hydrateCard(p, subjectsCatalog, teachersCatalog, classroomsCatalog);
          added += 1;
        }
        return next;
      });
      const unplacedNote =
        res.unplaced.length > 0
          ? t("generateUnplacedNote", {
              list: res.unplaced
                .map((u) => {
                  const base = `${u.subject_name} (${u.hours_missing})`;
                  const hints = u.blocking_issues?.length
                    ? ` [${u.blocking_issues.join(", ")}]`
                    : "";
                  return base + hints;
                })
                .join(", ")
            })
          : "";
      setSaveMessage(
        t("generateDraftSummary", {
          added: String(added),
          total: String(res.proposals.length),
          unplacedNote
        })
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("401")) {
        setSaveMessage(t("generateAuthExpired"));
      } else if (msg.includes("403")) {
        setSaveMessage(t("generateForbidden"));
      } else {
        setSaveMessage(t("generateFailed"));
      }
    } finally {
      setFillFromPlanLoading(false);
    }
  }

  function applyOperationsLocally(operations: ScheduleDraftOperation[], opts?: { onlyClassId?: number | null }) {
    const only = opts?.onlyClassId;
    setHistory((prev) => [...prev.slice(-19), { draftCards }]);
    setDraftCards((prev) => {
      const next = { ...prev };
      const byId = new Map<number, SlotKey>();
      for (const [slot, card] of Object.entries(prev) as [SlotKey, LessonCard][]) {
        if (card.lesson.id != null) byId.set(card.lesson.id, slot);
      }
      for (const operation of operations) {
        if (operation.type === "create" && operation.payload) {
          if (only != null && operation.payload.class_id !== only) continue;
          const slotKey = lessonSlotIdToSlotKey(operation.payload.lesson_slot_id);
          if (!slotKey || next[slotKey]) continue;
          next[slotKey] = hydrateCard(operation.payload, subjectsCatalog, teachersCatalog, classroomsCatalog);
          continue;
        }
        if (operation.type === "delete") {
          const slot = byId.get(operation.id);
          if (!slot) continue;
          if (only != null && prev[slot] && prev[slot].lesson.class_id !== only) continue;
          delete next[slot];
          continue;
        }
        if (operation.type === "update" && operation.payload) {
          const slot = byId.get(operation.id);
          if (!slot) continue;
          if (only != null && operation.payload.class_id !== only) continue;
          const payload = operation.payload;
          const updated = hydrateCard({ ...payload, id: operation.id }, subjectsCatalog, teachersCatalog, classroomsCatalog);
          const target = lessonSlotIdToSlotKey(payload.lesson_slot_id) ?? slot;
          if (target !== slot) delete next[slot];
          next[target] = updated;
        }
      }
      return next;
    });
  }

  async function runShortenedDayScenario() {
    const dayRaw = window.prompt(t("confirmShortenedDay"), "1");
    if (dayRaw == null) return;
    const maxRaw = window.prompt("Max lesson number?", "4");
    if (maxRaw == null) return;
    const day = Number(dayRaw);
    const maxLesson = Number(maxRaw);
    if (!Number.isFinite(day) || !Number.isFinite(maxLesson)) return;
    setScenarioLoading(true);
    try {
      const res = await api.generateScenarioDraft({
        school_id: schoolId,
        scenario: "shortened_day",
        day_of_week: day,
        max_lesson_number: maxLesson
      });
      applyOperationsLocally(res.operations);
      setSaveMessage(
        res.issues.length
          ? t("scenarioAppliedWithWarnings", { issues: res.issues.join(", ") })
          : t("scenarioApplied")
      );
    } catch {
      setSaveMessage(t("scenarioFailed"));
    } finally {
      setScenarioLoading(false);
    }
  }

  async function runTeacherAbsenceScenario() {
    if (!selectedCard) {
      setSaveMessage(t("pickLessonCard"));
      return;
    }
    const ok = window.confirm(t("confirmTeacherAbsentDraft", { teacher: selectedCard.teacherName }));
    if (!ok) return;
    setScenarioLoading(true);
    setSaveMessage(null);
    try {
      const day = Math.ceil(selectedCard.lesson.lesson_slot_id / 7);
      const res = await api.generateTeacherAbsenceDraft(schoolId, selectedCard.lesson.teacher_id, day);
      applyOperationsLocally(res.operations);
      if (res.issues.length > 0) {
        setSaveMessage(t("scenarioAppliedWithWarnings", { issues: res.issues.join(", ") }));
      } else {
        setSaveMessage(t("scenarioApplied"));
      }
    } catch {
      setSaveMessage(t("scenarioFailed"));
    } finally {
      setScenarioLoading(false);
    }
  }

  async function reloadDraftForSelectedClass() {
    const [items, subjects, teachers, classrooms] = await Promise.all([
      api.listSchedule(schoolId),
      api.listSubjects(),
      api.listTeachers(schoolId),
      api.listClassrooms(schoolId)
    ]);
    const next: Record<SlotKey, LessonCard> = {};
    items
      .filter((item) => item.class_id === selectedClassId)
      .forEach((item) => {
        const slot = `${Math.ceil(item.lesson_slot_id / 7)}-${((item.lesson_slot_id - 1) % 7) + 1}` as SlotKey;
        next[slot] = hydrateCard(item, subjects, teachers, classrooms);
      });
    setServerSnapshot(next);
    setDraftCards(next);
    setSaveStatus("saved");
  }

  function toggleFrozenForSelectedSlot() {
    if (!selectedCard) return;
    const slotId = selectedCard.lesson.lesson_slot_id;
    setFrozenLessonSlotIds((prev) =>
      prev.includes(slotId) ? prev.filter((id) => id !== slotId) : [...prev, slotId]
    );
  }

  function saveSandboxSnapshot() {
    const name = window.prompt(t("sandboxNamePrompt"));
    if (!name?.trim()) return;
    const penalty = allIssues.reduce(
      (sum, issue) => sum + (issue.weight ?? (issue.severity === "error" ? 10 : 1)),
      0
    );
    const snap: SandboxSnapshot = {
      name: name.trim(),
      savedAt: new Date().toISOString(),
      cards: { ...draftCards },
      penalty
    };
    const next = [...sandboxSnapshots.filter((s) => s.name !== snap.name), snap];
    setSandboxSnapshots(next);
    localStorage.setItem(sandboxStorageKey, JSON.stringify(next));
    setSandboxComparePenalty(penalty);
    setSaveMessage(t("sandboxSaved", { name: snap.name, penalty: String(penalty) }));
  }

  function restoreSandboxSnapshot() {
    if (sandboxSnapshots.length === 0) {
      setSaveMessage(t("sandboxEmpty"));
      return;
    }
    const pick = window.prompt(
      t("sandboxRestorePrompt", { names: sandboxSnapshots.map((s) => s.name).join(", ") })
    );
    if (!pick?.trim()) return;
    const snap = sandboxSnapshots.find((s) => s.name === pick.trim());
    if (!snap) {
      setSaveMessage(t("sandboxNotFound"));
      return;
    }
    setHistory((prev) => [...prev.slice(-19), { draftCards }]);
    setDraftCards(snap.cards);
    const currentPenalty = allIssues.reduce(
      (sum, issue) => sum + (issue.weight ?? (issue.severity === "error" ? 10 : 1)),
      0
    );
    setSaveMessage(
      t("sandboxCompare", {
        baseline: String(snap.penalty),
        current: String(currentPenalty)
      })
    );
  }

  async function runSolverDraft(
    strategy: "cp_sat" | "ga_fallback" | "reoptimize" = "cp_sat",
    opts?: { regenerateMode?: "fill_gaps" | "from_plan" }
  ) {
    if (saveStatus === "saving") return;

    const scopeClassId = solverScope === "school" ? null : selectedClassId;
    let planUnder = "?";
    try {
      const plan = await api.schedulePlanStatus(schoolId);
      planUnder = String(plan.summary.rows_under);
    } catch {
      /* plan hint optional */
    }

    if (opts?.regenerateMode === "from_plan") {
      if (!window.confirm(t("confirmRegenerateStep1"))) return;
      if (!window.confirm(t("confirmRegenerateStep2"))) return;
    } else {
      const scopeLabel = solverScope === "school" ? t("scopeSchool") : selectedClassLabel;
      if (!window.confirm(t("confirmSolverRun", { scope: scopeLabel, under: planUnder }))) return;
    }

    setSolverRunning(true);
    setSolverPollHint(null);
    setSaveMessage(null);
    try {
      const created = await api.createSolverJob({
        school_id: schoolId,
        class_id: scopeClassId,
        strategy,
        regenerate_mode: opts?.regenerateMode ?? "fill_gaps",
        frozen_lesson_slot_ids: frozenLessonSlotIds,
        deterministic_seed: 42,
        apply_as_draft: schoolSolverDraftOnly
      });
      let attempts = 0;
      while (attempts < 45) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const status = await api.getSolverJob(created.job_id);
        if (status.status === "queued" || status.status === "running") {
          setSolverPollHint(t("solverProgress", { pct: String(Math.round(status.progress * 100)) }));
        }
        if (status.status === "completed") {
          setSolverPollHint(null);
          const count = status.operations.length;
          const breakdown = formatSolverBreakdown(status.operations, classNameById);
          const qualityNote =
            status.quality != null
              ? t("solverQuality", { penalty: String(Math.round(status.quality.total_penalty)) })
              : "";

          const unplacedNote =
            status.unplaced_details && status.unplaced_details.length > 0
              ? ` ${t("solverUnplacedNote", {
                  list: status.unplaced_details
                    .map((u) => (u.blocking_issues ?? []).join(", ") || String(u.subject_id))
                    .join("; ")
                })}`
              : "";

          if (solverScope === "school") {
            if (count > 0 && schoolSolverDraftOnly) {
              applyOperationsLocally(status.operations);
              setSaveMessage(
                `${t("solverApplied", { strategy: status.strategy, count: String(count) })}${unplacedNote} ${t("solverClassDraftHint")}`
              );
            } else if (count > 0) {
              try {
                const persisted = await api.applyScheduleDraft(status.operations);
                await reloadDraftForSelectedClass();
                setHistory([]);
                setSaveStatus("saved");
                const breakdownNote = breakdown ? ` ${t("solverBreakdown", { breakdown })}` : "";
                setSaveMessage(
                  `${t("solverSchoolSaved", {
                    strategy: status.strategy,
                    count: String(count),
                    created: String(persisted.created),
                    updated: String(persisted.updated)
                  })}${breakdownNote}${qualityNote ? ` ${qualityNote}` : ""}${unplacedNote}`
                );
              } catch {
                setSaveMessage(t("solverPersistFailed"));
              }
            } else {
              if (opts?.regenerateMode === "from_plan") {
                await reloadDraftForSelectedClass();
                setHistory([]);
                setSaveStatus("saved");
              }
              const hintParts = Array.from(new Set(status.issues ?? [])).map((code) => {
                if (code === "NO_CURRICULUM_FOR_CLASS") return t("solverEmptyNoCurriculum");
                if (code === "SOLVER_NO_MISSING_HOURS") return t("solverEmptyNoGaps");
                return code;
              });
              setSaveMessage(
                t("solverAppliedEmpty", { strategy: status.strategy, hint: hintParts.join(" · ") }) + unplacedNote
              );
            }
          } else {
            applyOperationsLocally(status.operations);
            if (count === 0) {
              const hintParts = Array.from(new Set(status.issues ?? [])).map((code) => {
                if (code === "NO_CURRICULUM_FOR_CLASS") return t("solverEmptyNoCurriculum");
                if (code === "SOLVER_NO_MISSING_HOURS") return t("solverEmptyNoGaps");
                return code;
              });
              setSaveMessage(
                t("solverAppliedEmpty", { strategy: status.strategy, hint: hintParts.join(" · ") }) + unplacedNote
              );
            } else {
              const breakdownNote = breakdown ? ` ${t("solverBreakdown", { breakdown })}` : "";
              setSaveMessage(
                `${t("solverApplied", { strategy: status.strategy, count: String(count) })}${breakdownNote}${qualityNote ? ` ${qualityNote}` : ""}${unplacedNote} ${t("solverClassDraftHint")}`
              );
            }
          }
          return;
        }
        if (status.status === "failed" || status.status === "cancelled") {
          setSaveMessage(t("solverFailed", { reason: status.error ?? status.status }));
          return;
        }
        attempts += 1;
      }
      setSaveMessage(t("solverFailed", { reason: "timeout" }));
    } catch {
      setSaveMessage(t("solverFailed", { reason: "network" }));
    } finally {
      setSolverRunning(false);
      setSolverPollHint(null);
    }
  }

  function undoLast() {
    const last = history[history.length - 1];
    if (!last) return;
    setDraftCards(last.draftCards);
    setHistory((prev) => prev.slice(0, -1));
    setSaveMessage(t("undoDone"));
  }

  function toggleSubjectFilter(subjectName: string) {
    setSubjectFilters((prev) => {
      const next = new Set(prev);
      if (next.has(subjectName)) next.delete(subjectName);
      else next.add(subjectName);
      return next;
    });
  }

  async function exportToExcel() {
    try {
      const { utils: xlsxUtils, writeFileXLSX } = await import("xlsx");
      const rows: (string | number)[][] = [[t("lesson"), t("dayMon"), t("dayTue"), t("dayWed"), t("dayThu"), t("dayFri")]];

      for (const lessonNumber of LESSONS) {
        const row: (string | number)[] = [lessonNumber];
        for (let day = 1; day <= DAYS.length; day += 1) {
          const slotKey = `${day}-${lessonNumber}` as SlotKey;
          const card = draftCards[slotKey];
          if (!card) {
            row.push("");
            continue;
          }
          row.push(
            `${card.subjectName}\n${card.teacherName}\n${card.preferredRoom ? `${t("roomShort")} ${card.preferredRoom}` : `${t("roomShort")} #${card.lesson.classroom_id}`}`
          );
        }
        rows.push(row);
      }

      const worksheet = xlsxUtils.aoa_to_sheet(rows);
      worksheet["!cols"] = [{ wch: 8 }, { wch: 28 }, { wch: 28 }, { wch: 28 }, { wch: 28 }, { wch: 28 }];
      const workbook = xlsxUtils.book_new();
      xlsxUtils.book_append_sheet(workbook, worksheet, t("sheetName"));

      const normalizedClass = selectedClassLabel.replace(/[^a-zA-Z0-9_-]+/g, "_");
      const filename = `schedule_${normalizedClass}_${new Date().toISOString().slice(0, 10)}.xlsx`;
      writeFileXLSX(workbook, filename);
      setSaveMessage(t("exported", {filename}));
    } catch {
      setSaveMessage(t("exportFailed"));
    }
  }

  async function exportPersisted(view: "class" | "teacher" | "school", format: "xlsx" | "pdf") {
    try {
      const teacherId = selectedCard?.lesson.teacher_id;
      const entityId = view === "class" ? selectedClassId : view === "teacher" ? teacherId : undefined;
      if (view === "teacher" && entityId == null) {
        setSaveMessage(t("pickLessonCard"));
        return;
      }
      const blob = await api.downloadScheduleExport(schoolId, view, format, entityId);
      const stamp = new Date().toISOString().slice(0, 10);
      const filename = `atlas_schedule_${view}_${stamp}.${format}`;
      saveBlob(blob, filename);
      setSaveMessage(t("exported", { filename }));
    } catch {
      setSaveMessage(t("exportFailed"));
    }
  }

  useEffect(() => {
    function onKeydown(event: KeyboardEvent) {
      const isSave = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s";
      if (isSave) {
        event.preventDefault();
        if (isDirty && saveStatus !== "saving" && metrics.errorsBlockingSave === 0) void applyDraftChanges();
        return;
      }
      if (event.key === "Escape") {
        setSelectedSlot(null);
        setEditingSlot(null);
        return;
      }
      if ((event.key === "Delete" || event.key === "Backspace") && selectedSlot && draftCards[selectedSlot]) {
        event.preventDefault();
        handleRemoveCard(selectedSlot);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        undoLast();
        return;
      }
    }
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, [selectedSlot, draftCards, isDirty, saveStatus, metrics.errorsBlockingSave, history]);

  return (
    <DndProvider backend={HTML5Backend}>
      <section className="schedule-builder space-y-2" data-testid="schedule-builder">
        <div className="schedule-action-bar reference-panel schedule-panel-tight">
          <div className="schedule-action-bar__filters">{filterSlot}</div>
          <div className="schedule-action-bar__actions">
            <span
              className={`info-badge schedule-save-status ${
                saveStatus === "saved"
                  ? "info-badge--ok"
                  : saveStatus === "error"
                    ? "info-badge--error"
                    : "info-badge--warn"
              }`}
            >
              {saveStatus === "saving"
                ? t("saving")
                : saveStatus === "dirty"
                  ? t("unsavedCount", {count: dirtySlots.length})
                  : saveStatus === "error"
                    ? t("saveError")
                    : t("saved")}
            </span>
            {saveDisabledReason && (isDirty || saveStatus === "saving") ? (
              <span className="schedule-hint-text" title={saveDisabledReason ?? undefined}>
                {saveDisabledReason}
              </span>
            ) : null}
            <button
              type="button"
              className={`btn-schedule-primary focus-ring-strong ${!isDirty || saveStatus === "saving" ? "disabled-save" : ""}`}
              disabled={!isDirty || saveStatus === "saving" || metrics.errorsBlockingSave > 0}
              onClick={() => void applyDraftChanges()}
              title={saveDisabledReason ?? t("saveChanges")}
            >
              {t("saveChanges")}
            </button>
            <div className="schedule-action-bar__secondary">
              <button type="button" className="btn-schedule-secondary focus-ring-strong" disabled={history.length === 0} onClick={undoLast}>
                {t("undo")}
              </button>
              <button type="button" className="btn-schedule-secondary focus-ring-strong" onClick={() => void exportToExcel()} disabled={loading}>
                {t("exportExcel")}
              </button>
              <button
                type="button"
                className="btn-schedule-secondary focus-ring-strong"
                onClick={() => void exportPersisted("class", "pdf")}
                disabled={loading}
              >
                {t("exportClassPdf")}
              </button>
              <button
                type="button"
                className="btn-schedule-secondary focus-ring-strong"
                onClick={() => void exportPersisted("teacher", "xlsx")}
                disabled={loading || !selectedCard}
              >
                {t("exportTeacherXlsx")}
              </button>
              <button
                type="button"
                className="btn-schedule-secondary focus-ring-strong"
                onClick={() => void exportPersisted("teacher", "pdf")}
                disabled={loading || !selectedCard}
              >
                {t("exportTeacherPdf")}
              </button>
              <button
                type="button"
                className="btn-schedule-secondary focus-ring-strong"
                onClick={() => void exportPersisted("school", "xlsx")}
                disabled={loading}
              >
                {t("exportSchoolXlsx")}
              </button>
            </div>
          </div>
        </div>

        <div className="schedule-validation-strip" aria-label={t("globalValidation")}>
          <span className="info-badge info-badge--neutral">{schoolLabel}</span>
          <span className="info-badge info-badge--neutral">{t("editing", {selectedClassLabel})}</span>
          <span className={`info-badge ${metrics.errorsBlockingSave > 0 ? "info-badge--error" : "info-badge--ok"}`}>
            {t("errors", {value: metrics.errorsBlockingSave})}
          </span>
          <span className={`info-badge ${metrics.warnings > 0 ? "info-badge--warn" : "info-badge--ok"}`}>
            {t("warnings", {value: metrics.warnings})}
          </span>
          <span className="info-badge info-badge--ok">{t("valid", {value: metrics.validSlots})}</span>
          <span className="schedule-validation-strip__hint">{t("validationHint")}</span>
          <span className="schedule-validation-strip__shortcuts">{t("shortcuts")}</span>
        </div>

        <div className="schedule-ghost-toolbar">
          <div className="schedule-scope-toggle" role="group" aria-label={t("solverScopeLabel")}>
            <label className="schedule-scope-option">
              <input
                type="radio"
                name="solverScope"
                checked={solverScope === "class"}
                onChange={() => setSolverScope("class")}
                data-testid="solver-scope-class"
              />
              {t("scopeClass")}
            </label>
            <label className="schedule-scope-option">
              <input
                type="radio"
                name="solverScope"
                checked={solverScope === "school"}
                onChange={() => setSolverScope("school")}
                data-testid="solver-scope-school"
              />
              {t("scopeSchool")}
            </label>
            {solverScope === "school" ? (
              <label className="schedule-scope-option">
                <input
                  type="checkbox"
                  checked={schoolSolverDraftOnly}
                  onChange={(e) => setSchoolSolverDraftOnly(e.target.checked)}
                  data-testid="school-solver-draft-only"
                />
                {t("schoolSolverDraftOnly")}
              </label>
            ) : null}
          </div>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={!isDirty || saveStatus === "saving"}
            onClick={resetDraft}
          >
            {t("restoreLast")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={!selectedSlot || !draftCards[selectedSlot]}
            onClick={quickMoveSelected}
          >
            {t("quickMove")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={
              !selectedSlot ||
              !draftCards[selectedSlot] ||
              isDirty ||
              suggestLoading ||
              saveStatus === "saving"
            }
            title={isDirty ? t("saveBeforeSuggestions") : t("pickBestSlot")}
            onClick={() => void applyBestSuggestedSlot()}
          >
            {suggestLoading ? "…" : t("pickSlot")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={isDirty || fillFromPlanLoading || saveStatus === "saving"}
            title={isDirty ? t("saveBeforeAutofill") : t("fillByPlanHint")}
            onClick={() => void fillDraftFromCurriculumPlan()}
          >
            {fillFromPlanLoading ? "…" : t("fillByPlan")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={!selectedCard || scenarioLoading || saveStatus === "saving"}
            onClick={() => void runTeacherAbsenceScenario()}
          >
            {scenarioLoading ? "…" : t("teacherAbsentDraft")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={scenarioLoading || saveStatus === "saving"}
            onClick={() => void runShortenedDayScenario()}
            data-testid="scenario-shortened-day"
          >
            {scenarioLoading ? "…" : t("scenarioShortenedDay")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={solverRunning || saveStatus === "saving"}
            title={solverScope === "school" ? t("fillGapsHint") : t("fillByPlanHint")}
            onClick={() => void runSolverDraft("cp_sat")}
            data-testid="solver-cp-sat"
          >
            {solverRunning ? "…" : t("solverDraft")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={solverRunning || saveStatus === "saving"}
            onClick={() => void runSolverDraft("ga_fallback")}
          >
            {solverRunning ? "…" : t("gaDraft")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={solverRunning || saveStatus === "saving"}
            onClick={() => void runSolverDraft("reoptimize")}
            data-testid="solver-reoptimize"
          >
            {solverRunning ? "…" : t("reoptimizeDraft")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={solverRunning || saveStatus === "saving"}
            title={t("fromPlanHint")}
            onClick={() => void runSolverDraft("cp_sat", { regenerateMode: "from_plan" })}
            data-testid="solver-from-plan"
          >
            {solverRunning ? "…" : t("regenerateFromPlan")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={saveStatus === "saving"}
            onClick={saveSandboxSnapshot}
            data-testid="sandbox-save"
          >
            {t("sandboxSave")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            disabled={saveStatus === "saving"}
            onClick={restoreSandboxSnapshot}
            data-testid="sandbox-restore"
          >
            {t("sandboxRestore")}
          </button>
          <button
            type="button"
            className="btn-schedule-ghost focus-ring-strong"
            onClick={() => setViewMode((prev) => (prev === "full" ? "compact" : "full"))}
            aria-label="Toggle full view"
          >
            {viewMode === "full" ? t("compactView") : t("fullView")}
          </button>
        </div>

        {solverPollHint ? <p className="schedule-hint-text">{solverPollHint}</p> : null}
        {sandboxComparePenalty != null ? (
          <p className="schedule-hint-text">{t("sandboxBaseline", { penalty: String(sandboxComparePenalty) })}</p>
        ) : null}
        {saveMessage ? (
          <p className={`inline-feedback ${saveStatus === "error" ? "error" : "success"} schedule-inline-feedback`}>{saveMessage}</p>
        ) : null}

        <div className={`reference-panel schedule-main-wrap schedule-panel-tight ${viewMode === "compact" ? "schedule-layout-compact-host" : ""}`}>
          <div className={`reference-panel-body schedule-layout ${viewMode === "compact" ? "schedule-layout-compact" : ""}`}>
            <div>
              <div className="schedule-grid-heading">
                <strong className="text-sm text-slate-800">{t("gridTitle")}</strong>
                <span className="schedule-grid-sub">{t("gridHint")}</span>
              </div>
              {viewMode === "full" ? (
                <div className="mb-2">
                  <DetailPanel
                    card={selectedCard}
                    issueCount={selectedSlot ? (issuesBySlotGrid[selectedSlot]?.length ?? 0) : 0}
                    frozen={
                      selectedCard ? frozenLessonSlotIds.includes(selectedCard.lesson.lesson_slot_id) : false
                    }
                    onToggleFrozen={selectedCard ? toggleFrozenForSelectedSlot : undefined}
                  />
                </div>
              ) : null}
              {loading ? <p className="empty-note">{t("loading")}</p> : null}
              {error ? <p className="empty-note">{error}</p> : null}
              <div className="schedule-grid-wrap">
                <div className="schedule-grid">
                  <div className="grid-head">№</div>
                  {DAYS.map((d) => (
                    <div key={d} className="grid-head">
                      {d}
                    </div>
                  ))}
                  {LESSONS.map((lessonNumber) => (
                    <Fragment key={`lesson-row-${lessonNumber}`}>
                      <div className="slot-index">
                        <div>{lessonNumber}</div>
                      </div>
                      {DAYS.map((_, dayIdx) => {
                        const slotKey = `${dayIdx + 1}-${lessonNumber}` as SlotKey;
                        return (
                          <Slot
                            key={slotKey}
                            slotKey={slotKey}
                            card={draftCards[slotKey]}
                            issues={issuesBySlotGrid[slotKey] ?? []}
                            onDrop={handleDrop}
                            onRemoveCard={handleRemoveCard}
                            onQuickMoveCard={quickMoveFromSlot}
                            onSelect={() => {
                              setSelectedSlot(slotKey);
                              if (viewMode === "compact") {
                                setQuickPickCardId("");
                              }
                            }}
                            selected={selectedSlot === slotKey}
                            isDirty={dirtySlots.includes(slotKey)}
                            dragLocked={saveStatus === "saving"}
                            slotRef={(node) => {
                              slotRefs.current[slotKey] = node;
                            }}
                            quickPickEnabled={viewMode === "compact"}
                            quickPickOpen={viewMode === "compact" && selectedSlot === slotKey}
                            quickPickCardId={quickPickCardId}
                            quickPickOptions={visiblePool}
                            onQuickPickChange={setQuickPickCardId}
                            onQuickPickApply={() => {
                              if (saveStatus === "saving") return;
                              void applyQuickPick();
                            }}
                            onQuickPickClose={() => {
                              setSelectedSlot(null);
                              setQuickPickCardId("");
                            }}
                            onOpenCardEdit={() => {
                              const existing = draftCards[slotKey];
                              if (!existing) return;
                              setEditingSlot(slotKey);
                              setCardEditDraft({
                                subject_id: existing.lesson.subject_id,
                                teacher_id: existing.lesson.teacher_id,
                                classroom_id: existing.lesson.classroom_id
                              });
                            }}
                            cardEditOpen={editingSlot === slotKey}
                            cardEditDraft={editingSlot === slotKey ? cardEditDraft : null}
                            subjects={subjectsCatalog}
                            teachers={teachersCatalog}
                            classrooms={classroomsCatalog}
                            onCardEditDraftChange={setCardEditDraft}
                            onCardEditApply={() => void applyCardEdit()}
                            onCardEditClose={() => {
                              setEditingSlot(null);
                              setCardEditDraft(null);
                            }}
                          />
                        );
                      })}
                    </Fragment>
                  ))}
                </div>
              </div>
            </div>
            <div className={`reference-panel pool-sidebar schedule-pool-sidebar mb-0 ${viewMode === "compact" ? "schedule-hidden" : ""}`}>
              <div className="reference-panel-header schedule-pool-header">
                <div className="schedule-pool-tabs" role="tablist" aria-label={t("lessonPool")}>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={poolTab === "subjects"}
                    className={`schedule-pool-tab ${poolTab === "subjects" ? "schedule-pool-tab--active" : ""}`}
                    onClick={() => setPoolTab("subjects")}
                  >
                    {t("poolTabSubjects")}
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={poolTab === "teachers"}
                    className={`schedule-pool-tab ${poolTab === "teachers" ? "schedule-pool-tab--active" : ""}`}
                    onClick={() => setPoolTab("teachers")}
                  >
                    {t("poolTabTeachers")}
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={poolTab === "rooms"}
                    className={`schedule-pool-tab ${poolTab === "rooms" ? "schedule-pool-tab--active" : ""}`}
                    onClick={() => setPoolTab("rooms")}
                  >
                    {t("poolTabRooms")}
                  </button>
                </div>
                <span className="info-badge info-badge--neutral schedule-pool-count">
                  {t("cardsCount", {visible: visiblePool.length, total: basePool.length})}
                </span>
              </div>
              {poolTab === "subjects" ? (
                <>
                  <div className="reference-panel-body pool-filters">
                    <div className="pool-filter-actions">
                      <button type="button" className="btn-schedule-ghost focus-ring-strong" onClick={() => setSubjectFilters(new Set())}>
                        {t("reset")}
                      </button>
                      <button
                        type="button"
                        className="btn-schedule-ghost focus-ring-strong"
                        onClick={() => setSubjectFilters(new Set(subjectOptions))}
                        disabled={subjectOptions.length === 0}
                      >
                        {t("selectAll")}
                      </button>
                    </div>
                    <div className="pool-filter-list">
                      {subjectOptions.map((subjectName) => {
                        const active = subjectFilters.has(subjectName);
                        return (
                          <label key={subjectName} className={`pool-filter-chip ${active ? "active" : ""}`}>
                            <input type="checkbox" checked={active} onChange={() => toggleSubjectFilter(subjectName)} />
                            <span>{subjectName}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                  <div className={`reference-panel-body pool-sidebar-cards grid gap-2 ${saveStatus === "saving" ? "saving-state" : ""}`}>
                    {basePool.length === 0 ? <p className="empty-note">{t("poolEmpty")}</p> : null}
                    {basePool.length > 0 && visiblePool.length === 0 ? (
                      <p className="empty-note">{t("noCardsByFilter")}</p>
                    ) : null}
                    {visiblePool.map((card) => (
                      <DraggableCard key={card.id} card={card} />
                    ))}
                  </div>
                </>
              ) : poolTab === "teachers" ? (
                <div className={`reference-panel-body pool-sidebar-cards pool-tab-scroll grid gap-3 ${saveStatus === "saving" ? "saving-state" : ""}`}>
                  {basePool.length === 0 ? <p className="empty-note">{t("poolEmpty")}</p> : null}
                  {poolByTeacher.map(([name, cards]) => (
                    <div key={name} className="pool-group">
                      <p className="pool-group-title">{name}</p>
                      <div className="grid gap-2">
                        {cards.map((card) => (
                          <DraggableCard key={card.id} card={card} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className={`reference-panel-body pool-sidebar-cards pool-tab-scroll grid gap-3 ${saveStatus === "saving" ? "saving-state" : ""}`}>
                  {basePool.length === 0 ? <p className="empty-note">{t("poolEmpty")}</p> : null}
                  {poolByRoom.map(([room, cards]) => (
                    <div key={room} className="pool-group">
                      <p className="pool-group-title">
                        {t("roomShort")} {room}
                      </p>
                      <div className="grid gap-2">
                        {cards.map((card) => (
                          <DraggableCard key={card.id} card={card} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className={`bottom-panels schedule-bottom-panels ${viewMode === "compact" ? "schedule-hidden" : ""}`}>
          <aside className="reference-panel">
            <div className="reference-panel-header flex flex-col gap-1">
              <strong className="text-sm">{t("conflictsAndWarnings")}</strong>
              <p className="text-xs font-normal text-slate-500">{t("conflictsPanelSource")}</p>
              {allIssues.length > 0 ? (
                <label className="flex cursor-pointer items-center gap-2 text-xs font-normal text-slate-600">
                  <input
                    type="checkbox"
                    className="rounded border-slate-300"
                    checked={showWholeSchoolIssues}
                    onChange={(e) => setShowWholeSchoolIssues(e.target.checked)}
                  />
                  {t("conflictsShowWholeSchool", { count: allIssues.length })}
                </label>
              ) : null}
            </div>
            <div className="reference-panel-body schedule-issues-panel-body">
              {allIssues.length === 0 ? (
                <p className="empty-note">{t("checksClean")}</p>
              ) : panelIssues.length === 0 ? (
                <p className="empty-note">{t("conflictsFilteredEmpty")}</p>
              ) : (
                <ul className="schedule-issues-list space-y-2 text-sm text-slate-700">
                  {panelIssues
                    .slice()
                    .sort((a, b) => (a.severity === "error" && b.severity !== "error" ? -1 : 1))
                    .map((issue, index) => {
                      const targetCid = issueTargetClassId(issue);
                      const classLabel = targetCid != null ? classNameById[targetCid] : null;
                      const slot = lessonSlotIdToSlotKey(Number(issue.slot_ref?.lesson_slot_id));
                      return (
                    <li key={issueKey(issue, index)} className="issue-row">
                      <div className="issue-row-main">
                        <span className="issue-message">{issue.message}</span>
                        {classLabel ? (
                          <span className="issue-class-badge">{classLabel}</span>
                        ) : targetCid != null ? (
                          <span className="issue-class-badge">#{targetCid}</span>
                        ) : null}
                      </div>
                      <div className="issue-actions">
                        <button
                          type="button"
                          className="btn-schedule-ghost focus-ring-strong"
                          disabled={!slot}
                          onClick={() => {
                            if (!slot) return;
                            if (targetCid != null && targetCid !== selectedClassId && onNavigateToClassAndSlot) {
                              onNavigateToClassAndSlot(targetCid, slot);
                              return;
                            }
                            setSelectedSlot(slot);
                            requestAnimationFrame(() => slotRefs.current[slot]?.focus());
                          }}
                        >
                          {t("jump")}
                        </button>
                      </div>
                    </li>
                  );
                    })}
                </ul>
              )}
            </div>
          </aside>
          <aside className="reference-panel">
            <div className="reference-panel-header">
              <strong className="text-sm">{t("summary")}</strong>
            </div>
            <div className="reference-panel-body grid grid-cols-2 gap-2 text-sm">
              <div className="section-card">
                <p className="text-xs text-slate-500">{t("lessonsCount")}</p>
                <p className="text-xl font-bold">{summary.lessons}</p>
              </div>
              <div className="section-card">
                <p className="text-xs text-slate-500">{t("windowsCount")}</p>
                <p className="text-xl font-bold">{summary.windows}</p>
              </div>
              <div className="section-card">
                <p className="text-xs text-slate-500">{t("conflictsCount")}</p>
                <p className="text-xl font-bold">{summary.conflicts}</p>
              </div>
              <div className="section-card">
                <p className="text-xs text-slate-500">{t("warningsCount")}</p>
                <p className="text-xl font-bold">{summary.warnings}</p>
              </div>
            </div>
          </aside>
        </div>
      </section>
    </DndProvider>
  );
}
