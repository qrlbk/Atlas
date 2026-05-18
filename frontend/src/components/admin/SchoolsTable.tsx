"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { api, AdminSchoolListItem } from "@/lib/api";
import { HealthBadge } from "./HealthBadge";

type Props = {
  initialPlan?: string;
  initialHealth?: string;
};

function formatDate(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export function SchoolsTable({ initialPlan, initialHealth }: Props) {
  const t = useTranslations("admin.schools");
  const router = useRouter();
  const [items, setItems] = useState<AdminSchoolListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [plan, setPlan] = useState(initialPlan ?? "");
  const [health, setHealth] = useState(initialHealth ?? "");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .adminListSchools({
        page,
        page_size: 25,
        q: q || undefined,
        plan: plan || undefined,
        health: health || undefined,
        sort: "name"
      })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [page, q, plan, health]);

  return (
    <section className="section-card">
      <div className="admin-header">
        <h2>{t("title")}</h2>
        <Link href="/admin/schools/new" className="btn-schedule-secondary">
          {t("create")}
        </Link>
      </div>

      <div className="admin-filters">
        <input
          type="search"
          placeholder={t("search")}
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
        />
        <select
          value={plan}
          onChange={(e) => {
            setPage(1);
            setPlan(e.target.value);
          }}
        >
          <option value="">{t("filterPlan")}: {t("all")}</option>
          <option value="free">free</option>
          <option value="pro">pro</option>
        </select>
        <select
          value={health}
          onChange={(e) => {
            setPage(1);
            setHealth(e.target.value);
          }}
        >
          <option value="">{t("filterHealth")}: {t("all")}</option>
          <option value="green">green</option>
          <option value="yellow">yellow</option>
          <option value="red">red</option>
          <option value="unknown">unknown</option>
        </select>
      </div>

      {loading ? (
        <p>{t("title")}…</p>
      ) : items.length === 0 ? (
        <p>{t("empty")}</p>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>{t("colId")}</th>
                <th>{t("colName")}</th>
                <th>{t("colPlan")}</th>
                <th>{t("colPro")}</th>
                <th>{t("colHealth")}</th>
                <th>{t("colTrial")}</th>
                <th>{t("colActivity")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} onClick={() => router.push(`/admin/schools/${row.id}`)}>
                  <td>{row.id}</td>
                  <td>{row.name}</td>
                  <td>{row.plan}</td>
                  <td>{row.pro_access ? "✓" : "—"}</td>
                  <td>
                    <HealthBadge status={row.readiness_status} />
                  </td>
                  <td>{formatDate(row.trial_ends_at)}</td>
                  <td>{formatDate(row.last_event_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem" }}>
        <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          ←
        </button>
        <span>{t("page", { page, total })}</span>
        <button
          type="button"
          disabled={page * 25 >= total}
          onClick={() => setPage((p) => p + 1)}
        >
          →
        </button>
      </div>
    </section>
  );
}
