import type { QueryClient } from "@tanstack/react-query";
import type { GroupedTasksResponse, Task } from "@/types/api";
import { keys } from "@/lib/keys";

/**
 * Helpers that mutate the grouped Board/List cache
 * (`['tasks', listId, {}, { groupBy: 'status' }]`) in an immutable way.
 * Ordering inside a group is always `position ASC, created_at ASC` — the
 * client never invents an order, it re-sorts by server-provided fields.
 */

function sortGroup(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    if (a.position !== b.position) return a.position < b.position ? -1 : 1;
    return a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0;
  });
}

export function upsertTaskInGroups(
  data: GroupedTasksResponse | undefined,
  task: Task,
): GroupedTasksResponse | undefined {
  if (!data) return data;
  let found = false;
  const groups = data.groups.map((group) => {
    const without = group.results.filter((t) => t.id !== task.id);
    const removed = without.length !== group.results.length;
    if (group.status_id === task.status_id) {
      found = true;
      return {
        ...group,
        results: sortGroup([...without, task]),
        count: group.count + (removed ? 0 : 1),
      };
    }
    if (removed) return { ...group, results: without, count: Math.max(0, group.count - 1) };
    return group;
  });
  // Status not present (e.g. status set changed elsewhere) — leave untouched;
  // the caller should invalidate instead.
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
      const without = group.results.filter((t) => t.id !== taskId);
      if (without.length === group.results.length) return group;
      return { ...group, results: without, count: Math.max(0, group.count - 1) };
    }),
  };
}

export function findTaskInGroups(
  data: GroupedTasksResponse | undefined,
  taskId: string,
): Task | undefined {
  if (!data) return undefined;
  for (const group of data.groups) {
    const task = group.results.find((t) => t.id === taskId);
    if (task) return task;
  }
  return undefined;
}

/**
 * Optimistic move: place the task at `toIndex` inside the destination status
 * group *by array order* (no position invented) — reconciled once the server
 * returns the authoritative `position`.
 */
export function applyLocalMove(
  data: GroupedTasksResponse | undefined,
  taskId: string,
  toStatusId: string,
  toIndex: number,
): GroupedTasksResponse | undefined {
  if (!data) return data;
  const task = findTaskInGroups(data, taskId);
  if (!task) return data;
  const moved: Task = { ...task, status_id: toStatusId };
  return {
    ...data,
    groups: data.groups.map((group) => {
      const without = group.results.filter((t) => t.id !== taskId);
      const removed = without.length !== group.results.length;
      if (group.status_id === toStatusId) {
        const results = [...without];
        results.splice(Math.min(toIndex, results.length), 0, moved);
        return { ...group, results, count: group.count + (removed ? 0 : 1) };
      }
      if (removed) return { ...group, results: without, count: Math.max(0, group.count - 1) };
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
