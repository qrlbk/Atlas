"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, ClassFatigueAlert, DayCongestionAnalytics, hasAuthToken, TeacherLoadMatrixRow } from "@/lib/api";

type Props = { schoolId: number };

function heatLevel(count: number, max: number): string {
  if (max <= 0 || count <= 0) return "heatmap-cell--0";
  const ratio = count / max;
  if (ratio >= 0.85) return "heatmap-cell--4";
  if (ratio >= 0.6) return "heatmap-cell--3";
  if (ratio >= 0.35) return "heatmap-cell--2";
  return "heatmap-cell--1";
}

export function ScheduleHeatmaps({ schoolId }: Props) {
  const t = useTranslations("analytics.heatmaps");
  const [teachers, setTeachers] = useState<TeacherLoadMatrixRow[]>([]);
  const [congestion, setCongestion] = useState<DayCongestionAnalytics | null>(null);
  const [fatigue, setFatigue] = useState<ClassFatigueAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hasAuthToken()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    void Promise.all([
      api.teacherLoadMatrix(schoolId),
      api.dayCongestion(schoolId),
      api.classFatigue(schoolId)
    ])
      .then(([tm, dc, cf]) => {
        setTeachers(tm);
        setCongestion(dc);
        setFatigue(cf.alerts);
      })
      .catch(() => {
        setTeachers([]);
        setCongestion(null);
        setFatigue([]);
      })
      .finally(() => setLoading(false));
  }, [schoolId]);

  const maxTeacherDay = Math.max(1, ...teachers.flatMap((row) => Object.values(row.by_day)));
  const dayKeys = congestion ? Object.keys(congestion.by_day_slot).sort() : [];
  const slotKeys = dayKeys.length
    ? Array.from(
        new Set(dayKeys.flatMap((d) => Object.keys(congestion!.by_day_slot[d] ?? {})))
      ).sort((a, b) => Number(a) - Number(b))
    : [];
  const maxCongestion = Math.max(
    1,
    ...dayKeys.flatMap((d) => Object.values(congestion?.by_day_slot[d] ?? {}))
  );

  if (loading) return <p className="empty-note">{t("loading")}</p>;

  return (
    <div className="space-y-6" data-testid="schedule-heatmaps">
      <section className="section-card space-y-2">
        <h3 className="section-title text-base">{t("teacherLoadTitle")}</h3>
        {teachers.length === 0 ? (
          <p className="empty-note">{t("empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr>
                  <th className="text-left p-1">{t("teacher")}</th>
                  {[1, 2, 3, 4, 5].map((d) => (
                    <th key={d} className="p-1">
                      {t("day", { day: d })}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {teachers.map((row) => (
                  <tr key={row.teacher_id}>
                    <td className="p-1 font-medium">{row.teacher_name}</td>
                    {[1, 2, 3, 4, 5].map((d) => {
                      const c = row.by_day[d] ?? 0;
                      return (
                        <td
                          key={d}
                          className={`heatmap-cell p-1 text-center ${heatLevel(c, maxTeacherDay)}`}
                          title={String(c)}
                        >
                          {c || "·"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section-card space-y-2">
        <h3 className="section-title text-base">{t("congestionTitle")}</h3>
        {!congestion || dayKeys.length === 0 ? (
          <p className="empty-note">{t("empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr>
                  <th className="text-left p-1">{t("daySlot")}</th>
                  {slotKeys.map((s) => (
                    <th key={s} className="p-1">
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dayKeys.map((d) => (
                  <tr key={d}>
                    <td className="p-1">{t("day", { day: d })}</td>
                    {slotKeys.map((s) => {
                      const c = congestion.by_day_slot[d]?.[s] ?? 0;
                      return (
                        <td key={s} className={`heatmap-cell p-1 text-center ${heatLevel(c, maxCongestion)}`}>
                          {c || "·"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section-card space-y-2">
        <h3 className="section-title text-base">{t("fatigueTitle")}</h3>
        {fatigue.length === 0 ? (
          <p className="empty-note">{t("fatigueEmpty")}</p>
        ) : (
          <ul className="text-sm space-y-1">
            {fatigue.map((a, i) => (
              <li key={`${a.class_id}-${a.day_of_week}-${a.subject_id}-${i}`}>
                {t("fatigueRow", {
                  className: a.class_name,
                  day: a.day_of_week,
                  subjectId: a.subject_id
                })}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
