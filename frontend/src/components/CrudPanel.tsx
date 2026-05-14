"use client";

import { TeachersPanel } from "@/components/crud/TeachersPanel";
import { ClassroomsPanel } from "@/components/crud/ClassroomsPanel";
import { ClassesPanel } from "@/components/crud/ClassesPanel";
import { FlowsPanel } from "@/components/crud/FlowsPanel";
import { CurriculumPanel } from "@/components/crud/CurriculumPanel";

type Props = { schoolId: number };

export function CrudPanel({ schoolId }: Props) {
  return (
    <section className="space-y-6" data-testid="crud-panel">
      <div className="grid gap-4 md:grid-cols-2">
        <TeachersPanel schoolId={schoolId} />
        <ClassroomsPanel schoolId={schoolId} />
        <ClassesPanel schoolId={schoolId} />
        <FlowsPanel schoolId={schoolId} />
      </div>
      <CurriculumPanel schoolId={schoolId} />
    </section>
  );
}
