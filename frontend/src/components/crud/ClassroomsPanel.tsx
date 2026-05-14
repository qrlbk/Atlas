"use client";

import { FormEvent, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, Classroom, hasAuthToken, ScheduleItem, StudentClass } from "@/lib/api";
import { CrudEntityCardShell } from "./CrudEntityCardShell";

type Props = { schoolId: number };

export function ClassroomsPanel({ schoolId }: Props) {
  const t = useTranslations("crud.classrooms");
  const [items, setItems] = useState<Classroom[]>([]);
  const [scheduleItems, setScheduleItems] = useState<ScheduleItem[]>([]);
  const [classesMap, setClassesMap] = useState<Record<number, StudentClass>>({});
  const [totalLessonSlots, setTotalLessonSlots] = useState(35);
  const [editing, setEditing] = useState<Classroom | null>(null);
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
      .listClassrooms(schoolId)
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
      setClassesMap({});
      setTotalLessonSlots(35);
      return;
    }
    void Promise.all([api.listSchedule(schoolId), api.listClasses(schoolId), api.listLessonSlots()])
      .then(([schedule, classes, lessonSlots]) => {
        setScheduleItems(schedule);
        setClassesMap(
          classes.reduce<Record<number, StudentClass>>((acc, row) => {
            acc[row.id] = row;
            return acc;
          }, {})
        );
        setTotalLessonSlots(lessonSlots.length || 35);
      })
      .catch(() => {
        setScheduleItems([]);
        setClassesMap({});
        setTotalLessonSlots(35);
      });
  }, [schoolId, items.length]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const payload = {
      room_number: String(fd.get("room_number")),
      capacity: Number(fd.get("capacity")),
      specialization: String(fd.get("specialization")),
      school_id: schoolId
    };

    setSubmitBusy(true);
    setFeedback(null);
    try {
      if (editing) {
        const updated = await api.updateClassroom(editing.id, payload);
        setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
        setEditing(null);
        setFeedback({ type: "success", text: t("updated") });
      } else {
        const created = await api.createClassroom(payload);
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
        key={`classroom-form-${editing?.id ?? "new"}`}
        onSubmit={submit}
        className={`crud-form-panel ${submitBusy ? "busy-state" : ""}`}
      >
        <div className="crud-form-grid">
          <input name="room_number" placeholder={t("roomNumber")} required defaultValue={editing?.room_number} />
          <input name="capacity" placeholder={t("capacity")} type="number" required defaultValue={editing?.capacity} />
          <select name="specialization" defaultValue={editing?.specialization ?? "standard"}>
            <option value="standard">standard</option>
            <option value="chemistry_lab">chemistry_lab</option>
            <option value="physics_lab">physics_lab</option>
            <option value="gym">gym</option>
            <option value="language_room">language_room</option>
          </select>
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
            const roomLessons = scheduleItems.filter((lesson) => lesson.classroom_id === item.id);
            const lessonsCount = roomLessons.length;
            const freeSlots = Math.max(0, totalLessonSlots - lessonsCount);
            const maxClassSize = roomLessons.reduce((acc, lesson) => {
              const size = classesMap[lesson.class_id]?.students_count ?? 0;
              return Math.max(acc, size);
            }, 0);
            const overCapacity = maxClassSize > item.capacity;
            const usagePercent = Math.min(100, Math.round((lessonsCount / Math.max(1, totalLessonSlots)) * 100));
            const slotOver = lessonsCount > totalLessonSlots;
            return (
              <CrudEntityCardShell
                key={item.id}
                title={item.room_number}
                meta={
                  <>
                    <span>{item.specialization}</span>
                    <span className="saas-entity-card__meta-muted">{t("capacityShort", { value: item.capacity })}</span>
                  </>
                }
                progress={{
                  actual: lessonsCount,
                  max: totalLessonSlots,
                  percent: usagePercent,
                  over: overCapacity || slotOver,
                  caption: t("progressCaption", { actual: lessonsCount, max: totalLessonSlots })
                }}
                statEmphasis={t("statHeadline", { value: freeSlots })}
                status={overCapacity || slotOver ? "bad" : "ok"}
                statusLabel={
                  slotOver
                    ? t("slotsOver", { value: lessonsCount - totalLessonSlots })
                    : overCapacity
                      ? t("capacityMismatch", { maxClassSize, capacity: item.capacity })
                      : t("capacityMatched")
                }
                onEdit={() => setEditing(item)}
                onDelete={() => {
                  void (async () => {
                    setDeletingId(item.id);
                    setFeedback(null);
                    try {
                      await api.deleteClassroom(item.id);
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
