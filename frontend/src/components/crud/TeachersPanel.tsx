"use client";

import { FormEvent, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, hasAuthToken, Teacher, TeacherAnalytics } from "@/lib/api";
import { CrudEntityCardShell } from "./CrudEntityCardShell";

type Props = { schoolId: number };

export function TeachersPanel({ schoolId }: Props) {
  const t = useTranslations("crud.teachers");
  const [items, setItems] = useState<Teacher[]>([]);
  const [teacherStats, setTeacherStats] = useState<Record<number, TeacherAnalytics>>({});
  const [editing, setEditing] = useState<Teacher | null>(null);
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
      .listTeachers(schoolId)
      .then(setItems)
      .catch(() => {
        setItems([]);
        setError(t("loadError"));
      })
      .finally(() => setLoading(false));
  }, [schoolId, t]);

  useEffect(() => {
    if (!hasAuthToken()) {
      setTeacherStats({});
      return;
    }
    void api
      .teacherAnalytics(schoolId)
      .then((rows) => {
        const next: Record<number, TeacherAnalytics> = {};
        rows.forEach((row) => {
          next[row.teacher_id] = row;
        });
        setTeacherStats(next);
      })
      .catch(() => {
        setTeacherStats({});
      });
  }, [schoolId, items.length]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const payload = {
      full_name: String(fd.get("full_name")),
      subjects: String(fd.get("subjects"))
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      weekly_load_limit: Number(fd.get("weekly_load_limit")) || 0,
      unavailable_days: String(fd.get("unavailable_days"))
        .split(",")
        .map((n) => Number(n.trim()))
        .filter((n) => !Number.isNaN(n)),
      school_id: schoolId
    };
    setSubmitBusy(true);
    setFeedback(null);
    try {
      if (editing) {
        const updated = await api.updateTeacher(editing.id, payload);
        setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
        setEditing(null);
        setFeedback({ type: "success", text: t("updated") });
      } else {
        const created = await api.createTeacher(payload);
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
        key={`teacher-form-${editing?.id ?? "new"}`}
        onSubmit={submit}
        className={`crud-form-panel ${submitBusy ? "busy-state" : ""}`}
      >
        <div className="crud-form-grid">
          <input name="full_name" placeholder={t("fullName")} required defaultValue={editing?.full_name} />
          <input name="subjects" placeholder={t("subjects")} defaultValue={editing?.subjects?.join(",")} />
          <input
            name="weekly_load_limit"
            placeholder={t("weeklyLimit")}
            type="number"
            defaultValue={editing?.weekly_load_limit}
          />
          <input
            name="unavailable_days"
            placeholder={t("unavailableDays")}
            defaultValue={editing?.unavailable_days?.join(",")}
          />
          <div className="crud-form-actions">
            <button type="submit" className="btn-primary focus-ring-strong" disabled={submitBusy}>
              {editing ? t("save") : t("add")}
            </button>
            {editing ? (
              <button type="button" onClick={() => setEditing(null)} className="btn-secondary focus-ring-strong">
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
            const stat = teacherStats[item.id];
            const actual = stat?.current_load ?? 0;
            const max = stat?.weekly_limit ?? item.weekly_load_limit ?? 0;
            const remaining = Math.max(0, max - actual);
            const over = actual > max && max > 0;
            const percent = max > 0 ? Math.min(100, Math.round((actual / max) * 100)) : 0;
            const emphasis =
              max > 0 ? t("statHeadline", { value: remaining }) : t("statHeadlineNoLimit", { value: actual });
            return (
              <CrudEntityCardShell
                key={item.id}
                title={item.full_name}
                meta={t("subjectsLabel", { value: item.subjects?.length ? item.subjects.join(", ") : "—" })}
                progress={{
                  actual,
                  max: max || 0,
                  percent,
                  over,
                  caption: t("progressCaption", { actual, max: max || 0 })
                }}
                statEmphasis={emphasis}
                status={over ? "bad" : "ok"}
                statusLabel={over ? t("overBy", { value: actual - max }) : t("withinLimit")}
                onEdit={() => setEditing(item)}
                onDelete={() => {
                  void (async () => {
                    setDeletingId(item.id);
                    setFeedback(null);
                    try {
                      await api.deleteTeacher(item.id);
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
