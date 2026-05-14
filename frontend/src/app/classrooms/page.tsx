"use client";

import { ClassroomsPanel } from "@/components/crud/ClassroomsPanel";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import {useTranslations} from "next-intl";

export default function ClassroomsPage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.classrooms");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={<span className="metric-chip subtle">{t("actions")}</span>}
    >
      <ClassroomsPanel key={`classrooms-${refreshKey}`} schoolId={schoolId} />
    </DashboardShell>
  );
}
