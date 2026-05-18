"use client";

import { useTranslations } from "next-intl";
import { AdminUser } from "@/lib/api";

export function SchoolUsersTable({ users }: { users: AdminUser[] }) {
  const t = useTranslations("admin.school");
  return (
    <section className="section-card">
      <h3>{t("users")}</h3>
      <table className="admin-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Email</th>
            <th>Name</th>
            <th>Role</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.email}</td>
              <td>{u.full_name}</td>
              <td>{u.role}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
