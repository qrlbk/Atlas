"use client";

import { useTranslations } from "next-intl";

export function HealthBadge({ status }: { status: string }) {
  const t = useTranslations("admin.health");
  const key = ["green", "yellow", "red", "unknown"].includes(status) ? status : "unknown";
  return <span className={`health-badge health-badge--${key}`}>{t(key as "green")}</span>;
}
