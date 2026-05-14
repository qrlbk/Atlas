"use client";

import { FormEvent, useEffect, useState } from "react";
import {useTranslations} from "next-intl";
import { api, GroupFlow, hasAuthToken, ScheduleItem, StudentClass } from "@/lib/api";
import { CrudEntityCardShell } from "./CrudEntityCardShell";

type Props = { schoolId: number };

export function FlowsPanel({ schoolId }: Props) {
  const t = useTranslations("crud.flows");
  const [items, setItems] = useState<GroupFlow[]>([]);
  const [scheduleItems, setScheduleItems] = useState<ScheduleItem[]>([]);
  const [availableClasses, setAvailableClasses] = useState<StudentClass[]>([]);
  const [classesMap, setClassesMap] = useState<Record<number, StudentClass>>({});
  const [totalLessonSlots, setTotalLessonSlots] = useState(35);
  const [selectedCombinedClasses, setSelectedCombinedClasses] = useState<number[]>([]);
  const [editing, setEditing] = useState<GroupFlow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitBusy, setSubmitBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (!hasAuthToken()) {
      setItems([]);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    void api
      .listFlows(schoolId)
      .then(setItems)
      .catch(() => {
        setItems([]);
        setError(t("loadError"));
      })
      .finally(() => setLoading(false));
  }, [schoolId, t]);

  useEffect(() => {
    if (!hasAuthToken()) {
      setScheduleItems([]);
      setAvailableClasses([]);
      setClassesMap({});
      setTotalLessonSlots(35);
      return;
    }
    void Promise.all([api.listSchedule(schoolId), api.listClasses(schoolId), api.listLessonSlots()])
      .then(([schedule, classes, lessonSlots]) => {
        setScheduleItems(schedule);
        setAvailableClasses(classes);
        setClassesMap(
          classes.reduce<Record<number, StudentClass>>((acc, item) => {
            acc[item.id] = item;
            return acc;
          }, {})
        );
        setTotalLessonSlots(lessonSlots.length || 35);
      })
      .catch(() => {
        setScheduleItems([]);
        setAvailableClasses([]);
        setClassesMap({});
        setTotalLessonSlots(35);
      });
  }, [schoolId, items.length]);

  useEffect(() => {
    if (editing) {
      setSelectedCombinedClasses(editing.combined_classes);
    } else {
      setSelectedCombinedClasses([]);
    }
  }, [editing]);

  function toggleClass(classId: number) {
    setSelectedCombinedClasses((prev) => {
      if (prev.includes(classId)) return prev.filter((id) => id !== classId);
      return [...prev, classId];
    });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const payload = {
      group_name: String(fd.get("group_name")),
      combined_classes: selectedCombinedClasses,
      school_id: schoolId
    };
    if (payload.combined_classes.length === 0) {
      setFeedback({ type: "error", text: t("selectClass") });
      return;
    }
    setSubmitBusy(true);
    setFeedback(null);
    try {
      if (editing) {
        const updated = await api.updateFlow(editing.id, payload);
        setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
        setEditing(null);
        setFeedback({ type: "success", text: t("updated") });
      } else {
        const created = await api.createFlow(payload);
        setItems((prev) => [...prev, created]);
        setFeedback({ type: "success", text: t("added") });
        form.reset();
        setSelectedCombinedClasses([]);
      }
    } catch {
      setFeedback({ type: "error", text: t("saveError") });
    } finally {
      setSubmitBusy(false);
    }
  }

  return (
    <article className="section-card space-y-3">
      <header className="space-y-1">
        <h2 className="section-title">{t("title")}</h2>
        <p className="section-subtitle">{t("subtitle")}</p>
      </header>
      <form
        key={`flow-form-${editing?.id ?? "new"}`}
        onSubmit={submit}
        className={`crud-form-panel ${submitBusy ? "busy-state" : ""}`}
      >
        <div className="crud-form-grid">
          <input
            name="group_name"
            className="crud-form-span-full"
            placeholder={t("groupName")}
            required
            defaultValue={editing?.group_name}
          />
          <div className="pool-filters crud-form-span-full">
            <p className="text-xs text-slate-500">{t("chooseClasses")}</p>
            <div className="pool-filter-list">
              {availableClasses.map((item) => {
                const active = selectedCombinedClasses.includes(item.id);
                return (
                  <label key={item.id} className={`pool-filter-chip ${active ? "active" : ""}`}>
                    <input type="checkbox" checked={active} onChange={() => toggleClass(item.id)} />
                    <span>{item.class_name}</span>
                  </label>
                );
              })}
            </div>
          </div>
          <div className="crud-form-actions">
            <button type="submit" className="btn-primary focus-ring-strong" disabled={submitBusy}>
              {editing ? t("save") : t("add")}
            </button>
            {editing ? (
              <button
                type="button"
                className="btn-secondary focus-ring-strong"
                onClick={() => {
                  setEditing(null);
                  setSelectedCombinedClasses([]);
                }}
              >
                {t("cancel")}
              </button>
            ) : null}
          </div>
        </div>
      </form>
      {feedback ? <p className={`inline-feedback ${feedback.type}`}>{feedback.text}</p> : null}

      {loading ? <p className="empty-note">{t("loading")}</p> : null}
      {error ? <p className="empty-note">{error}</p> : null}
      {!loading && !error && items.length === 0 ? <p className="empty-note">{t("empty")}</p> : null}

      <div className="saas-grid-host">
        <ul className="entity-card-grid">
          {items.map((item) => {
            const groupedLessons = scheduleItems.filter((lesson) => lesson.is_grouped && lesson.group_id === item.id);
            const lessonsCount = groupedLessons.length;
            const totalStudents = item.combined_classes.reduce(
              (sum, classId) => sum + (classesMap[classId]?.students_count ?? 0),
              0
            );
            const freeSlots = Math.max(0, totalLessonSlots - lessonsCount);
            const percent = Math.min(100, Math.round((lessonsCount / Math.max(1, totalLessonSlots)) * 100));
            const slotOver = lessonsCount > totalLessonSlots;
            return (
              <CrudEntityCardShell
                key={item.id}
                title={item.group_name}
                meta={
                  <>
                    <span>{t("classes", { value: item.combined_classes.length })}</span>
                    <span className="saas-entity-card__meta-muted">{t("studentsTotal", { value: totalStudents })}</span>
                  </>
                }
                progress={{
                  actual: lessonsCount,
                  max: totalLessonSlots,
                  percent,
                  over: slotOver,
                  caption: t("progressCaption", { actual: lessonsCount, max: totalLessonSlots })
                }}
                statEmphasis={t("statHeadline", { value: freeSlots })}
                status={slotOver ? "bad" : "ok"}
                statusLabel={slotOver ? t("slotsOver", { value: lessonsCount - totalLessonSlots }) : t("withinSlots")}
                onEdit={() => setEditing(item)}
                onDelete={() => {
                  void (async () => {
                    setDeletingId(item.id);
                    setFeedback(null);
                    try {
                      await api.deleteFlow(item.id);
                      setItems((prev) => prev.filter((x) => x.id !== item.id));
                      if (editing?.id === item.id) setEditing(null);
                      setFeedback({ type: "success", text: t("deleted") });
                    } catch {
                      setFeedback({ type: "error", text: t("deleteError") });
                    } finally {
                      setDeletingId(null);
                    }
                  })();
                }}
                deleteDisabled={deletingId === item.id}
                editLabel={t("edit")}
                deleteLabel={t("delete")}
                busy={deletingId === item.id}
              />
            );
          })}
        </ul>
      </div>
    </article>
  );
}
