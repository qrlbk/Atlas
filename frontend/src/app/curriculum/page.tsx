"use client";

import { CurriculumPanel } from "@/components/crud/CurriculumPanel";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import { useTranslations } from "next-intl";

export default function CurriculumPage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.curriculum");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={<span className="metric-chip subtle">{t("sync", {refreshKey})}</span>}
    >
      <CurriculumPanel key={`curriculum-${refreshKey}`} schoolId={schoolId} hideHeader />
    </DashboardShell>
  );
}
