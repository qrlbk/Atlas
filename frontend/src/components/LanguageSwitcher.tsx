"use client";

import {useEffect} from "react";
import {useLocale, useTranslations} from "next-intl";
import {useRouter} from "next/navigation";

const LOCALES = [
  {id: "en", label: "EN"},
  {id: "ru", label: "RU"},
  {id: "kk", label: "KK"}
] as const;

type LangProps = { className?: string };

export function LanguageSwitcher({ className }: LangProps) {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations("lang");

  useEffect(() => {
    localStorage.setItem("atlas_locale", locale);
  }, [locale]);

  return (
    <label className={`schedule-lang-switch ${className ?? ""}`.trim()}>
      <span className="schedule-lang-switch__label">{t("label")}</span>
      <select
        className="schedule-lang-switch__select focus-ring-strong"
        value={locale}
        onChange={(event) => {
          const nextLocale = event.target.value;
          document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; max-age=31536000; samesite=lax`;
          localStorage.setItem("atlas_locale", nextLocale);
          router.refresh();
          window.location.reload();
        }}
      >
        {LOCALES.map((entry) => (
          <option key={entry.id} value={entry.id}>
            {entry.label}
          </option>
        ))}
      </select>
    </label>
  );
}
