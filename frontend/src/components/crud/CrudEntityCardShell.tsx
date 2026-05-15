"use client";

import type { ReactNode } from "react";

export type CrudEntityCardStatus = "ok" | "bad";

export type CrudEntityCardShellProps = {
  title: ReactNode;
  meta?: ReactNode;
  progress: {
    actual: number;
    max: number;
    percent: number;
    over?: boolean;
    caption: string;
  };
  statEmphasis: ReactNode;
  status: CrudEntityCardStatus;
  statusLabel: string;
  extra?: ReactNode;
  /** When false, card is read-only (no edit/delete row). */
  showActions?: boolean;
  onEdit?: () => void;
  onDelete?: () => void;
  deleteDisabled?: boolean;
  editLabel?: string;
  deleteLabel?: string;
  busy?: boolean;
};

export function CrudEntityCardShell({
  title,
  meta,
  progress,
  statEmphasis,
  status,
  statusLabel,
  extra,
  showActions = true,
  onEdit,
  onDelete,
  deleteDisabled,
  editLabel,
  deleteLabel,
  busy
}: CrudEntityCardShellProps) {
  const maxAria = progress.max > 0 ? progress.max : 100;
  const hasActions =
    showActions !== false && onEdit && onDelete && editLabel != null && editLabel !== "" && deleteLabel != null && deleteLabel !== "";
  return (
    <li className={`interactive-card saas-entity-card ${busy ? "busy-state" : ""}`} tabIndex={0}>
      <div className="saas-entity-card__head">
        <h3 className="saas-entity-card__title">{title}</h3>
        {meta ? <div className="saas-entity-card__meta">{meta}</div> : null}
      </div>

      <div className="saas-entity-card__progress-row">
        <div
          className="saas-progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={maxAria}
          aria-valuenow={progress.actual}
          aria-label={progress.caption}
        >
          <div
            className={`saas-progress-fill ${progress.over ? "saas-progress-fill--over" : ""}`}
            style={{ width: `${Math.min(100, Math.max(0, progress.percent))}%` }}
          />
        </div>
        <span className="saas-progress-caption">{progress.caption}</span>
      </div>

      <p className="saas-entity-card__emphasis">{statEmphasis}</p>

      <span className={`status-pill ${status === "ok" ? "status-pill--success" : "status-pill--danger"}`}>{statusLabel}</span>
      {extra ? <div className="saas-entity-card__meta">{extra}</div> : null}

      {hasActions ? (
        <div className="saas-entity-card__actions">
          <button type="button" className="btn-saas-edit focus-ring-strong" onClick={onEdit}>
            <span className="btn-saas-ico" aria-hidden>
              ✏️
            </span>{" "}
            {editLabel}
          </button>
          <button type="button" className="btn-saas-delete focus-ring-strong" disabled={deleteDisabled} onClick={onDelete}>
            <span className="btn-saas-ico" aria-hidden>
              🗑️
            </span>{" "}
            {deleteLabel}
          </button>
        </div>
      ) : null}
    </li>
  );
}
