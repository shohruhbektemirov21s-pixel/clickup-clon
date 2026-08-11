import { endOfWeek, isToday } from "date-fns";
import { DUE_BUCKET_LABEL } from "@/i18n/uz";
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

/** Matn `src/i18n/uz.ts` da; bu yerda faqat qayta eksport. */
export const BUCKET_LABEL: Record<BucketKey, string> = DUE_BUCKET_LABEL;

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

/**
 * Due date ascending, undated last — the order every task list here uses.
 *
 * Solishtirish INSTANT bo'yicha, satr bo'yicha emas. Vaqt tamg'alari
 * v1.4.0 dan `+05:00` ofseti bilan keladi (§1.2); leksikografik solishtiruv
 * faqat ofset hamma qatorda bir xil bo'lgunicha to'g'ri ishlaydi va aynan
 * shunday jim taxminlar migratsiyada sinadi.
 */
export function byDueDate(a: Task, b: Task): number {
  const at = a.due_date ? Date.parse(a.due_date) : null;
  const bt = b.due_date ? Date.parse(b.due_date) : null;
  if (at === null && bt === null) return Date.parse(a.created_at) - Date.parse(b.created_at);
  if (at === null) return 1;
  if (bt === null) return -1;
  return at - bt;
}
