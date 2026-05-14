"use client";

import { useEffect, useMemo, useState } from "react";
import {useTranslations} from "next-intl";
import Link from "next/link";
import {
  api,
  Classroom,
  GroupFlow,
  hasAuthToken,
  ScheduleItem,
  SchedulePlanStatus,
  StudentClass,
  Teacher,
  TeacherAnalytics
} from "@/lib/api";

type Props = { schoolId: number };

type OverviewState = {
  teachers: Teacher[];
  classrooms: Classroom[];
  classes: StudentClass[];
  flows: GroupFlow[];
  schedule: ScheduleItem[];
  analytics: TeacherAnalytics[];
  planStatus: SchedulePlanStatus | null;
};

const EMPTY_STATE: OverviewState = {
  teachers: [],
  classrooms: [],
  classes: [],
  flows: [],
  schedule: [],
  analytics: [],
  planStatus: null
};

export function DashboardOverview({ schoolId }: Props) {
  const t = useTranslations("overview");
  const [data, setData] = useState<OverviewState>(EMPTY_STATE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasAuthToken()) {
      setData(EMPTY_STATE);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    void Promise.all([
      api.listTeachers(schoolId),
      api.listClassrooms(schoolId),
      api.listClasses(schoolId),
      api.listFlows(schoolId),
      api.listSchedule(schoolId),
      api.teacherAnalytics(schoolId),
      api.schedulePlanStatus(schoolId).catch(() => null)
    ])
      .then(([teachers, classrooms, classes, flows, schedule, analytics, planStatus]) => {
        setData({ teachers, classrooms, classes, flows, schedule, analytics, planStatus });
      })
      .catch(() => {
        setData(EMPTY_STATE);
        setError(t("loadError"));
      })
      .finally(() => setLoading(false));
  }, [schoolId, t]);

  const stats = useMemo(() => {
    const overloadedTeachers = data.analytics.filter((row) => row.current_load > row.weekly_limit).length;
    const totalCapacity = data.classrooms.reduce((sum, room) => sum + room.capacity, 0);
    const totalStudents = data.classes.reduce((sum, group) => sum + group.students_count, 0);
    const capacityBuffer = totalCapacity - totalStudents;
    const groupedLessons = data.schedule.filter((item) => item.is_grouped).length;
    return {
      teachers: data.teachers.length,
      classrooms: data.classrooms.length,
      classes: data.classes.length,
      flows: data.flows.length,
      lessons: data.schedule.length,
      overloadedTeachers,
      totalCapacity,
      totalStudents,
      capacityBuffer,
      groupedLessons
    };
  }, [data]);

  const topTeacherRisks = useMemo(
    () =>
      data.analytics
        .filter((row) => row.current_load > row.weekly_limit)
        .sort((a, b) => b.current_load - b.weekly_limit - (a.current_load - a.weekly_limit))
        .slice(0, 4),
    [data.analytics]
  );

  const lessonsByDay = useMemo(() => {
    const bins = [0, 0, 0, 0, 0];
    data.schedule.forEach((item) => {
      const dayIndex = Math.ceil(item.lesson_slot_id / 7) - 1;
      if (dayIndex >= 0 && dayIndex < bins.length) bins[dayIndex] += 1;
    });
    return bins;
  }, [data.schedule]);

  const topTeacherLoads = useMemo(
    () =>
      data.analytics
        .slice()
        .sort((a, b) => b.current_load - a.current_load)
        .slice(0, 6)
        .map((row) => row.current_load),
    [data.analytics]
  );

  if (loading) return <p className="empty-note">{t("loading")}</p>;
  if (error) return <p className="empty-note">{error}</p>;

  return (
    <section className="overview-grid" data-testid="dashboard-overview">
      <article className="section-card compact-card">
        <h3 className="section-title">{t("coreKpis")}</h3>
        <div className="sparkline-block">
          <p className="section-subtitle">{t("lessonsByWeekday")}</p>
          <div className="sparkline-bars" aria-label={t("lessonsByWeekday")}>
            {lessonsByDay.map((value, idx) => {
              const max = Math.max(1, ...lessonsByDay);
              const height = Math.max(16, Math.round((value / max) * 42));
              return (
                <div key={`day-${idx}`} className="spark-bar-wrap">
                  <div className="spark-bar" style={{ height }} />
                  <span>{["M", "T", "W", "T", "F"][idx]}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="kpi-grid">
          <div className="kpi-tile"><p>{t("teachers")}</p><strong>{stats.teachers}</strong></div>
          <div className="kpi-tile"><p>{t("classrooms")}</p><strong>{stats.classrooms}</strong></div>
          <div className="kpi-tile"><p>{t("classes")}</p><strong>{stats.classes}</strong></div>
          <div className="kpi-tile"><p>{t("flows")}</p><strong>{stats.flows}</strong></div>
          <div className="kpi-tile"><p>{t("lessons")}</p><strong>{stats.lessons}</strong></div>
          <div className="kpi-tile"><p>{t("grouped")}</p><strong>{stats.groupedLessons}</strong></div>
        </div>
      </article>

      <article className="section-card compact-card">
        <h3 className="section-title">{t("teacherLoadRisk")}</h3>
        <p className="section-subtitle">{t("teacherLoadRiskSubtitle")}</p>
        <p className="metric-chip subtle">{t("overloaded", {value: stats.overloadedTeachers})}</p>
        <div className="sparkline-block">
          <p className="section-subtitle">{t("topTeacherLoads")}</p>
          <div className="sparkline-bars" aria-label={t("topTeacherLoads")}>
            {topTeacherLoads.map((value, idx) => {
              const max = Math.max(1, ...topTeacherLoads);
              const height = Math.max(16, Math.round((value / max) * 42));
              return (
                <div key={`teacher-load-${idx}`} className="spark-bar-wrap">
                  <div className="spark-bar alt" style={{ height }} />
                  <span>{idx + 1}</span>
                </div>
              );
            })}
          </div>
        </div>
        <ul className="compact-list">
          {topTeacherRisks.length === 0 ? (
            <li className="empty-note">{t("noOverloads")}</li>
          ) : (
            topTeacherRisks.map((row) => (
              <li key={row.teacher_id} className="compact-row">
                <span className="font-medium text-slate-800">{row.teacher_name}</span>
                <span className="status-pill warning">{t("overHours", {value: row.current_load - row.weekly_limit})}</span>
              </li>
            ))
          )}
        </ul>
      </article>

      <article className="section-card compact-card">
        <h3 className="section-title">{t("planCoverageTitle")}</h3>
        <p className="section-subtitle">{t("planCoverageSubtitle")}</p>
        {data.planStatus == null ? (
          <p className="empty-note">{t("planCoverageUnavailable")}</p>
        ) : (
          <>
            <p className="metric-chip subtle">
              {t("planCoverageLine", {
                fill: Math.min(100, Math.max(0, Math.round((data.planStatus.summary.fill_rate ?? 0) * 100))),
                rows: data.planStatus.summary.plan_row_count,
                missing: data.planStatus.summary.classes_without_plan_count
              })}
            </p>
            <p className="section-subtitle">
              {t("planCoverageUnderOver", {
                under: data.planStatus.summary.rows_under,
                over: data.planStatus.summary.rows_over
              })}
            </p>
            <p>
              <Link href="/curriculum" className="text-sky-700 underline">
                {t("planCoverageCta")}
              </Link>
            </p>
          </>
        )}
      </article>

      <article className="section-card compact-card">
        <h3 className="section-title">{t("capacitySummary")}</h3>
        <div className="compact-metrics">
          <p>{t("totalStudents")} <strong>{stats.totalStudents}</strong></p>
          <p>{t("totalCapacity")} <strong>{stats.totalCapacity}</strong></p>
          <p>
            {t("buffer")}{" "}
            <strong className={stats.capacityBuffer < 0 ? "text-red-700" : "text-slate-700"}>{stats.capacityBuffer}</strong>
          </p>
        </div>
      </article>

      <article className="section-card compact-card">
        <h3 className="section-title">{t("readonlyTitle")}</h3>
        <p className="section-subtitle">
          {t("readonlySubtitle")}
        </p>
      </article>
    </section>
  );
}

