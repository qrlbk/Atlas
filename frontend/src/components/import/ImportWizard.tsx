"use client";

import { ChangeEvent, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  api,
  CommitImportResponse,
  hasAuthToken,
  ImportIssue,
  ImportMode,
  ImportSheetStats,
  ValidateImportResponse
} from "@/lib/api";

type Props = { schoolId: number };

type Stage = "idle" | "validating" | "preview" | "committing" | "done";

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function ImportWizard({ schoolId }: Props) {
  const t = useTranslations("imports");
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<ValidateImportResponse | null>(null);
  const [commitResult, setCommitResult] = useState<CommitImportResponse | null>(null);
  const [modes, setModes] = useState<Record<string, ImportMode>>({});
  const [stage, setStage] = useState<Stage>("idle");
  const [feedback, setFeedback] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  const totalIssues = validation?.issues.length ?? 0;
  const errorCount = validation?.summary.error_count ?? 0;
  const warningCount = validation?.summary.warning_count ?? 0;
  const canCommit = Boolean(validation && validation.can_commit && stage !== "committing");

  const errorIssues = useMemo(
    () => (validation?.issues ?? []).filter((issue) => issue.severity === "error"),
    [validation]
  );
  const warningIssues = useMemo(
    () => (validation?.issues ?? []).filter((issue) => issue.severity === "warning"),
    [validation]
  );

  async function handleDownloadTemplate() {
    if (!hasAuthToken()) {
      setFeedback({ type: "error", text: t("authRequired") });
      return;
    }
    setFeedback(null);
    try {
      const blob = await api.downloadImportTemplate(schoolId);
      downloadBlob(blob, `atlas_import_template_school_${schoolId}.xlsx`);
      setFeedback({ type: "success", text: t("templateDownloaded") });
    } catch {
      setFeedback({ type: "error", text: t("templateFailed") });
    }
  }

  function handleFilePick(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0] ?? null;
    setFile(picked);
    setValidation(null);
    setCommitResult(null);
    setStage("idle");
    setFeedback(null);
    setModes({});
  }

  async function handleValidate() {
    if (!file) return;
    setStage("validating");
    setFeedback(null);
    setCommitResult(null);
    try {
      const response = await api.validateImport(schoolId, file);
      setValidation(response);
      const defaultModes: Record<string, ImportMode> = {};
      response.summary.sheets.forEach((sheet) => {
        defaultModes[sheet.sheet] = sheet.default_mode;
      });
      setModes(defaultModes);
      setStage("preview");
    } catch {
      setFeedback({ type: "error", text: t("validateFailed") });
      setStage("idle");
    }
  }

  async function handleCommit() {
    if (!file || !canCommit) return;
    setStage("committing");
    setFeedback(null);
    try {
      const response = await api.commitImport(schoolId, file, modes);
      setCommitResult(response);
      if (response.committed) {
        setFeedback({ type: "success", text: t("commitDone") });
        setStage("done");
      } else {
        setFeedback({ type: "error", text: t("commitBlocked") });
        setStage("preview");
      }
    } catch {
      setFeedback({ type: "error", text: t("commitFailed") });
      setStage("preview");
    }
  }

  function handleModeChange(sheet: string, mode: ImportMode) {
    setModes((prev) => ({ ...prev, [sheet]: mode }));
  }

  function handleReset() {
    setFile(null);
    setValidation(null);
    setCommitResult(null);
    setModes({});
    setStage("idle");
    setFeedback(null);
  }

  return (
    <section className="section-card space-y-3">
      <header className="space-y-1">
        <h2 className="section-title">{t("title")}</h2>
        <p className="section-subtitle">{t("subtitle")}</p>
      </header>

      <ol className="import-wizard-steps">
        <li>
          <strong>1. {t("step1Title")}</strong>
          <p className="section-subtitle">{t("step1Subtitle")}</p>
          <button type="button" className="btn-primary focus-ring-strong" onClick={handleDownloadTemplate}>
            {t("downloadTemplate")}
          </button>
        </li>
        <li>
          <strong>2. {t("step2Title")}</strong>
          <p className="section-subtitle">{t("step2Subtitle")}</p>
          <input
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={handleFilePick}
          />
          <button
            type="button"
            className="btn-primary focus-ring-strong"
            disabled={!file || stage === "validating"}
            onClick={handleValidate}
          >
            {stage === "validating" ? t("validating") : t("validate")}
          </button>
        </li>
      </ol>

      {feedback ? <p className={`inline-feedback ${feedback.type}`}>{feedback.text}</p> : null}

      {validation ? (
        <article className="space-y-3">
          <header className="space-y-1">
            <h3 className="section-title">{t("previewTitle")}</h3>
            <p className="section-subtitle">
              {t("previewSummary", { errors: errorCount, warnings: warningCount, total: totalIssues })}
            </p>
          </header>

          <div className="saas-grid-host">
            <table className="import-summary-table">
              <thead>
                <tr>
                  <th>{t("colSheet")}</th>
                  <th>{t("colRows")}</th>
                  <th>{t("colCreate")}</th>
                  <th>{t("colUpdate")}</th>
                  <th>{t("colReplace")}</th>
                  <th>{t("colSkip")}</th>
                  <th>{t("colErrors")}</th>
                  <th>{t("colMode")}</th>
                </tr>
              </thead>
              <tbody>
                {validation.summary.sheets.map((sheet) => (
                  <SheetRow
                    key={sheet.sheet}
                    sheet={sheet}
                    mode={modes[sheet.sheet] ?? sheet.default_mode}
                    onChange={(mode) => handleModeChange(sheet.sheet, mode)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {errorIssues.length > 0 ? (
            <details open className="space-y-2">
              <summary className="section-title">{t("errorsHeading", { count: errorIssues.length })}</summary>
              <IssuesList issues={errorIssues} />
            </details>
          ) : null}

          {warningIssues.length > 0 ? (
            <details className="space-y-2">
              <summary className="section-title">{t("warningsHeading", { count: warningIssues.length })}</summary>
              <IssuesList issues={warningIssues} />
            </details>
          ) : null}

          <div className="crud-form-actions">
            <button
              type="button"
              className="btn-primary focus-ring-strong"
              disabled={!canCommit}
              onClick={handleCommit}
            >
              {stage === "committing" ? t("committing") : t("commit")}
            </button>
            <button type="button" className="btn-secondary focus-ring-strong" onClick={handleReset}>
              {t("reset")}
            </button>
          </div>
          {!canCommit && validation && !validation.can_commit ? (
            <p className="inline-feedback error">{t("fixErrorsFirst")}</p>
          ) : null}
        </article>
      ) : null}

      {commitResult ? (
        <article className="space-y-3">
          <header className="space-y-1">
            <h3 className="section-title">{t("resultTitle")}</h3>
            <p className="section-subtitle">
              {commitResult.committed ? t("resultCommitted") : t("resultNotCommitted")}
            </p>
          </header>
          <ul className="compact-list">
            {commitResult.applied.map((row) => (
              <li key={row.sheet} className="compact-row">
                <span className="font-medium text-slate-800">{row.sheet}</span>
                <span className="status-pill ok">
                  {t("resultLine", {
                    mode: row.mode,
                    created: row.created,
                    updated: row.updated,
                    deleted: row.deleted,
                    skipped: row.skipped
                  })}
                </span>
              </li>
            ))}
          </ul>
        </article>
      ) : null}
    </section>
  );
}

function SheetRow({
  sheet,
  mode,
  onChange
}: {
  sheet: ImportSheetStats;
  mode: ImportMode;
  onChange: (mode: ImportMode) => void;
}) {
  return (
    <tr>
      <td>{sheet.sheet}</td>
      <td>{sheet.rows_total}</td>
      <td>{sheet.rows_to_create}</td>
      <td>{sheet.rows_to_update}</td>
      <td>{sheet.rows_to_replace}</td>
      <td>{sheet.rows_to_skip}</td>
      <td>{sheet.rows_with_errors}</td>
      <td>
        <select
          value={mode}
          onChange={(event) => onChange(event.target.value as ImportMode)}
          aria-label={`${sheet.sheet}-mode`}
        >
          {sheet.allowed_modes.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </td>
    </tr>
  );
}

function IssuesList({ issues }: { issues: ImportIssue[] }) {
  return (
    <ul className="compact-list">
      {issues.slice(0, 200).map((issue, idx) => (
        <li key={`${issue.sheet}-${issue.row ?? "x"}-${idx}`} className="compact-row">
          <span className="font-medium text-slate-800">
            {issue.sheet}
            {issue.row != null ? ` · row ${issue.row}` : ""}
            {issue.column ? ` · ${issue.column}` : ""}
          </span>
          <span className={`status-pill ${issue.severity === "error" ? "bad" : "warning"}`}>{issue.message}</span>
        </li>
      ))}
    </ul>
  );
}
