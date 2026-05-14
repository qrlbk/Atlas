"use client";

import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import {useTranslations} from "next-intl";

export default function Home() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.home");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={
        <>
          <span className="metric-chip subtle">{t("school", {schoolId})}</span>
          <span className="metric-chip">{t("session", {refreshKey})}</span>
        </>
      }
    >
      <DashboardOverview key={`overview-${refreshKey}`} schoolId={schoolId} />
    </DashboardShell>
  );
}
