"use client";

import { useQuery } from "@tanstack/react-query";
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
