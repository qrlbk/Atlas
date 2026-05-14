"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, hasAuthToken, TeacherAnalytics as TeacherAnalyticsRow } from "@/lib/api";
import { CrudEntityCardShell } from "@/components/crud/CrudEntityCardShell";

type Props = { schoolId: number; hideHeader?: boolean };

export function TeacherAnalytics({ schoolId, hideHeader }: Props) {
  const t = useTranslations("analytics");
  const [rows, setRows] = useState<TeacherAnalyticsRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "overloaded">("all");

  useEffect(() => {
    if (!hasAuthToken()) {
      setRows([]);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    void api
      .teacherAnalytics(schoolId)
      .then(setRows)
      .catch(() => {
        setRows([]);
        setError(t("loadError"));
      })
      .finally(() => setLoading(false));
  }, [schoolId, t]);

  const visibleRows = rows.filter((row) => (filter === "overloaded" ? row.current_load > row.weekly_limit : true));

  return (
    <section className="section-card space-y-3" data-testid="teacher-analytics">
      {hideHeader ? null : (
        <header className="space-y-1">
          <h2 className="section-title">{t("title")}</h2>
          <p className="section-subtitle">{t("subtitle")}</p>
        </header>
      )}
      <div className="saas-toolbar" role="group" aria-label={t("title")}>
        <button
          type="button"
          className={`saas-toolbar-btn focus-ring-strong ${filter === "all" ? "saas-toolbar-btn--active" : ""}`}
          onClick={() => setFilter("all")}
        >
          {t("all")}
        </button>
        <button
          type="button"
          className={`saas-toolbar-btn focus-ring-strong ${filter === "overloaded" ? "saas-toolbar-btn--active" : ""}`}
          onClick={() => setFilter("overloaded")}
        >
          {t("overloaded")}
        </button>
      </div>
      {loading ? <p className="empty-note">{t("loading")}</p> : null}
      {error ? <p className="empty-note">{error}</p> : null}
      {!loading && !error && visibleRows.length === 0 ? <p className="empty-note">{t("empty")}</p> : null}
      {!loading && !error && visibleRows.length > 0 ? (
        <div className="saas-grid-host">
          <ul className="entity-card-grid text-sm">
            {visibleRows.map((row) => {
              const max = row.weekly_limit;
              const actual = row.current_load;
              const remaining = Math.max(0, max - actual);
              const over = max > 0 && actual > max;
              const pct = max > 0 ? Math.min(100, Math.round((actual / max) * 100)) : 0;
              const emphasis =
                max > 0 ? t("statHeadline", { value: remaining }) : t("statHeadlineNoLimit", { value: actual });
              return (
                <CrudEntityCardShell
                  key={row.teacher_id}
                  title={row.teacher_name}
                  meta={t("windowsLine", { value: row.windows })}
                  progress={{
                    actual,
                    max: max || 0,
                    percent: pct,
                    over,
                    caption: t("progressCaption", { actual, max: max || 0 })
                  }}
                  statEmphasis={emphasis}
                  status={over ? "bad" : "ok"}
                  statusLabel={over ? t("overBy", { value: actual - max }) : t("withinLimit")}
                  showActions={false}
                />
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
