import { endOfWeek, isToday } from "date-fns";
import type { Task } from "@/types/api";

/**
 * Due-date bucketing shared by the workspace dashboard and the member profile.
 *
 * Mirrors the server vocabulary (contract §10.5): `overdue` is `due_date < now`
 * on a non-closed task, `today`/`this_week` are calendar windows. Bucketing is
 * done on the client rather than with three `due=` requests because those
 * windows overlap — an overdue task is also inside `this_week`.
 */
export type BucketKey = "overdue" | "today" | "week" | "later" | "none";

export const BUCKET_ORDER: BucketKey[] = ["overdue", "today", "week", "later", "none"];

export const BUCKET_LABEL: Record<BucketKey, string> = {
  overdue: "Muddati o'tgan",
  today: "Bugun",
  week: "Shu hafta",
  later: "Keyinroq",
  none: "Muddatsiz",
};

export function bucketOf(task: Task, now: Date, weekEnd: Date): BucketKey {
  if (!task.due_date) return "none";
  const due = new Date(task.due_date);
  if (due < now) return "overdue";
  if (isToday(due)) return "today";
  if (due <= weekEnd) return "week";
  return "later";
}

export function groupByDue(tasks: Task[]): Record<BucketKey, Task[]> {
  const now = new Date();
  const weekEnd = endOfWeek(now, { weekStartsOn: 1 });
  const groups: Record<BucketKey, Task[]> = {
    overdue: [],
    today: [],
    week: [],
    later: [],
    none: [],
  };
  for (const task of tasks) groups[bucketOf(task, now, weekEnd)].push(task);
  return groups;
}

/** Due date ascending, undated last — the order every task list here uses. */
export function byDueDate(a: Task, b: Task): number {
  if (!a.due_date && !b.due_date) return a.created_at < b.created_at ? -1 : 1;
  if (!a.due_date) return 1;
  if (!b.due_date) return -1;
  return a.due_date < b.due_date ? -1 : a.due_date > b.due_date ? 1 : 0;
}
