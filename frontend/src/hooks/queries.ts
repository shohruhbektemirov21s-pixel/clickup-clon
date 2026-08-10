"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/keys";
import { useAuthStore } from "@/stores/auth-store";
import type {
  Comment,
  GroupedTasksResponse,
  Invitation,
  List,
  Member,
  Paginated,
  SearchResponse,
  Status,
  StatusSet,
  Tag,
  Task,
  User,
  Workspace,
  WorkspaceTree,
} from "@/types/api";

function useAuthed() {
  return useAuthStore((s) => s.status === "authenticated");
}

export function useMe() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api.get<User>("me/"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useWorkspaces() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaces,
    queryFn: () => api.get<Paginated<Workspace>>("workspaces/"),
    enabled,
    staleTime: 60_000,
  });
}

export function useWorkspace(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspace(workspaceId),
    queryFn: () => api.get<Workspace>(`workspaces/${workspaceId}/`),
    enabled: enabled && !!workspaceId,
    staleTime: 60_000,
  });
}

export function useWorkspaceTree(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.tree(workspaceId),
    queryFn: () => api.get<WorkspaceTree>(`workspaces/${workspaceId}/tree/`),
    enabled: enabled && !!workspaceId,
    staleTime: 30_000,
  });
}

export function useMembers(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.members(workspaceId),
    queryFn: () =>
      api.get<Paginated<Member>>(`workspaces/${workspaceId}/members/`, {
        page_size: 200,
      }),
    enabled: enabled && !!workspaceId,
    staleTime: 60_000,
  });
}

export function useInvitations(workspaceId: string, canRead: boolean) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.invitations(workspaceId),
    queryFn: () =>
      api.get<Paginated<Invitation>>(`workspaces/${workspaceId}/invitations/`),
    enabled: enabled && !!workspaceId && canRead,
  });
}

export function useTags(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.tags(workspaceId),
    queryFn: () =>
      api.get<Paginated<Tag>>(`workspaces/${workspaceId}/tags/`, { page_size: 200 }),
    enabled: enabled && !!workspaceId,
    staleTime: 60_000,
  });
}

export function useList(listId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.list(listId),
    queryFn: () => api.get<List>(`lists/${listId}/`),
    enabled: enabled && !!listId,
    staleTime: 30_000,
  });
}

export function useStatusSet(listId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.statusSet(listId),
    queryFn: () => api.get<StatusSet>(`lists/${listId}/status-set/`),
    enabled: enabled && !!listId,
    staleTime: 60_000,
  });
}

export function useGroupedTasks(listId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.tasksGrouped(listId),
    queryFn: () =>
      api.get<GroupedTasksResponse>(`lists/${listId}/tasks/`, {
        group_by: "status",
      }),
    enabled: enabled && !!listId,
  });
}

/**
 * Tasks assigned to the caller across the whole workspace (contract §10.5:
 * `assignee=me`). Due-date buckets are derived on the client from this single
 * response — the server `due=` filters overlap (an overdue task is also inside
 * `this_week`), which would duplicate rows across sections.
 */
export function useMyTasks(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaceTasks(workspaceId, "mine"),
    queryFn: () =>
      api.get<Paginated<Task>>(`workspaces/${workspaceId}/tasks/`, {
        assignee: "me",
        ordering: "due_date",
        page_size: 200,
      }),
    enabled: enabled && !!workspaceId,
    staleTime: 30_000,
  });
}

/**
 * One workspace-wide task page, used only to derive per-member open-task
 * counts on the dashboard (never one request per member).
 */
export function useWorkspaceTasks(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaceTasks(workspaceId, "all"),
    queryFn: () =>
      api.get<Paginated<Task>>(`workspaces/${workspaceId}/tasks/`, {
        page_size: 200,
      }),
    enabled: enabled && !!workspaceId,
    staleTime: 60_000,
  });
}

/**
 * Status sets for several lists at once (dashboard rows carry only a
 * `status_id`). Shares `keys.statusSet` with `useStatusSet`, so list pages and
 * the dashboard reuse the same cache entries.
 */
export function useStatusesByListIds(listIds: string[]) {
  const enabled = useAuthed();
  return useQueries({
    queries: listIds.map((listId) => ({
      queryKey: keys.statusSet(listId),
      queryFn: () => api.get<StatusSet>(`lists/${listId}/status-set/`),
      enabled: enabled && !!listId,
      staleTime: 60_000,
    })),
    combine: (results) => {
      const byId = new Map<string, Status>();
      for (const result of results) {
        for (const status of result.data?.statuses ?? []) byId.set(status.id, status);
      }
      return { statusById: byId, isPending: results.some((r) => r.isPending) };
    },
  });
}

export function useTask(taskId: string | null) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.task(taskId ?? ""),
    queryFn: () => api.get<Task>(`tasks/${taskId}/`),
    enabled: enabled && !!taskId,
  });
}

export function useComments(taskId: string | null) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.comments(taskId ?? ""),
    queryFn: () =>
      api.get<Paginated<Comment>>(`tasks/${taskId}/comments/`, { page_size: 100 }),
    enabled: enabled && !!taskId,
  });
}

export function useWorkspaceSearch(workspaceId: string, q: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.search(workspaceId, q),
    queryFn: () => api.get<SearchResponse>(`workspaces/${workspaceId}/search/`, { q }),
    enabled: enabled && !!workspaceId && q.trim().length >= 2,
  });
}
