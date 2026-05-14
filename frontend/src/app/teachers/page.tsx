"use client";

import { TeachersPanel } from "@/components/crud/TeachersPanel";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import {useTranslations} from "next-intl";

export default function TeachersPage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.teachers");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={<span className="metric-chip subtle">{t("sync", {refreshKey})}</span>}
    >
      <TeachersPanel key={`teachers-${refreshKey}`} schoolId={schoolId} />
    </DashboardShell>
  );
}
