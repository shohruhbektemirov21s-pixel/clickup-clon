"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/keys";
import { useAuthStore } from "@/stores/auth-store";
import type {
  Comment,
  GroupedTasksResponse,
  Invitation,
  InvitationLookup,
  List,
  Member,
  MemberProfile,
  MyPermissions,
  Paginated,
  PermissionCatalog,
  RolePermissionMatrix,
  SearchResponse,
  Status,
  StatusSet,
  Tag,
  Task,
  TaskAttachment,
  User,
  Workspace,
  WorkspaceActivity,
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

/**
 * `GET workspaces/{id}/members/{userId}/profile/` (§4.1) — the header, the
 * counters and the space breakdown of the member profile page in one request.
 * Every number is already scoped to the caller's visibility server-side, so
 * the client never re-filters. Requires `member.read`; pass `canRead: false`
 * to skip a request that would 403.
 */
export function useMemberProfile(workspaceId: string, userId: string, canRead = true) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.memberProfile(workspaceId, userId),
    queryFn: () =>
      api.get<MemberProfile>(
        `workspaces/${workspaceId}/members/${userId}/profile/`,
      ),
    enabled: enabled && !!workspaceId && !!userId && canRead,
    retry: false,
    staleTime: 30_000,
  });
}

/**
 * `GET workspaces/{id}/activity/` (§10.8) — the workspace history feed,
 * newest first. `actorId` maps to `?actor=`; pass `null` for everybody.
 * Requires `task.read`.
 */
export function useWorkspaceActivity(
  workspaceId: string,
  actorId: string | null,
  canRead = true,
) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.activity(workspaceId, actorId),
    queryFn: () =>
      api.get<Paginated<WorkspaceActivity>>(`workspaces/${workspaceId}/activity/`, {
        actor: actorId ?? undefined,
        page_size: 50,
      }),
    enabled: enabled && !!workspaceId && canRead,
    staleTime: 30_000,
  });
}

/**
 * Tasks assigned to ONE member across the workspace (§10.5 `assignee=<uuid>`).
 * Same shape and ordering as `useMyTasks`, so the profile page can reuse the
 * dashboard's due-date bucketing verbatim.
 */
export function useMemberTasks(workspaceId: string, userId: string, canRead = true) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaceTasks(workspaceId, `user:${userId}`),
    queryFn: () =>
      api.get<Paginated<Task>>(`workspaces/${workspaceId}/tasks/`, {
        assignee: userId,
        ordering: "due_date",
        page_size: 200,
      }),
    enabled: enabled && !!workspaceId && !!userId && canRead,
    staleTime: 30_000,
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
 * One workspace-wide task page. It backs BOTH dashboard consumers — the
 * per-member open-task counters and the "Jamoa vazifalari" view grouped by
 * assignee — from a single cache entry, so neither adds a request per member.
 * `canRead` mirrors `task.read`; pass `false` to skip a guaranteed-empty read.
 * The server already drops tasks in spaces the caller cannot see, so the
 * client never re-filters for visibility.
 */
export function useWorkspaceTasks(workspaceId: string, canRead = true) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.workspaceTasks(workspaceId, "all"),
    queryFn: () =>
      api.get<Paginated<Task>>(`workspaces/${workspaceId}/tasks/`, {
        page_size: 200,
      }),
    enabled: enabled && !!workspaceId && canRead,
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

/**
 * Attachments of a task (§10.7). `canRead` mirrors `attachment.read`, which
 * every role holds by default — pass `false` only when the matrix revoked it,
 * so the panel does not fire a request that is guaranteed to 403.
 */
export function useAttachments(taskId: string | null, canRead = true) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.attachments(taskId ?? ""),
    queryFn: () =>
      api.get<Paginated<TaskAttachment>>(`tasks/${taskId}/attachments/`, {
        page_size: 100,
      }),
    enabled: enabled && !!taskId && canRead,
  });
}

// ---------------------------------------------------------------------------
// §18 Permissions (docs/DESIGN_PERMISSIONS.md §D.1–D.5)
// ---------------------------------------------------------------------------

/**
 * The permission catalog is derived from server *code*, not from the database:
 * it only ever changes on deploy. `staleTime: Infinity` keeps it to one fetch
 * per session (risk R4 — never add a round trip per screen).
 */
export function usePermissionCatalog() {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.permissionCatalog,
    queryFn: () => api.get<PermissionCatalog>("permissions/"),
    enabled,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

/**
 * The caller's own effective permissions — every UI affordance in the
 * workspace is gated off this single request. Available to any member,
 * guests included. Invalidated by the `permission.updated` WS frame.
 */
export function useMyPermissions(workspaceId: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.myPermissions(workspaceId),
    queryFn: () => api.get<MyPermissions>(`workspaces/${workspaceId}/my-permissions/`),
    enabled: enabled && !!workspaceId,
    staleTime: 5 * 60_000,
  });
}

/**
 * The full role × permission matrix. Requires `workspace.manage_permissions`
 * (owner-only by default), so the caller passes `canRead` to avoid a
 * guaranteed 403. `version` is the optimistic-concurrency token.
 */
export function useRolePermissions(workspaceId: string, canRead: boolean) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: keys.rolePermissions(workspaceId),
    queryFn: () =>
      api.get<RolePermissionMatrix>(`workspaces/${workspaceId}/role-permissions/`),
    enabled: enabled && !!workspaceId && canRead,
    staleTime: 30_000,
  });
}

/**
 * `GET invitations/lookup/?token=` — PUBLIC endpoint, shuning uchun
 * `auth: false` bilan chaqiriladi (chaqiruvchi tizimga kirmagan bo'lishi
 * mumkin). Noma'lum/eskirgan token → 404; retry qilinmaydi.
 */
export function useInvitationLookup(token: string) {
  return useQuery({
    queryKey: keys.invitationLookup(token),
    queryFn: () =>
      api.get<InvitationLookup>("invitations/lookup/", { token }, { auth: false }),
    enabled: !!token,
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
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
