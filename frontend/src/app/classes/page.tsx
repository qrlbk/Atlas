"use client";

import { ClassesPanel } from "@/components/crud/ClassesPanel";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import {useTranslations} from "next-intl";

export default function ClassesPage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.classes");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={<span className="metric-chip subtle">{t("actions")}</span>}
    >
      <ClassesPanel key={`classes-${refreshKey}`} schoolId={schoolId} />
    </DashboardShell>
  );
}
