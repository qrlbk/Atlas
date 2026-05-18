"use client";

import { FormEvent, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";

type Props = {
  schoolId: number;
  onActivated: () => void;
};

export function BillingNoteForm({ schoolId, onActivated }: Props) {
  const t = useTranslations("admin.billing");
  const [status, setStatus] = useState("pending");
  const [amount, setAmount] = useState("");
  const [period, setPeriod] = useState("year");
  const [busy, setBusy] = useState(false);

  async function onMarkPaid(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const until = new Date();
      if (period === "year") until.setFullYear(until.getFullYear() + 1);
      else until.setMonth(until.getMonth() + 1);
      await api.adminActivatePro(schoolId, {
        until: until.toISOString(),
        amount_kzt: amount ? Number(amount) : undefined,
        period_label: period
      });
      await api.adminPatchSchool(schoolId, {
        billing: {
          status,
          amount_kzt: amount ? Number(amount) : undefined,
          period_label: period
        }
      });
      onActivated();
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onMarkPaid} className="section-card" style={{ marginTop: "0.5rem" }}>
      <h4>{t("title")}</h4>
      <div className="admin-filters">
        <label>
          {t("status")}
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="pending">pending</option>
            <option value="paid">paid</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
        <label>
          {t("amount")}
          <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label>
          {t("period")}
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="month">month</option>
            <option value="year">year</option>
          </select>
        </label>
        <button type="submit" className="btn-schedule-primary" disabled={busy}>
          {t("markPaid")}
        </button>
      </div>
    </form>
  );
}
