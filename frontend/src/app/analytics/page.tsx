"use client";

import { ScheduleHeatmaps } from "@/components/ScheduleHeatmaps";
import { TeacherAnalytics } from "@/components/TeacherAnalytics";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import {useTranslations} from "next-intl";

export default function AnalyticsPage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.analytics");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={<span className="metric-chip subtle">{t("actions")}</span>}
    >
      <TeacherAnalytics key={`analytics-${refreshKey}`} schoolId={schoolId} hideHeader />
      <ScheduleHeatmaps key={`heatmaps-${refreshKey}`} schoolId={schoolId} />
    </DashboardShell>
  );
}
