"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { CrudPanel } from "@/components/CrudPanel";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";

/**
 * Single-page “compact” workspace: same blocks as the sidebar pages,
 * in one scroll. Uses the same shell as the rest of the app so navigation stays visible.
 */
export default function WorkspacePage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.workspace");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
      actions={
        <Link href="/" className="text-sm text-sky-800 underline whitespace-nowrap">
          {t("backToDashboard")}
        </Link>
      }
    >
      {isAuthenticated ? (
        <CrudPanel key={`workspace-crud-${refreshKey}`} schoolId={schoolId} />
      ) : null}
    </DashboardShell>
  );
}
