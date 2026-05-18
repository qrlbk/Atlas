"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api, AdminEvent } from "@/lib/api";

export function SchoolEventsList({ schoolId }: { schoolId: number }) {
  const t = useTranslations("admin.school");
  const [items, setItems] = useState<AdminEvent[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [eventType, setEventType] = useState("");

  useEffect(() => {
    api
      .adminSchoolEvents(schoolId, {
        page,
        page_size: 30,
        event_type: eventType || undefined
      })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch(() => setItems([]));
  }, [schoolId, page, eventType]);

  return (
    <section className="section-card">
      <h3>{t("events")}</h3>
      <input
        placeholder="event_type"
        value={eventType}
        onChange={(e) => {
          setPage(1);
          setEventType(e.target.value);
        }}
        style={{ marginBottom: "0.5rem" }}
      />
      <table className="admin-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Type</th>
            <th>Payload</th>
          </tr>
        </thead>
        <tbody>
          {items.map((e) => (
            <tr key={e.id}>
              <td>{new Date(e.created_at).toLocaleString()}</td>
              <td>{e.event_type}</td>
              <td>
                <code style={{ fontSize: "0.75rem" }}>
                  {JSON.stringify(e.payload ?? {})}
                </code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
        <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          ←
        </button>
        <span>
          {page} / {Math.max(1, Math.ceil(total / 30))}
        </span>
        <button type="button" disabled={page * 30 >= total} onClick={() => setPage((p) => p + 1)}>
          →
        </button>
      </div>
    </section>
  );
}
