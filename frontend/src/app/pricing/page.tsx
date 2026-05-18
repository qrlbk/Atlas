"use client";

import { useTranslations } from "next-intl";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";

export default function PricingPage() {
  const { schoolId, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pricing");

  return (
    <DashboardShell
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
    >
      <section className="pricing-grid">
        <article className="section-card">
          <h3 className="section-title">{t("freeTitle")}</h3>
          <p className="section-subtitle">{t("freeDesc")}</p>
          <ul className="compact-list">
            <li>{t("freeManual")}</li>
            <li>{t("freeValidation")}</li>
            <li>{t("freePdf")}</li>
          </ul>
        </article>
        <article className="section-card pricing-pro">
          <h3 className="section-title">{t("proTitle")}</h3>
          <p className="section-subtitle">{t("proDesc")}</p>
          <ul className="compact-list">
            <li>{t("proSolver")}</li>
            <li>{t("proScenarios")}</li>
            <li>{t("proExport")}</li>
          </ul>
          <p className="metric-chip">{t("proPrice")}</p>
          <p className="section-subtitle">{t("contact")}</p>
        </article>
      </section>
    </DashboardShell>
  );
}
