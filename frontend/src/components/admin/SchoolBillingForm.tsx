"use client";

import { FormEvent, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { AdminSchoolDetail, api } from "@/lib/api";
import { BillingNoteForm } from "./BillingNoteForm";

type Props = {
  detail: AdminSchoolDetail;
  onUpdated: () => void;
};

function toInputDate(iso: string | null) {
  if (!iso) return "";
  return iso.slice(0, 10);
}

export function SchoolBillingForm({ detail, onUpdated }: Props) {
  const t = useTranslations("admin.school");
  const school = detail.school;
  const [name, setName] = useState(school.name);
  const [address, setAddress] = useState(school.address);
  const [plan, setPlan] = useState(school.plan);
  const [trialEnds, setTrialEnds] = useState(toInputDate(school.trial_ends_at));
  const [subscriptionEnds, setSubscriptionEnds] = useState(toInputDate(school.subscription_ends_at));
  const [manualPro, setManualPro] = useState(detail.manual_pro);
  const [adminNotes, setAdminNotes] = useState(detail.admin_notes ?? "");

  useEffect(() => {
    setName(school.name);
    setAddress(school.address);
    setPlan(school.plan);
    setTrialEnds(toInputDate(school.trial_ends_at));
    setSubscriptionEnds(toInputDate(school.subscription_ends_at));
    setManualPro(detail.manual_pro);
    setAdminNotes(detail.admin_notes ?? "");
  }, [detail, school]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      await api.adminPatchSchool(school.id, {
        name,
        address,
        plan,
        trial_ends_at: trialEnds ? `${trialEnds}T12:00:00` : null,
        subscription_ends_at: subscriptionEnds ? `${subscriptionEnds}T12:00:00` : null,
        manual_pro: manualPro,
        admin_notes: adminNotes
      });
      setMessage(t("saved"));
      onUpdated();
    } catch {
      setMessage(t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function extendTrial() {
    await api.adminExtendTrial(school.id, 14);
    onUpdated();
  }

  async function activateProYear() {
    const until = new Date();
    until.setFullYear(until.getFullYear() + 1);
    await api.adminActivatePro(school.id, { until: until.toISOString() });
    onUpdated();
  }

  return (
    <section className="section-card admin-detail-grid">
      <h3>{t("billing")}</h3>
      <form onSubmit={save} className="admin-detail-grid">
        <label>
          {t("name")}
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          {t("address")}
          <input value={address} onChange={(e) => setAddress(e.target.value)} required />
        </label>
        <label>
          {t("plan")}
          <select value={plan} onChange={(e) => setPlan(e.target.value)}>
            <option value="free">free</option>
            <option value="pro">pro</option>
          </select>
        </label>
        <label>
          {t("trialEnds")}
          <input type="date" value={trialEnds} onChange={(e) => setTrialEnds(e.target.value)} />
        </label>
        <label>
          {t("subscriptionEnds")}
          <input
            type="date"
            value={subscriptionEnds}
            onChange={(e) => setSubscriptionEnds(e.target.value)}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input
            type="checkbox"
            checked={manualPro}
            onChange={(e) => setManualPro(e.target.checked)}
          />
          {t("manualPro")}
        </label>
        <label>
          {t("adminNotes")}
          <textarea
            rows={3}
            value={adminNotes}
            onChange={(e) => setAdminNotes(e.target.value)}
            style={{ width: "100%", minHeight: 80 }}
          />
        </label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          <button type="submit" className="btn-schedule-primary" disabled={saving}>
            {t("save")}
          </button>
          <button type="button" className="btn-schedule-secondary" onClick={() => void extendTrial()}>
            {t("extendTrial")}
          </button>
          <button type="button" className="btn-schedule-secondary" onClick={() => void activateProYear()}>
            {t("activateProYear")}
          </button>
        </div>
        {message && <p>{message}</p>}
      </form>
      <BillingNoteForm schoolId={school.id} onActivated={onUpdated} />
    </section>
  );
}
