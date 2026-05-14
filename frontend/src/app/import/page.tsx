"use client";

import { useTranslations } from "next-intl";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import { ImportWizard } from "@/components/import/ImportWizard";

export default function ImportPage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.import");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={<span className="metric-chip subtle">{t("sync", { refreshKey })}</span>}
    >
      <ImportWizard key={`import-${refreshKey}`} schoolId={schoolId} />
    </DashboardShell>
  );
}
