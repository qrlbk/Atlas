"use client";

import { FormEvent, useState } from "react";
import {useTranslations} from "next-intl";
import { api, clearStoredToken, setStoredToken } from "@/lib/api";

type Props = {
  /** Mirrors JWT presence; parent updates on login, logout, and atlas-auth-expired. */
  sessionActive: boolean;
  onAuthChange: () => void;
  /** `mini` — compact top-bar row (schedule / focus layouts). */
  variant?: "panel" | "mini";
};

export function LoginBar({ sessionActive, onAuthChange, variant = "panel" }: Props) {
  const t = useTranslations("login");
  const [loginError, setLoginError] = useState<string | null>(null);

  async function onLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form) return;
    const fd = new FormData(form);
    const email = String(fd.get("email"));
    const password = String(fd.get("password"));
    setLoginError(null);
    try {
      const res = await api.login(email, password);
      setStoredToken(res.access_token);
      // Reset before bump: parent may switch UI and unmount this form (avoid detached / pooled event issues).
      form.reset();
      onAuthChange();
    } catch {
      clearStoredToken();
      setLoginError(t("invalidCredentials"));
      onAuthChange();
    }
  }

  function onLogout() {
    clearStoredToken();
    setLoginError(null);
    onAuthChange();
  }

  if (variant === "mini") {
    return (
      <div className="login-bar login-bar--mini" data-testid="login-bar">
        {sessionActive ? (
          <div className="login-bar-mini-session">
            <span className="login-bar-mini-dot" aria-hidden />
            <span className="login-bar-mini-label" data-testid="login-status">
              {t("miniRole")}
            </span>
            <button type="button" data-testid="logout-button" onClick={onLogout} className="btn-schedule-ghost">
              {t("logout")}
            </button>
          </div>
        ) : (
          <form onSubmit={onLogin} className="login-bar-mini-form">
            <input
              name="email"
              type="email"
              data-testid="login-email"
              required
              placeholder={t("email")}
              className="login-bar-mini-input focus-ring-strong"
              autoComplete="username"
            />
            <input
              name="password"
              type="password"
              data-testid="login-password"
              required
              placeholder={t("password")}
              className="login-bar-mini-input focus-ring-strong"
              autoComplete="current-password"
            />
            <button type="submit" data-testid="login-submit" className="btn-schedule-secondary">
              {t("signin")}
            </button>
            {loginError ? <span className="login-bar-mini-error">{loginError}</span> : null}
          </form>
        )}
      </div>
    );
  }

  return (
    <section className="section-card" data-testid="login-bar">
      {sessionActive ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h2 className="section-title">{t("authTitle")}</h2>
            <p className="section-subtitle">{t("sessionActive")}</p>
          </div>
          <span className="status-pill success" data-testid="login-status">
            {t("signedIn")}
          </span>
          <button type="button" data-testid="logout-button" onClick={onLogout} className="btn-secondary">
            {t("logout")}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="space-y-1">
            <h2 className="section-title">{t("signinTitle")}</h2>
            <p className="section-subtitle">{t("signinSubtitle")}</p>
          </div>
          <form onSubmit={onLogin} className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <label className="flex flex-col gap-1 text-sm text-slate-700">
              {t("email")}
              <input name="email" type="email" data-testid="login-email" required className="min-w-[220px]" />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-700">
              {t("password")}
              <input name="password" type="password" data-testid="login-password" required />
            </label>
            <button type="submit" data-testid="login-submit" className="btn-primary">
              {t("signin")}
            </button>
          </form>
          {loginError ? <p className="text-sm text-red-600">{loginError}</p> : null}
        </div>
      )}
    </section>
  );
}
