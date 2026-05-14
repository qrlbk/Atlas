"use client";

import { useEffect, useMemo, useState } from "react";
import { api, StudentClass } from "@/lib/api";
import { ScheduleBuilder } from "@/components/ScheduleBuilder";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { useDashboardState } from "@/components/dashboard/useDashboardState";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useTranslations } from "next-intl";

export default function SchedulePage() {
  const { schoolId, refreshKey, isAuthenticated, bump } = useDashboardState();
  const t = useTranslations("pages.schedule");
  const tShell = useTranslations("shell");
  const [classes, setClasses] = useState<StudentClass[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [selectedWeek, setSelectedWeek] = useState("week1");
  const [pendingSlotFocus, setPendingSlotFocus] = useState<string | null>(null);
  const selectedClassLabel = useMemo(
    () => classes.find((item) => item.id === selectedClassId)?.class_name ?? t("none"),
    [classes, selectedClassId, t]
  );
  const classNameById = useMemo(
    () => Object.fromEntries(classes.map((c) => [c.id, c.class_name])) as Record<number, string>,
    [classes]
  );

  useEffect(() => {
    if (!isAuthenticated) {
      setClasses([]);
      setSelectedClassId(null);
      return;
    }
    void api
      .listClasses(schoolId)
      .then((items) => {
        setClasses(items);
        setSelectedClassId((prev) => (prev != null && items.some((c) => c.id === prev) ? prev : items[0]?.id ?? null));
      })
      .catch(() => {
        setClasses([]);
        setSelectedClassId(null);
      });
  }, [schoolId, isAuthenticated]);

  const filterSlot = (
    <>
      <select
        aria-label={t("classPicker")}
        value={selectedClassId ?? ""}
        onChange={(event) => {
          const nextId = Number(event.target.value);
          if (isDirty) {
            const shouldSwitch = window.confirm(t("switchConfirm"));
            if (!shouldSwitch) return;
          }
          setPendingSlotFocus(null);
          setSelectedClassId(nextId);
        }}
        className="schedule-filter-select focus-ring-strong"
      >
        {classes.map((item) => (
          <option key={item.id} value={item.id}>
            {item.class_name}
          </option>
        ))}
      </select>
      <select
        aria-label={t("weekPicker")}
        value={selectedWeek}
        onChange={(event) => setSelectedWeek(event.target.value)}
        className="schedule-filter-select focus-ring-strong"
      >
        <option value="week1">{t("week1")}</option>
        <option value="week2">{t("week2")}</option>
        <option value="week3">{t("week3")}</option>
      </select>
      <LanguageSwitcher />
    </>
  );

  function handleNavigateToClassAndSlot(classId: number, slotKey: string) {
    if (isDirty) {
      const ok = window.confirm(t("switchConfirm"));
      if (!ok) return;
    }
    setPendingSlotFocus(slotKey);
    setSelectedClassId(classId);
  }

  return (
    <DashboardShell
      headerMode="schedule"
      mainClassName="dashboard-main--schedule-tight"
      title={t("title")}
      subtitle={t("subtitle")}
      schoolId={schoolId}
      isAuthenticated={isAuthenticated}
      onAuthChange={bump}
    >
      {selectedClassId ? (
        <ScheduleBuilder
          key={`schedule-${refreshKey}-${selectedClassId}`}
          schoolId={schoolId}
          selectedClassId={selectedClassId}
          selectedClassLabel={selectedClassLabel}
          schoolLabel={tShell("schoolMetric", { schoolId })}
          filterSlot={filterSlot}
          classNameById={classNameById}
          pendingSlotFocus={pendingSlotFocus}
          onPendingSlotFocusConsumed={() => setPendingSlotFocus(null)}
          onNavigateToClassAndSlot={handleNavigateToClassAndSlot}
          onDirtyChange={setIsDirty}
        />
      ) : (
        <p className="empty-note">{t("empty")}</p>
      )}
    </DashboardShell>
  );
}
