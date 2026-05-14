"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  api,
  ClassSubjectHours,
  hasAuthToken,
  PlanRowCoverage,
  StudentClass,
  Subject,
  SchedulePlanStatus
} from "@/lib/api";
import { CrudEntityCardShell } from "@/components/crud/CrudEntityCardShell";

type Props = { schoolId: number; hideHeader?: boolean };

function fillPercent(fillRate: number): number {
  return Math.min(100, Math.max(0, Math.round(fillRate * 100)));
}

export function CurriculumPanel({ schoolId, hideHeader }: Props) {
  const t = useTranslations("crud.curriculum");
  const [classes, setClasses] = useState<StudentClass[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [planRows, setPlanRows] = useState<ClassSubjectHours[]>([]);
  const [planStatus, setPlanStatus] = useState<SchedulePlanStatus | null>(null);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [editing, setEditing] = useState<ClassSubjectHours | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitBusy, setSubmitBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const coverageByPlanId = useMemo(() => {
    const m = new Map<number, PlanRowCoverage>();
    planStatus?.rows.forEach((r) => m.set(r.plan_id, r));
    return m;
  }, [planStatus]);

  async function reload() {
    if (!hasAuthToken()) {
      setLoading(false);
      setClasses([]);
      setSubjects([]);
      setPlanRows([]);
      setPlanStatus(null);
      setSelectedClassId(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [cls, subj, hours, status] = await Promise.all([
        api.listClasses(schoolId),
        api.listSubjects(),
        api.listClassSubjectHours(schoolId),
        api.schedulePlanStatus(schoolId)
      ]);
      setClasses(cls);
      setSubjects(subj);
      setPlanRows(hours);
      setPlanStatus(status);
      setSelectedClassId((prev) => {
        if (prev != null && cls.some((c) => c.id === prev)) return prev;
        return cls[0]?.id ?? null;
      });
    } catch {
      setClasses([]);
      setSubjects([]);
      setPlanRows([]);
      setPlanStatus(null);
      setSelectedClassId(null);
      setError(t("loadError"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, [schoolId]);

  const rowsForClass = useMemo(() => {
    if (selectedClassId == null) return [];
    return planRows.filter((r) => r.class_id === selectedClassId);
  }, [planRows, selectedClassId]);

  const subjectOptions = useMemo(() => {
    const used = new Set(rowsForClass.map((r) => r.subject_id));
    if (editing) used.delete(editing.subject_id);
    return subjects.filter((s) => !used.has(s.id));
  }, [subjects, rowsForClass, editing]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedClassId == null) {
      setFeedback({ type: "error", text: t("pickClass") });
      return;
    }
    const form = event.currentTarget;
    const fd = new FormData(form);
    const subjectId = Number(fd.get("subject_id"));
    const hours = Number(fd.get("hours_per_week"));
    if (!subjectId || Number.isNaN(hours) || hours < 1) {
      setFeedback({ type: "error", text: t("invalidHours") });
      return;
    }
    const payload = {
      school_id: schoolId,
      class_id: selectedClassId,
      subject_id: subjectId,
      hours_per_week: Math.floor(hours)
    };
    setSubmitBusy(true);
    setFeedback(null);
    try {
      if (editing) {
        const updated = await api.updateClassSubjectHours(editing.id, payload);
        setPlanRows((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
        setEditing(null);
        setFeedback({ type: "success", text: t("updated") });
      } else {
        const created = await api.createClassSubjectHours(payload);
        setPlanRows((prev) => [...prev, created]);
        setFeedback({ type: "success", text: t("added") });
      }
      form.reset();
      const status = await api.schedulePlanStatus(schoolId);
      setPlanStatus(status);
    } catch {
      setFeedback({ type: "error", text: t("saveError") });
    } finally {
      setSubmitBusy(false);
    }
  }

  async function remove(id: number) {
    setDeletingId(id);
    setFeedback(null);
    try {
      await api.deleteClassSubjectHours(id);
      setPlanRows((prev) => prev.filter((x) => x.id !== id));
      setFeedback({ type: "success", text: t("deleted") });
      const status = await api.schedulePlanStatus(schoolId);
      setPlanStatus(status);
    } catch {
      setFeedback({ type: "error", text: t("deleteError") });
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <article className="section-card space-y-3">
      {hideHeader ? null : (
        <header className="space-y-1">
          <h2 className="section-title">{t("title")}</h2>
          <p className="section-subtitle">{t("subtitle")}</p>
        </header>
      )}

      {planStatus ? (
        <div className="reference-panel panel-subtle">
          <div className="reference-panel-header">
            <span className="text-sm font-semibold text-slate-800">{t("summaryLine", {
              rows: planStatus.summary.plan_row_count,
              fill: fillPercent(planStatus.summary.fill_rate),
              missing: planStatus.summary.classes_without_plan_count
            })}</span>
          </div>
          <div className="reference-panel-body space-y-2">
            <div className="flex flex-wrap gap-2 items-center">
              <span className="metric-chip">{t("chipFill", { value: fillPercent(planStatus.summary.fill_rate) })}</span>
              <span className="metric-chip subtle">{t("chipRows", { value: planStatus.summary.plan_row_count })}</span>
              <span className="metric-chip subtle">{t("chipMissing", { value: planStatus.summary.classes_without_plan_count })}</span>
            </div>
            <p className="text-xs text-slate-500 leading-snug">{t("snapshotHelp")}</p>
          </div>
        </div>
      ) : null}

      {loading ? <p className="empty-note">{t("loading")}</p> : null}
      {error ? <p className="empty-note">{error}</p> : null}

      {!loading && !error && classes.length === 0 ? <p className="empty-note">{t("noClasses")}</p> : null}

      {!loading && !error && classes.length > 0 ? (
        <div className="saas-dual-stack">
          <div className="workspace-grid curriculum-workspace">
          <div className="panel">
            <div className="panel-header">
              <span className="text-sm font-semibold text-slate-900">{t("formPanelTitle")}</span>
            </div>
            <div className="panel-body space-y-3">
              <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
                {t("classLabel")}
                <select
                  className="w-full max-w-md"
                  value={selectedClassId ?? ""}
                  onChange={(e) => setSelectedClassId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">{t("classPlaceholder")}</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.class_name}
                    </option>
                  ))}
                </select>
              </label>

              {selectedClassId != null ? (
                <form
                  key={`curriculum-form-${editing?.id ?? "new"}`}
                  onSubmit={submit}
                  className={`crud-form-panel ${submitBusy ? "busy-state" : ""}`}
                >
                  <div className="crud-form-grid">
                  <select
                    name="subject_id"
                    required
                    className="w-full max-w-md"
                    defaultValue={editing?.subject_id ?? ""}
                    key={`subsel-${editing?.id ?? "new"}-${selectedClassId}`}
                  >
                    <option value="" disabled>
                      {t("subjectPlaceholder")}
                    </option>
                    {(editing
                      ? subjects.filter(
                          (s) =>
                            s.id === editing.subject_id ||
                            !rowsForClass.some((r) => r.subject_id === s.id && r.id !== editing.id)
                        )
                      : subjectOptions
                    ).map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                  <input
                    name="hours_per_week"
                    type="number"
                    min={1}
                    required
                    placeholder={t("hoursPlaceholder")}
                    defaultValue={editing?.hours_per_week ?? 1}
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
              ) : (
                <p className="text-sm text-slate-600">{t("pickClass")}</p>
              )}
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <span className="text-sm font-semibold text-slate-900">{t("listPanelTitle")}</span>
            </div>
            <div className="panel-body">
              {feedback ? <p className={`inline-feedback ${feedback.type}`}>{feedback.text}</p> : null}

              {selectedClassId == null ? (
                <p className="empty-note">{t("pickClass")}</p>
              ) : rowsForClass.length === 0 ? (
                <p className="empty-note">{t("emptyClass")}</p>
              ) : (
                <div className="saas-grid-host">
                  <ul className="entity-card-grid" data-testid="curriculum-rows">
                    {rowsForClass.map((row) => {
                      const cov = coverageByPlanId.get(row.id);
                      const scheduled = cov != null ? cov.scheduled_hours : 0;
                      const planned = row.hours_per_week;
                      const denom = Math.max(planned, 1);
                      const pct = Math.min(100, Math.round((scheduled / denom) * 100));
                      const over = scheduled > planned;
                      const subjectName = subjects.find((s) => s.id === row.subject_id)?.name ?? `#${row.subject_id}`;
                      return (
                        <CrudEntityCardShell
                          key={row.id}
                          title={subjectName}
                          meta={t("hoursLine", { planned, scheduled: String(scheduled) })}
                          progress={{
                            actual: scheduled,
                            max: planned,
                            percent: pct,
                            over,
                            caption: t("progressCaption", { actual: scheduled, max: planned })
                          }}
                          statEmphasis={
                            over
                              ? t("statOver", { value: scheduled - planned })
                              : t("statHeadline", { value: Math.max(0, planned - scheduled) })
                          }
                          status={over ? "bad" : "ok"}
                          statusLabel={over ? t("overPlan", { value: scheduled - planned }) : t("withinPlan")}
                          onEdit={() => setEditing(row)}
                          onDelete={() => void remove(row.id)}
                          deleteDisabled={deletingId === row.id}
                          editLabel={t("edit")}
                          deleteLabel={t("delete")}
                          busy={deletingId === row.id}
                        />
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
        </div>
      ) : null}
    </article>
  );
}
