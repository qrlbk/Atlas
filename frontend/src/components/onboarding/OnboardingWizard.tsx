"use client";

import { ChangeEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";
import {
  api,
  ApiError,
  CommitImportResponse,
  hasAuthToken,
  ValidateImportResponse
} from "@/lib/api";
import { UpgradePanel } from "@/components/UpgradePanel";

type Props = { schoolId: number };

type Stage = "upload" | "validating" | "preview" | "committing" | "done";

export function OnboardingWizard({ schoolId }: Props) {
  const t = useTranslations("onboarding");
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<ValidateImportResponse | null>(null);
  const [stage, setStage] = useState<Stage>("upload");
  const [error, setError] = useState<string | null>(null);
  const [upgradeCapability, setUpgradeCapability] = useState<string | null>(null);

  const modes = api.onboardingImportModes();

  function handleFilePick(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setValidation(null);
    setStage("upload");
    setError(null);
  }

  async function handleValidate() {
    if (!file || !hasAuthToken()) return;
    setStage("validating");
    setError(null);
    try {
      const res = await api.validateImport(schoolId, file, modes);
      setValidation(res);
      setStage("preview");
    } catch {
      setError(t("validateFailed"));
      setStage("upload");
    }
  }

  async function handleCommit() {
    if (!file || !validation?.can_commit) return;
    setStage("committing");
    setError(null);
    setUpgradeCapability(null);
    try {
      const res: CommitImportResponse = await api.commitImport(schoolId, file, modes);
      if (!res.committed) {
        setError(t("commitBlocked"));
        setStage("preview");
        return;
      }
      setStage("done");
      router.push("/schedule");
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        setUpgradeCapability("import_schedule");
        setStage("preview");
        return;
      }
      setError(t("commitFailed"));
      setStage("preview");
    }
  }

  const preview = validation?.summary.entity_preview ?? {};
  const buckets = validation?.summary.issue_buckets ?? {};

  return (
    <section className="onboarding-wizard section-card">
      <h2 className="section-title">{t("title")}</h2>
      <p className="section-subtitle">{t("subtitle")}</p>
      <ol className="onboarding-steps">
        <li className={stage !== "upload" ? "done" : "active"}>{t("stepUpload")}</li>
        <li className={stage === "preview" || stage === "committing" || stage === "done" ? "done" : ""}>{t("stepPreview")}</li>
        <li className={stage === "done" ? "done" : ""}>{t("stepStart")}</li>
      </ol>

      <div className="onboarding-upload">
        <input type="file" accept=".xlsx" onChange={handleFilePick} />
        <button type="button" className="btn-schedule-secondary" disabled={!file || stage === "validating"} onClick={() => void handleValidate()}>
          {stage === "validating" ? t("validating") : t("validate")}
        </button>
        <Link href="/workspace" className="btn-schedule-ghost">
          {t("manualSetup")}
        </Link>
      </div>

      {upgradeCapability ? <UpgradePanel capability={upgradeCapability} onDismiss={() => setUpgradeCapability(null)} /> : null}

      {validation && stage !== "upload" ? (
        <article className="onboarding-preview">
          <h3 className="section-title">{t("previewTitle")}</h3>
          <ul className="compact-list">
            <li>{t("countTeachers", { count: preview.teachers ?? 0 })}</li>
            <li>{t("countClasses", { count: preview.classes ?? 0 })}</li>
            <li>{t("countCurriculum", { count: preview.curriculum ?? preview.curriculum_hours ?? 0 })}</li>
          </ul>
          {buckets.total ? (
            <p className="metric-chip subtle">
              {t("issueSummary", {
                total: buckets.total ?? 0,
                review: buckets.needs_review ?? 0
              })}
            </p>
          ) : null}
          {!validation.can_commit ? <p className="status-pill warning">{t("fixErrorsFirst")}</p> : null}
          <button
            type="button"
            className="btn-schedule-primary"
            disabled={!validation.can_commit || stage === "committing"}
            onClick={() => void handleCommit()}
          >
            {stage === "committing" ? t("committing") : t("startBuilding")}
          </button>
        </article>
      ) : null}

      {error ? <p className="status-pill warning">{error}</p> : null}
    </section>
  );
}
