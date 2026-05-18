"use client";

import { ReactNode, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { AdminShell } from "@/components/admin/AdminShell";
import { LoginBar } from "@/components/LoginBar";
import { api, hasAuthToken, MeUser } from "@/lib/api";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("admin");
  const router = useRouter();
  const [sessionActive, setSessionActive] = useState(false);
  const [me, setMe] = useState<MeUser | null>(null);
  const [checking, setChecking] = useState(true);

  const refreshAuth = useCallback(() => {
    setSessionActive(hasAuthToken());
  }, []);

  useEffect(() => {
    refreshAuth();
    const onExpired = () => refreshAuth();
    window.addEventListener("atlas-auth-expired", onExpired);
    return () => window.removeEventListener("atlas-auth-expired", onExpired);
  }, [refreshAuth]);

  useEffect(() => {
    if (!sessionActive) {
      setMe(null);
      setChecking(false);
      return;
    }
    setChecking(true);
    api
      .authMe()
      .then((user) => {
        if (user.role !== "admin") {
          router.replace("/");
          return;
        }
        setMe(user);
      })
      .catch(() => {
        setMe(null);
      })
      .finally(() => setChecking(false));
  }, [sessionActive, router]);

  if (!sessionActive) {
    return (
      <div className="admin-main" style={{ maxWidth: 480, margin: "2rem auto" }}>
        <h1>{t("title")}</h1>
        <p style={{ margin: "0.75rem 0 1rem", color: "var(--text-muted)" }}>{t("forbidden")}</p>
        <LoginBar sessionActive={sessionActive} onAuthChange={refreshAuth} />
      </div>
    );
  }

  if (checking || !me) {
    return <div className="admin-main" style={{ padding: "2rem" }}>{t("loading")}</div>;
  }

  return (
    <AdminShell email={me.email} onLogout={() => refreshAuth()}>
      {children}
    </AdminShell>
  );
}
