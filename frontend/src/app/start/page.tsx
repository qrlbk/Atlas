"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { api, hasAuthToken } from "@/lib/api";

export default function StartPage() {
  const { schoolId, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.start");
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!hasAuthToken()) {
      setChecking(false);
      return;
    }
    void api
      .schoolReadiness(schoolId)
      .then((r) => {
        if (r.summary.onboarding_completed && r.status !== "unknown") {
          router.replace("/");
        }
      })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, [schoolId, router]);

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
    >
      {checking ? <p className="empty-note">{t("loading")}</p> : <OnboardingWizard schoolId={schoolId} />}
    </DashboardShell>
  );
}
