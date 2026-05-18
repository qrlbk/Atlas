"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { api, AdminDashboard } from "@/lib/api";
import { HealthBadge } from "@/components/admin/HealthBadge";

function reasonLabel(tReason: (k: string) => string, code: string) {
  const map: Record<string, string> = {
    readiness_red: "readiness_red",
    trial_expiring: "trial_expiring",
    inactive: "inactive"
  };
  const k = map[code];
  return k ? tReason(k) : code;
}

export default function AdminDashboardPage() {
  const t = useTranslations("admin.dashboard");
  const tReason = useTranslations("admin.dashboard.reason");
  const router = useRouter();
  const [data, setData] = useState<AdminDashboard | null>(null);

  useEffect(() => {
    api.adminDashboard().then(setData).catch(() => setData(null));
  }, []);

  if (!data) {
    return <p>{t("title")}…</p>;
  }

  const kpis = [
    { label: t("totalSchools"), value: data.total_schools },
    { label: t("free"), value: data.free_count },
    { label: t("pro"), value: data.pro_count },
    { label: t("trialActive"), value: data.trial_active_count },
    { label: t("readinessRed"), value: data.readiness_red_count },
    { label: t("events24h"), value: data.events_last_24h }
  ];

  return (
    <>
      <div className="admin-header">
        <h2>{t("title")}</h2>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <Link href="/admin/schools" className="btn-schedule-secondary">
            {t("allSchools")}
          </Link>
          <Link href="/admin/schools/new" className="btn-schedule-primary">
            {t("createSchool")}
          </Link>
        </div>
      </div>

      <div
        className="kpi-grid"
        style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))", marginBottom: "1rem" }}
      >
        {kpis.map((k) => (
          <div key={k.label} className="kpi-tile section-card">
            <p>{k.label}</p>
            <strong>{k.value}</strong>
          </div>
        ))}
      </div>

      <section className="section-card">
        <h3>{t("attention")}</h3>
        {data.attention.length === 0 ? (
          <p style={{ marginTop: "0.5rem", color: "var(--text-muted)" }}>{t("noAttention")}</p>
        ) : (
          <div className="admin-table-wrap" style={{ marginTop: "0.75rem" }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t("allSchools")}</th>
                  <th>Plan</th>
                  <th>Health</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {data.attention.map((row) => (
                  <tr
                    key={row.school_id}
                    onClick={() => router.push(`/admin/schools/${row.school_id}`)}
                  >
                    <td>{row.school_id}</td>
                    <td>{row.school_name}</td>
                    <td>{row.plan}</td>
                    <td>
                      <HealthBadge status={row.readiness_status} />
                    </td>
                    <td>
                      {row.reason.split(",").map((r) => (
                        <span key={r} style={{ marginRight: "0.35rem" }}>
                          {reasonLabel(tReason, r.trim())}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
