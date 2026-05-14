"use client";

import { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {useTranslations} from "next-intl";
import { LoginBar } from "@/components/LoginBar";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

type NavItem = { href: string; labelKey: string };

const NAV_ITEMS: NavItem[] = [
  { href: "/schedule", labelKey: "schedule" },
  { href: "/curriculum", labelKey: "curriculum" },
  { href: "/teachers", labelKey: "teachers" },
  { href: "/classrooms", labelKey: "classrooms" },
  { href: "/classes", labelKey: "classes" },
  { href: "/flows", labelKey: "flows" },
  { href: "/analytics", labelKey: "analytics" },
  { href: "/import", labelKey: "import" },
  { href: "/workspace", labelKey: "workspace" },
  { href: "/", labelKey: "dashboard" }
];

type Props = {
  title: string;
  subtitle: string;
  schoolId: number;
  isAuthenticated: boolean;
  onAuthChange: () => void;
  actions?: ReactNode;
  children: ReactNode;
  /** Title + subtitle only in the top bar; auth as mini widget; no school chip / actions row here. */
  headerMode?: "default" | "schedule";
  /** Extra class on the main column (e.g. tighter rhythm for schedule). */
  mainClassName?: string;
};

export function DashboardShell({
  title,
  subtitle,
  schoolId,
  isAuthenticated,
  onAuthChange,
  actions,
  children,
  headerMode = "default",
  mainClassName
}: Props) {
  const pathname = usePathname();
  const t = useTranslations("shell");
  const tNav = useTranslations("nav");

  return (
    <main className="dashboard-app">
      <aside className="dashboard-sidebar">
        <div className="dashboard-sidebar-inner">
          <div className="brand-block">
            <div className="brand-logo">✦</div>
            <div>
              <p className="brand-name">Atlas</p>
              <p className="brand-subtitle">School OS</p>
            </div>
          </div>
          <nav className="side-nav">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`side-nav-item ${pathname === item.href ? "active" : ""}`}
                aria-current={pathname === item.href ? "page" : undefined}
              >
                {tNav(item.labelKey)}
              </Link>
            ))}
          </nav>
        </div>
      </aside>

      <section className={`dashboard-main${mainClassName ? ` ${mainClassName}` : ""}`}>
        <header className={`dashboard-topbar${headerMode === "schedule" ? " dashboard-topbar--schedule" : ""}`}>
          <div className="dashboard-topbar__lead">
            <h1 className="page-title">{title}</h1>
            <p className="page-subtitle">{subtitle}</p>
          </div>
          {headerMode === "schedule" ? (
            <LoginBar sessionActive={isAuthenticated} onAuthChange={onAuthChange} variant="mini" />
          ) : (
            <div className="toolbar-row">
              <span className="metric-chip">{t("schoolMetric", {schoolId})}</span>
              <LanguageSwitcher />
              {actions}
            </div>
          )}
        </header>

        {headerMode === "schedule" ? null : <LoginBar sessionActive={isAuthenticated} onAuthChange={onAuthChange} />}

        {!isAuthenticated && headerMode === "schedule" ? (
          <p className="schedule-signin-hint text-sm text-slate-600">{t("signInHint")}</p>
        ) : null}

        {isAuthenticated ? (
          children
        ) : headerMode === "schedule" ? null : (
          <section className="section-card">
            <p className="text-sm text-slate-600">
              {t("signInHint")}
            </p>
          </section>
        )}
      </section>
    </main>
  );
}
