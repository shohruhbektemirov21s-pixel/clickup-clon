import type { QueryClient } from "@tanstack/react-query";
import type { GroupedTasksResponse, Task, TaskStatus } from "@/types/api";
import { keys } from "@/lib/keys";

/**
 * Helpers that mutate the grouped Board/List cache
 * (`['tasks', listId, {}, { groupBy: 'status' }]`) in an immutable way.
 * Ordering inside a group is always `position ASC, created_at ASC` — the
 * client never invents an order, it re-sorts by server-provided fields.
 */

function sortGroup(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    // `position` — ATAYLAB satr sifatida: u base-62 kasr kalit va shartnoma
    // uni oddiy satr sifatida solishtirishni talab qiladi (§10.3).
    if (a.position !== b.position) return a.position < b.position ? -1 : 1;
    // `created_at` esa vaqt — instant bo'yicha (ofsetli ISO, §1.2).
    return Date.parse(a.created_at) - Date.parse(b.created_at);
  });
}

export function upsertTaskInGroups(
  data: GroupedTasksResponse | undefined,
  task: Task,
): GroupedTasksResponse | undefined {
  if (!data) return data;
  let found = false;
  const groups = data.groups.map((group) => {
    const without = group.tasks.filter((t) => t.id !== task.id);
    const removed = without.length !== group.tasks.length;
    if (group.status === task.status) {
      found = true;
      return {
        ...group,
        tasks: sortGroup([...without, task]),
        count: group.count + (removed ? 0 : 1),
      };
    }
    if (removed) return { ...group, tasks: without, count: Math.max(0, group.count - 1) };
    return group;
  });
  // Kod noma'lum guruhga tushdi (server yangi holat qo'shgan bo'lsa) — tegmay
  // qoldiramiz; chaqiruvchi invalidatsiya qilsin.
  if (!found) return data;
  return { ...data, groups };
}

export function removeTaskFromGroups(
  data: GroupedTasksResponse | undefined,
  taskId: string,
): GroupedTasksResponse | undefined {
  if (!data) return data;
  return {
    ...data,
    groups: data.groups.map((group) => {
      const without = group.tasks.filter((t) => t.id !== taskId);
      if (without.length === group.tasks.length) return group;
      return { ...group, tasks: without, count: Math.max(0, group.count - 1) };
    }),
  };
}

export function findTaskInGroups(
  data: GroupedTasksResponse | undefined,
  taskId: string,
): Task | undefined {
  if (!data) return undefined;
  for (const group of data.groups) {
    const task = group.tasks.find((t) => t.id === taskId);
    if (task) return task;
  }
  return undefined;
}

/**
 * Optimistic move: place the task at `toIndex` inside the destination status
 * group *by array order* (no position invented) — reconciled once the server
 * returns the authoritative `position`. Guruhlar serverdan keladi va doim
 * to'rttasi bor, shuning uchun maqsad ustuni topilmay qolmaydi.
 */
export function applyLocalMove(
  data: GroupedTasksResponse | undefined,
  taskId: string,
  toStatus: TaskStatus,
  toIndex: number,
): GroupedTasksResponse | undefined {
  if (!data) return data;
  const task = findTaskInGroups(data, taskId);
  if (!task) return data;
  const moved: Task = { ...task, status: toStatus };
  return {
    ...data,
    groups: data.groups.map((group) => {
      const without = group.tasks.filter((t) => t.id !== taskId);
      const removed = without.length !== group.tasks.length;
      if (group.status === toStatus) {
        const tasks = [...without];
        tasks.splice(Math.min(toIndex, tasks.length), 0, moved);
        return { ...group, tasks, count: group.count + (removed ? 0 : 1) };
      }
      if (removed) return { ...group, tasks: without, count: Math.max(0, group.count - 1) };
      return group;
    }),
  };
}

/** Write a task into every cache that shows it (grouped list + detail). */
export function writeTaskEverywhere(queryClient: QueryClient, task: Task) {
  queryClient.setQueryData<GroupedTasksResponse>(
    keys.tasksGrouped(task.list_id),
    (old) => upsertTaskInGroups(old, task) ?? old,
  );
  queryClient.setQueryData<Task>(keys.task(task.id), (old) =>
    old ? { ...old, ...task } : task,
  );
}
