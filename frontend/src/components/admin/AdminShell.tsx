"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { clearStoredToken } from "@/lib/api";

type Props = {
  children: ReactNode;
  email: string;
  onLogout: () => void;
};

export function AdminShell({ children, email, onLogout }: Props) {
  const t = useTranslations("admin");
  const pathname = usePathname();

  function handleLogout() {
    clearStoredToken();
    onLogout();
  }

  const nav = [
    { href: "/admin", label: t("nav.dashboard"), exact: true },
    { href: "/admin/schools", label: t("nav.schools"), exact: false }
  ];

  return (
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <h1>{t("title")}</h1>
        <nav className="admin-nav">
          {nav.map((item) => {
            const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href} className={active ? "active" : undefined}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div style={{ marginTop: "auto", fontSize: "0.8rem", opacity: 0.85 }}>{email}</div>
        <button type="button" className="btn-schedule-ghost" onClick={handleLogout}>
          {t("nav.logout")}
        </button>
      </aside>
      <main className="admin-main">{children}</main>
    </div>
  );
}
