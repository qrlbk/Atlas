"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

type Props = {
  capability?: string;
  onDismiss?: () => void;
};

export function UpgradePanel({ capability, onDismiss }: Props) {
  const t = useTranslations("upgrade");

  return (
    <div className="upgrade-panel" role="alert">
      <h3 className="section-title">{t("title")}</h3>
      <p className="section-subtitle">{t("subtitle")}</p>
      {capability ? <p className="metric-chip subtle">{t("capability", { capability })}</p> : null}
      <div className="upgrade-panel__actions">
        <Link href="/pricing" className="btn-schedule-primary">
          {t("ctaPricing")}
        </Link>
        {onDismiss ? (
          <button type="button" className="btn-schedule-ghost" onClick={onDismiss}>
            {t("dismiss")}
          </button>
        ) : null}
      </div>
    </div>
  );
}
