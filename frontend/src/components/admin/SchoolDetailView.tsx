"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api, AdminSchoolDetail } from "@/lib/api";
import { HealthBadge } from "./HealthBadge";
import { SchoolBillingForm } from "./SchoolBillingForm";
import { SchoolUsersTable } from "./SchoolUsersTable";
import { SchoolEventsList } from "./SchoolEventsList";

export function SchoolDetailView({ schoolId }: { schoolId: number }) {
  const t = useTranslations("admin.school");
  const [detail, setDetail] = useState<AdminSchoolDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    api
      .adminGetSchool(schoolId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [schoolId]);

  useEffect(() => {
    reload();
  }, [reload]);

  if (loading || !detail) {
    return <p>{t("billing")}…</p>;
  }

  return (
    <div className="admin-detail-grid">
      <div className="admin-header">
        <div>
          <Link href="/admin/schools">{t("back")}</Link>
          <h2 style={{ marginTop: "0.35rem" }}>
            #{detail.school.id} {detail.school.name}
          </h2>
        </div>
        <HealthBadge status={detail.readiness.status} />
      </div>

      <SchoolBillingForm key={detail.school.id} detail={detail} onUpdated={reload} />

      <section className="section-card">
        <div className="admin-header">
          <h3>{t("health")}</h3>
          <button type="button" className="btn-schedule-secondary" onClick={() => reload()}>
            {t("refreshHealth")}
          </button>
        </div>
        {detail.readiness.blockers.length > 0 && (
          <ul>
            {detail.readiness.blockers.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        )}
        {detail.readiness.recommendations.length > 0 && (
          <ul style={{ marginTop: "0.5rem", color: "var(--text-muted)" }}>
            {detail.readiness.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        )}
      </section>

      {detail.usage.length > 0 && (
        <section className="section-card">
          <h3>{t("usage")}</h3>
          <ul className="compact-list">
            {detail.usage.map((u) => (
              <li key={u.metric} className="compact-row">
                <span>{u.metric}</span>
                <strong>{u.count}</strong>
              </li>
            ))}
          </ul>
        </section>
      )}

      {detail.snapshots.length > 0 && (
        <section className="section-card">
          <h3>{t("snapshots")}</h3>
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Label</th>
                <th>Reason</th>
                <th>Items</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {detail.snapshots.map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{s.label}</td>
                  <td>{s.reason}</td>
                  <td>{s.item_count}</td>
                  <td>{new Date(s.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <SchoolUsersTable users={detail.users} />
      <SchoolEventsList schoolId={schoolId} />
    </div>
  );
}
