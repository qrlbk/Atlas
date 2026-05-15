"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, hasAuthToken } from "@/lib/api";

const DEFAULT_PREFS = `{
  "plan_compliance": "warn",
  "issue_weights": {
    "TEACHER_DOUBLE_BOOKING": 10
  }
}`;

type Props = { schoolId: number };

export function SchedulingPreferencesPanel({ schoolId }: Props) {
  const t = useTranslations("schedulingPrefs");
  const [jsonText, setJsonText] = useState(DEFAULT_PREFS);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hasAuthToken()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    void api
      .listSchools()
      .then((schools) => {
        const school = schools.find((s) => s.id === schoolId);
        if (school?.scheduling_preferences) {
          setJsonText(JSON.stringify(school.scheduling_preferences, null, 2));
        } else {
          setJsonText(DEFAULT_PREFS);
        }
      })
      .catch(() => setStatus(t("loadFailed")))
      .finally(() => setLoading(false));
  }, [schoolId, t]);

  async function save() {
    setStatus(null);
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(jsonText) as Record<string, unknown>;
    } catch {
      setStatus(t("invalidJson"));
      return;
    }
    try {
      await api.patchSchool(schoolId, { scheduling_preferences: parsed });
      setStatus(t("saved"));
    } catch {
      setStatus(t("saveFailed"));
    }
  }

  return (
    <section className="reference-panel schedule-panel-tight" data-testid="scheduling-preferences">
      <div className="reference-panel-header">
        <strong className="text-sm">{t("title")}</strong>
        <span className="schedule-grid-sub">{t("hint")}</span>
      </div>
      {loading ? <p className="empty-note">{t("loading")}</p> : null}
      <textarea
        className="scheduling-prefs-editor focus-ring-strong"
        rows={8}
        value={jsonText}
        onChange={(e) => setJsonText(e.target.value)}
        aria-label={t("editorLabel")}
        data-testid="scheduling-prefs-json"
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="btn-schedule-primary focus-ring-strong"
          onClick={() => void save()}
          data-testid="scheduling-prefs-save"
        >
          {t("save")}
        </button>
        {status ? <span className="schedule-hint-text">{status}</span> : null}
      </div>
    </section>
  );
}
