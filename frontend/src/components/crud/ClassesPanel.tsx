"use client";

import { FormEvent, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, hasAuthToken, ScheduleItem, StudentClass } from "@/lib/api";
import { CrudEntityCardShell } from "./CrudEntityCardShell";

type Props = { schoolId: number };

export function ClassesPanel({ schoolId }: Props) {
  const t = useTranslations("crud.classes");
  const [items, setItems] = useState<StudentClass[]>([]);
  const [scheduleItems, setScheduleItems] = useState<ScheduleItem[]>([]);
  const [totalLessonSlots, setTotalLessonSlots] = useState(35);
  const [editing, setEditing] = useState<StudentClass | null>(null);
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
      .listClasses(schoolId)
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
      setTotalLessonSlots(35);
      return;
    }
    void Promise.all([api.listSchedule(schoolId), api.listLessonSlots()])
      .then(([schedule, lessonSlots]) => {
        setScheduleItems(schedule);
        setTotalLessonSlots(lessonSlots.length || 35);
      })
      .catch(() => {
        setScheduleItems([]);
        setTotalLessonSlots(35);
      });
  }, [schoolId, items.length]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const payload = {
      class_name: String(fd.get("class_name")),
      students_count: Number(fd.get("students_count")),
      school_id: schoolId
    };
    setSubmitBusy(true);
    setFeedback(null);
    try {
      if (editing) {
        const updated = await api.updateClass(editing.id, payload);
        setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
        setEditing(null);
        setFeedback({ type: "success", text: t("updated") });
      } else {
        const created = await api.createClass(payload);
        setItems((prev) => [...prev, created]);
        setFeedback({ type: "success", text: t("added") });
        form.reset();
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
        key={`class-form-${editing?.id ?? "new"}`}
        onSubmit={submit}
        className={`crud-form-panel ${submitBusy ? "busy-state" : ""}`}
      >
        <div className="crud-form-grid">
          <input name="class_name" placeholder="11A" required defaultValue={editing?.class_name} />
          <input
            name="students_count"
            type="number"
            placeholder={t("studentsCount")}
            required
            defaultValue={editing?.students_count}
          />
          <div className="crud-form-actions">
            <button type="submit" className="btn-primary focus-ring-strong" disabled={submitBusy}>
              {editing ? t("save") : t("add")}
            </button>
            {editing ? (
              <button type="button" className="btn-secondary focus-ring-strong" onClick={() => setEditing(null)}>
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
            const classLessons = scheduleItems.filter((lesson) => lesson.class_id === item.id);
            const actual = classLessons.length;
            const max = totalLessonSlots;
            const remaining = Math.max(0, max - actual);
            const over = actual > max;
            const percent = Math.min(100, Math.round((actual / Math.max(1, max)) * 100));
            return (
              <CrudEntityCardShell
                key={item.id}
                title={item.class_name}
                meta={t("students", { value: item.students_count })}
                progress={{
                  actual,
                  max,
                  percent,
                  over,
                  caption: t("progressCaption", { actual, max })
                }}
                statEmphasis={t("statHeadline", { value: remaining })}
                status={over ? "bad" : "ok"}
                statusLabel={over ? t("lackSlots", { value: actual - max }) : t("withinWeek")}
                onEdit={() => setEditing(item)}
                onDelete={() => {
                  void (async () => {
                    setDeletingId(item.id);
                    setFeedback(null);
                    try {
                      await api.deleteClass(item.id);
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
