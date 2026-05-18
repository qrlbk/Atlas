"use client";

import { use } from "react";
import { SchoolDetailView } from "@/components/admin/SchoolDetailView";

export default function AdminSchoolDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const schoolId = Number(id);
  if (!Number.isFinite(schoolId)) {
    return <p>Invalid school id</p>;
  }
  return <SchoolDetailView schoolId={schoolId} />;
}
