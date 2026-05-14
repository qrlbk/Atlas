"use client";

import { FlowsPanel } from "@/components/crud/FlowsPanel";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import {useTranslations} from "next-intl";

export default function FlowsPage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.flows");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={<span className="metric-chip subtle">{t("actions")}</span>}
    >
      <FlowsPanel key={`flows-${refreshKey}`} schoolId={schoolId} />
    </DashboardShell>
  );
}
