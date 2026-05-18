"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api, AdminSchoolCreateResponse } from "@/lib/api";

export default function AdminCreateSchoolPage() {
  const t = useTranslations("admin.create");
  const [result, setResult] = useState<AdminSchoolCreateResponse | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    try {
      const res = await api.adminCreateSchool({
        name: String(fd.get("name")),
        address: String(fd.get("address")),
        manager_email: String(fd.get("manager_email")),
        manager_full_name: String(fd.get("manager_full_name")),
        trial_days: Number(fd.get("trial_days") || 14)
      });
      setResult(res);
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <section className="section-card">
        <h2>{t("passwordTitle")}</h2>
        <p style={{ color: "var(--danger)", margin: "0.5rem 0" }}>{t("passwordWarning")}</p>
        <p>
          <strong>{result.manager_email}</strong>
        </p>
        <code
          style={{
            display: "block",
            padding: "0.75rem",
            background: "#f8fafc",
            borderRadius: 8,
            margin: "0.5rem 0"
          }}
        >
          {result.manager_password}
        </code>
        <Link href={`/admin/schools/${result.school_id}`} className="btn-schedule-primary">
          {t("goToSchool")}
        </Link>
      </section>
    );
  }

  return (
    <section className="section-card admin-detail-grid">
      <h2>{t("title")}</h2>
      <form onSubmit={onSubmit} className="admin-detail-grid">
        <label>
          {t("name")}
          <input name="name" required />
        </label>
        <label>
          {t("address")}
          <input name="address" required />
        </label>
        <label>
          {t("managerEmail")}
          <input name="manager_email" type="email" required />
        </label>
        <label>
          {t("managerName")}
          <input name="manager_full_name" required />
        </label>
        <label>
          {t("trialDays")}
          <input name="trial_days" type="number" defaultValue={14} min={1} />
        </label>
        <button type="submit" className="btn-schedule-primary" disabled={busy}>
          {t("submit")}
        </button>
      </form>
    </section>
  );
}
