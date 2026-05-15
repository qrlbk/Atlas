import type { ScheduleItem, ValidationIssue } from "@/lib/api";

/** Mirrors backend ``_is_grouped_joint_booking`` for client-side issue filtering. */
export function isGroupedJointBookingAtSlot(items: ScheduleItem[]): boolean {
  if (items.length < 2) return false;
  if (!items.every((item) => item.is_grouped && item.group_id != null)) return false;
  return new Set(items.map((item) => item.group_id)).size === 1;
}

function lessonSlotIdFromIssue(issue: ValidationIssue): number | null {
  const lid = issue.slot_ref?.lesson_slot_id;
  if (lid == null) return null;
  const n = Number(lid);
  return Number.isFinite(n) ? n : null;
}

/**
 * Drop false-positive teacher/room double-booking issues when grouped flow rows
 * legitimately share the same slot, teacher, and room.
 */
export function filterGroupedJointBookingIssues(
  issues: ValidationIssue[],
  lessons: ScheduleItem[]
): ValidationIssue[] {
  return issues.filter((issue) => {
    if (issue.issue_code !== "TEACHER_DOUBLE_BOOKING" && issue.issue_code !== "CLASSROOM_DOUBLE_BOOKING") {
      return true;
    }
    const slotId = lessonSlotIdFromIssue(issue);
    if (slotId == null) return true;
    const atSlot = lessons.filter((l) => l.lesson_slot_id === slotId);
    if (atSlot.length < 2) return true;
    return !isGroupedJointBookingAtSlot(atSlot);
  });
}
