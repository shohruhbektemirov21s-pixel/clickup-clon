"use client";

import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { api, isApiError } from "@/lib/api";
import { keys } from "@/lib/keys";
import {
  applyLocalMove,
  removeTaskFromGroups,
  upsertTaskInGroups,
  writeTaskEverywhere,
} from "@/lib/task-cache";
import type {
  ChatMessage,
  Conversation,
  CreateChannelRequest,
  AddSpaceMemberRequest,
  BulkSpaceMembersRequest,
  BulkSpaceMembersResponse,
  Comment,
  CreateCommentRequest,
  GroupedTasksResponse,
  Invitation,
  InvitableRole,
  Member,
  MoveTaskRequest,
  MoveTaskResponse,
  Paginated,
  ResetRolePermissionsRequest,
  Role,
  RolePermissionMatrix,
  SpaceAccess,
  SpaceMember,
  Task,
  TaskAttachment,
  TaskWriteRequest,
  UpdateRolePermissionsRequest,
  Workspace,
} from "@/types/api";

function errorMessage(err: unknown): string {
  if (isApiError(err)) {
    switch (err.code) {
      case "permission_denied":
        return "Sizda bu amal uchun ruxsat yo'q.";
      case "not_found":
        return "Topilmadi — u allaqachon o'chirilgan bo'lishi mumkin.";
      case "throttled":
        return "Urinishlar juda ko'p. Biroz kutib, qayta urinib ko'ring.";
      default:
        return err.message;
    }
  }
  return "Nimadir xato ketdi. Internet aloqasini tekshirib, qayta urinib ko'ring.";
}

// ---------------------------------------------------------------------------
// Workspace-wide rollups that every task write invalidates
// ---------------------------------------------------------------------------

/**
 * A task write does not only change its own list. Four caches summarise tasks
 * *above* the list level and go stale with it:
 *
 *   • `keys.tree`               — every list's `open_task_count` (sidebar badges)
 *   • `keys.workspaceTasksRoot` — the dashboard cards and "Mening vazifalarim"
 *   • `keys.activityRoot`       — the workspace history feed (§10.8)
 *   • `keys.memberProfileRoot`  — the per-member counters (§4.1)
 *
 * None of them can be patched in place: the server applies visibility filters,
 * bucketing and pagination that the client cannot re-evaluate (the same reason
 * `use-workspace-channel` refetches instead of merging). So they are refetched.
 *
 * The `useWorkspaceChannel` socket would have covered this, but it is mounted
 * on the workspace home only — it is not running while the user is on a list
 * page, which is exactly where task writes happen.
 */
const ROLLUP_KEYS = [
  keys.tree,
  keys.workspaceTasksRoot,
  keys.activityRoot,
  keys.memberProfileRoot,
] as const;

/**
 * Coalescing window. Editing a card fires a burst of PATCHes (status, then
 * assignee, then due date…) and one `invalidateQueries` per request would
 * refetch the tree once per keystroke-batch. One flush per window is enough —
 * the same discipline `use-workspace-channel` applies to inbound frames.
 */
const ROLLUP_FLUSH_MS = 200;

interface RollupState {
  pending: Set<string>;
  timer: ReturnType<typeof setTimeout> | null;
}

/**
 * Module-level so the flush coalesces across hook instances (a single task
 * panel mounts `useUpdateTask` three times). Keyed by `QueryClient` in a
 * WeakMap so a torn-down provider — or a second client in a test — can never be
 * invalidated by a timer it does not own.
 */
const rollups = new WeakMap<QueryClient, RollupState>();

function scheduleWorkspaceRollup(
  queryClient: QueryClient,
  workspaceId: string | null,
): void {
  if (!workspaceId) return;
  let state = rollups.get(queryClient);
  if (!state) {
    state = { pending: new Set(), timer: null };
    rollups.set(queryClient, state);
  }
  state.pending.add(workspaceId);
  if (state.timer !== null) return; // a flush is already scheduled
  const scheduled = state;
  scheduled.timer = setTimeout(() => {
    scheduled.timer = null;
    const workspaceIds = [...scheduled.pending];
    scheduled.pending.clear();
    for (const id of workspaceIds) {
      // Only *mounted* queries actually refetch, so a list page pays for the
      // tree and the rest are merely marked stale.
      for (const key of ROLLUP_KEYS) {
        void queryClient.invalidateQueries({ queryKey: key(id) });
      }
    }
  }, ROLLUP_FLUSH_MS);
}

/**
 * The workspace a task mutation happens in. Every task surface lives under
 * `/w/[workspaceId]/…`, so the route already carries the id and no call site
 * has to pass it; outside that segment it is `null` and the rollup is skipped.
 */
function useRouteWorkspaceId(): string | null {
  const params = useParams<{ workspaceId?: string | string[] }>();
  const raw = params?.workspaceId;
  return (Array.isArray(raw) ? raw[0] : raw) ?? null;
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export function useCreateTask(listId: string) {
  const queryClient = useQueryClient();
  const workspaceId = useRouteWorkspaceId();
  return useMutation({
    mutationFn: (body: TaskWriteRequest & { title: string }) =>
      api.post<Task>(`lists/${listId}/tasks/`, { ...body, id: crypto.randomUUID() }),
    onSuccess: (task) => {
      queryClient.setQueryData<GroupedTasksResponse>(
        keys.tasksGrouped(listId),
        (old) => upsertTaskInGroups(old, task) ?? old,
      );
      queryClient.invalidateQueries({ queryKey: keys.tasksGrouped(listId) });
      scheduleWorkspaceRollup(queryClient, workspaceId);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

/** Optimistic field update (status change, priority, title, dates, assignees…). */
export function useUpdateTask(listId: string) {
  const queryClient = useQueryClient();
  const workspaceId = useRouteWorkspaceId();
  return useMutation({
    mutationFn: ({ taskId, patch }: UpdateTaskVars) =>
      api.patch<Task>(`tasks/${taskId}/`, patch),
    onMutate: async ({ taskId, patch, optimistic }: UpdateTaskVars) => {
      const groupedKey = keys.tasksGrouped(listId);
      await queryClient.cancelQueries({ queryKey: groupedKey });
      await queryClient.cancelQueries({ queryKey: keys.task(taskId) });
      const previousGrouped =
        queryClient.getQueryData<GroupedTasksResponse>(groupedKey);
      const previousTask = queryClient.getQueryData<Task>(keys.task(taskId));

      // Scalar fields are derived from the patch; embedded arrays
      // (assignees/tags) must be resolved by the caller via `optimistic`,
      // since the request only carries ids.
      const scalarPatch: Partial<Task> = {};
      if (patch.title !== undefined) scalarPatch.title = patch.title;
      if (patch.status_id !== undefined) scalarPatch.status_id = patch.status_id;
      if (patch.priority !== undefined) scalarPatch.priority = patch.priority;
      if (patch.due_date !== undefined) scalarPatch.due_date = patch.due_date;
      if (patch.start_date !== undefined) scalarPatch.start_date = patch.start_date;
      if (optimistic?.assignees !== undefined) scalarPatch.assignees = optimistic.assignees;
      if (optimistic?.tags !== undefined) scalarPatch.tags = optimistic.tags;

      if (previousTask) {
        queryClient.setQueryData<Task>(keys.task(taskId), {
          ...previousTask,
          ...scalarPatch,
        });
      }
      if (previousGrouped) {
        const current = previousGrouped.groups
          .flatMap((g) => g.results)
          .find((t) => t.id === taskId);
        if (current) {
          queryClient.setQueryData<GroupedTasksResponse>(
            groupedKey,
            (old) => upsertTaskInGroups(old, { ...current, ...scalarPatch }) ?? old,
          );
        }
      }
      return { previousGrouped, previousTask };
    },
    onError: (err, { taskId }, ctx) => {
      if (ctx?.previousGrouped) {
        queryClient.setQueryData(keys.tasksGrouped(listId), ctx.previousGrouped);
      }
      if (ctx?.previousTask) {
        queryClient.setQueryData(keys.task(taskId), ctx.previousTask);
      }
      if (isApiError(err) && err.code === "invalid_status_for_list") {
        toast.error("Bu holat ushbu ro'yxatda mavjud emas.");
        queryClient.invalidateQueries({ queryKey: keys.statusSet(listId) });
      } else {
        toast.error(errorMessage(err));
      }
    },
    onSuccess: (task) => {
      writeTaskEverywhere(queryClient, task);
      scheduleWorkspaceRollup(queryClient, workspaceId);
    },
  });
}

export function useDeleteTask(listId: string) {
  const queryClient = useQueryClient();
  const workspaceId = useRouteWorkspaceId();
  return useMutation({
    mutationFn: (taskId: string) => api.delete(`tasks/${taskId}/`),
    onMutate: async (taskId) => {
      const groupedKey = keys.tasksGrouped(listId);
      await queryClient.cancelQueries({ queryKey: groupedKey });
      const previous = queryClient.getQueryData<GroupedTasksResponse>(groupedKey);
      queryClient.setQueryData<GroupedTasksResponse>(
        groupedKey,
        (old) => removeTaskFromGroups(old, taskId) ?? old,
      );
      return { previous };
    },
    onError: (err, _taskId, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(keys.tasksGrouped(listId), ctx.previous);
      }
      toast.error(errorMessage(err));
    },
    onSuccess: (_data, taskId) => {
      queryClient.removeQueries({ queryKey: keys.task(taskId) });
      scheduleWorkspaceRollup(queryClient, workspaceId);
      toast.success("Vazifa o'chirildi");
    },
  });
}

export interface UpdateTaskVars {
  taskId: string;
  patch: TaskWriteRequest;
  /**
   * Embedded values matching the ids in `patch`, so the optimistic write can
   * render avatars/chips before the server echoes the full objects back.
   */
  optimistic?: Pick<Partial<Task>, "assignees" | "tags">;
}

export interface MoveIntent {
  taskId: string;
  toStatusId: string;
  /** Index inside the destination column after removal of the dragged item. */
  toIndex: number;
  beforeId: string | null;
  afterId: string | null;
}

/**
 * §6.3 optimistic move: send before_id/after_id (never a position), splice
 * the card locally, reconcile with the server position, roll back on error.
 * A `position_conflict` triggers a silent refetch of the column.
 */
export function useMoveTask(listId: string) {
  const queryClient = useQueryClient();
  const workspaceId = useRouteWorkspaceId();
  return useMutation({
    mutationFn: (intent: MoveIntent) =>
      api.patch<MoveTaskResponse>(`tasks/${intent.taskId}/move/`, {
        list_id: listId,
        status_id: intent.toStatusId,
        before_id: intent.beforeId,
        after_id: intent.afterId,
      } satisfies MoveTaskRequest),
    onMutate: async (intent) => {
      const groupedKey = keys.tasksGrouped(listId);
      await queryClient.cancelQueries({ queryKey: groupedKey });
      const previous = queryClient.getQueryData<GroupedTasksResponse>(groupedKey);
      queryClient.setQueryData<GroupedTasksResponse>(
        groupedKey,
        (old) =>
          applyLocalMove(old, intent.taskId, intent.toStatusId, intent.toIndex) ?? old,
      );
      return { previous };
    },
    onSuccess: (response) => {
      // `rebalanced` is a move-response flag, not a task field. Writing the
      // whole response into `keys.task(id)` would persist it and leave the
      // cached object out of sync with what `GET tasks/{id}/` returns.
      const { rebalanced, ...task } = response;
      scheduleWorkspaceRollup(queryClient, workspaceId);
      if (rebalanced) {
        // Positions were renumbered server-side — refetch, don't patch.
        queryClient.invalidateQueries({ queryKey: keys.tasksRoot(listId) });
        return;
      }
      writeTaskEverywhere(queryClient, task);
    },
    onError: (err, _intent, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(keys.tasksGrouped(listId), ctx.previous);
      }
      if (isApiError(err) && (err.code === "position_conflict" || err.code === "conflict")) {
        // Stale neighbours — silent recovery via refetch.
        queryClient.invalidateQueries({ queryKey: keys.tasksRoot(listId) });
        return;
      }
      if (isApiError(err) && err.code === "invalid_status_for_list") {
        queryClient.invalidateQueries({ queryKey: keys.statusSet(listId) });
        toast.error("Bu holat ushbu ro'yxatda mavjud emas.");
        return; // rollback already applied above
      }
      toast.error(errorMessage(err));
    },
  });
}

// ---------------------------------------------------------------------------
// Comments
// ---------------------------------------------------------------------------

export function useCreateComment(taskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateCommentRequest) =>
      api.post<Comment>(`tasks/${taskId}/comments/`, { ...body, id: crypto.randomUUID() }),
    onSuccess: (comment) => {
      queryClient.setQueryData<Paginated<Comment>>(keys.comments(taskId), (old) =>
        old && !old.results.some((c) => c.id === comment.id)
          ? { ...old, count: old.count + 1, results: [...old.results, comment] }
          : old,
      );
      queryClient.invalidateQueries({ queryKey: keys.task(taskId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useUpdateComment(taskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      commentId,
      body,
    }: {
      commentId: string;
      body: Pick<CreateCommentRequest, "body_html" | "body_json">;
    }) => api.patch<Comment>(`comments/${commentId}/`, body),
    onSuccess: (comment) => {
      queryClient.setQueryData<Paginated<Comment>>(keys.comments(taskId), (old) =>
        old
          ? {
              ...old,
              results: old.results.map((c) => (c.id === comment.id ? comment : c)),
            }
          : old,
      );
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useDeleteComment(taskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (commentId: string) => api.delete(`comments/${commentId}/`),
    onSuccess: (_data, commentId) => {
      queryClient.setQueryData<Paginated<Comment>>(keys.comments(taskId), (old) =>
        old
          ? {
              ...old,
              count: Math.max(0, old.count - 1),
              results: old.results.filter((c) => c.id !== commentId),
            }
          : old,
      );
      queryClient.invalidateQueries({ queryKey: keys.task(taskId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

// ---------------------------------------------------------------------------
// Attachments (§10.7)
// ---------------------------------------------------------------------------

/** Uzbek message for an upload failure — field errors first, then the code. */
export function attachmentErrorMessage(err: unknown): string {
  if (isApiError(err)) {
    if (err.code === "validation_error") {
      // The server puts the real reason (size / type / empty) under `file`.
      const fieldError = err.fieldError("file");
      if (fieldError) return fieldError;
    }
    if (err.code === "throttled") {
      return "Juda ko'p fayl yuklandi. Biroz kutib, qayta urinib ko'ring.";
    }
    if (err.status === 0) return err.message; // network error from the XHR path
  }
  return errorMessage(err);
}

/**
 * multipart upload with progress. `attachment_count` lives on the task, so the
 * task query is invalidated alongside the attachment list.
 */
export function useUploadAttachment(taskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      onProgress,
    }: {
      file: File;
      onProgress?: (percent: number) => void;
    }) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<TaskAttachment>(
        `tasks/${taskId}/attachments/`,
        form,
        onProgress,
      );
    },
    onSuccess: (attachment) => {
      queryClient.setQueryData<Paginated<TaskAttachment>>(
        keys.attachments(taskId),
        (old) =>
          old && !old.results.some((a) => a.id === attachment.id)
            ? { ...old, count: old.count + 1, results: [attachment, ...old.results] }
            : old,
      );
      queryClient.invalidateQueries({ queryKey: keys.task(taskId) });
    },
    onError: (err) => toast.error(attachmentErrorMessage(err)),
  });
}

export function useDeleteAttachment(taskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (attachmentId: string) => api.delete(`attachments/${attachmentId}/`),
    onSuccess: (_data, attachmentId) => {
      queryClient.setQueryData<Paginated<TaskAttachment>>(
        keys.attachments(taskId),
        (old) =>
          old
            ? {
                ...old,
                count: Math.max(0, old.count - 1),
                results: old.results.filter((a) => a.id !== attachmentId),
              }
            : old,
      );
      queryClient.invalidateQueries({ queryKey: keys.task(taskId) });
      toast.success("Fayl o'chirildi");
    },
    onError: (err) => toast.error(attachmentErrorMessage(err)),
  });
}

// ---------------------------------------------------------------------------
// Workspace settings: rename, members, invitations
// ---------------------------------------------------------------------------

export function useRenameWorkspace(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; description?: string; color?: string }) =>
      api.patch<Workspace>(`workspaces/${workspaceId}/`, body),
    onSuccess: (workspace) => {
      queryClient.setQueryData(keys.workspace(workspaceId), workspace);
      queryClient.invalidateQueries({ queryKey: keys.workspaces });
      queryClient.invalidateQueries({ queryKey: keys.tree(workspaceId) });
      toast.success("Ish maydoni yangilandi");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useChangeMemberRole(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      api.patch<Member>(`workspaces/${workspaceId}/members/${userId}/`, { role }),
    onSuccess: (member) => {
      queryClient.setQueryData<Paginated<Member>>(keys.members(workspaceId), (old) =>
        old
          ? {
              ...old,
              results: old.results.map((m) => (m.id === member.id ? member : m)),
            }
          : old,
      );
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useRemoveMember(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      api.delete(`workspaces/${workspaceId}/members/${userId}/`),
    onSuccess: (_d, userId) => {
      queryClient.setQueryData<Paginated<Member>>(keys.members(workspaceId), (old) =>
        old
          ? {
              ...old,
              count: Math.max(0, old.count - 1),
              results: old.results.filter((m) => m.user.id !== userId),
            }
          : old,
      );
      toast.success("A'zo chiqarildi");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useCreateInvitation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role: InvitableRole }) =>
      api.post<Invitation>(`workspaces/${workspaceId}/invitations/`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.invitations(workspaceId) });
      // The roster changes as soon as an invite is accepted; refresh both.
      queryClient.invalidateQueries({ queryKey: keys.members(workspaceId) });
      toast.success("Taklif yuborildi");
    },
    onError: (err) => {
      if (isApiError(err)) {
        // §5: duplicate pending invite / already a member / send cap reached.
        if (err.code === "conflict") {
          toast.error("Bu foydalanuvchi allaqachon a'zo yoki taklifi yuborilgan.");
          return;
        }
        if (err.code === "throttled") {
          toast.error("Juda ko'p taklif yuborildi. Biroz kutib, qayta urinib ko'ring.");
          return;
        }
        const emailError = err.fieldError("email") ?? err.fieldError("role");
        if (emailError) {
          toast.error(emailError);
          return;
        }
      }
      toast.error(errorMessage(err));
    },
  });
}

export function useRevokeInvitation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) => api.delete(`invitations/${invitationId}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.invitations(workspaceId) });
      toast.success("Taklif bekor qilindi");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useResendInvitation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) =>
      api.post<Invitation>(`invitations/${invitationId}/resend/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.invitations(workspaceId) });
      toast.success("Taklif qayta yuborildi");
    },
    onError: (err) => {
      // §5: resend is throttled 1/5min and capped at 5 sends.
      if (isApiError(err) && err.code === "conflict") {
        toast.error("Bu taklif uchun yuborish chegarasi tugagan.");
        return;
      }
      toast.error(errorMessage(err));
    },
  });
}

// ---------------------------------------------------------------------------
// §18 Role permission matrix
// ---------------------------------------------------------------------------

/** Uzbek message for a 409 on the matrix — someone else saved in between. */
export const MATRIX_CONFLICT_MESSAGE =
  "Boshqa admin matritsani o'zgartirdi. Eng so'nggi holat qayta yuklandi — o'zgarishlaringizni ko'rib chiqing va qaytadan saqlang.";

/**
 * Writes a sparse patch of the matrix. `expected_version` is mandatory: the
 * server answers 409 when the stored version moved on, and we then reload the
 * matrix so the screen re-renders from the winning state.
 */
export function useUpdateRolePermissions(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateRolePermissionsRequest) =>
      api.put<RolePermissionMatrix>(
        `workspaces/${workspaceId}/role-permissions/`,
        body,
      ),
    onSuccess: (matrix) => {
      queryClient.setQueryData(keys.rolePermissions(workspaceId), matrix);
      // Own affordances and the workspace `permissions_version` both move.
      queryClient.invalidateQueries({ queryKey: keys.myPermissions(workspaceId) });
      queryClient.invalidateQueries({ queryKey: keys.workspace(workspaceId) });
      toast.success("Huquqlar saqlandi");
    },
    onError: (err) => {
      if (isApiError(err) && err.code === "conflict") {
        // Optimistic-concurrency loss — refetch so the UI shows the winner.
        queryClient.invalidateQueries({ queryKey: keys.rolePermissions(workspaceId) });
        toast.error(MATRIX_CONFLICT_MESSAGE);
        return;
      }
      if (isApiError(err) && err.code === "validation_error") {
        const monotonic = err.fieldError("monotonic");
        if (monotonic) {
          toast.error(monotonic);
          return;
        }
      }
      toast.error(errorMessage(err));
    },
  });
}

/** `role: null` resets every role back to the catalog defaults. */
export function useResetRolePermissions(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ResetRolePermissionsRequest) =>
      api.post<RolePermissionMatrix>(
        `workspaces/${workspaceId}/role-permissions/reset/`,
        body,
      ),
    onSuccess: (matrix) => {
      queryClient.setQueryData(keys.rolePermissions(workspaceId), matrix);
      queryClient.invalidateQueries({ queryKey: keys.myPermissions(workspaceId) });
      queryClient.invalidateQueries({ queryKey: keys.workspace(workspaceId) });
      toast.success("Standart huquqlar tiklandi");
    },
    onError: (err) => {
      if (isApiError(err) && err.code === "conflict") {
        queryClient.invalidateQueries({ queryKey: keys.rolePermissions(workspaceId) });
        toast.error(MATRIX_CONFLICT_MESSAGE);
        return;
      }
      toast.error(errorMessage(err));
    },
  });
}

// ---------------------------------------------------------------------------
// Hierarchy creation (sidebar)
// ---------------------------------------------------------------------------

export function useCreateSpace(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; color?: string }) =>
      api.post(`workspaces/${workspaceId}/spaces/`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.tree(workspaceId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

// ---------------------------------------------------------------------------
// Hierarchy rename / delete (sidebar context actions)
// ---------------------------------------------------------------------------

export type FolderDeleteStrategy = "cascade" | "detach";

/** PATCH spaces|folders|lists/{id}/ — rename. Invalidates the sidebar tree. */
export function useRenameEntity(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      kind,
      id,
      name,
    }: {
      kind: "space" | "folder" | "list";
      id: string;
      name: string;
    }) => {
      const segment =
        kind === "space" ? "spaces" : kind === "folder" ? "folders" : "lists";
      return api.patch(`${segment}/${id}/`, { name });
    },
    onSuccess: (_data, { kind, id }) => {
      queryClient.invalidateQueries({ queryKey: keys.tree(workspaceId) });
      if (kind === "list") queryClient.invalidateQueries({ queryKey: keys.list(id) });
      toast.success("Nomi o'zgartirildi");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

/** DELETE spaces/{id}/ — requires `confirm_name` (contract §6); admin+ only. */
export function useDeleteSpace(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, confirmName }: { id: string; confirmName: string }) =>
      api.delete(`spaces/${id}/`, { confirm_name: confirmName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.tree(workspaceId) });
      toast.success("Bo'lim o'chirildi");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

/** DELETE folders/{id}/?strategy=cascade|detach (contract §7). */
export function useDeleteFolder(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, strategy }: { id: string; strategy: FolderDeleteStrategy }) =>
      api.delete(`folders/${id}/`, undefined, { query: { strategy } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.tree(workspaceId) });
      toast.success("Jild o'chirildi");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

/** DELETE lists/{id}/ — no confirmation body; the UI confirms (contract §8). */
export function useDeleteList(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`lists/${id}/`),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: keys.tree(workspaceId) });
      queryClient.removeQueries({ queryKey: keys.list(id) });
      queryClient.removeQueries({ queryKey: keys.tasksRoot(id) });
      toast.success("Ro'yxat o'chirildi");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useCreateList(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      spaceId,
      name,
      folderId,
    }: {
      spaceId: string;
      name: string;
      folderId?: string | null;
    }) =>
      api.post(`spaces/${spaceId}/lists/`, {
        name,
        folder_id: folderId ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.tree(workspaceId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

// ---------------------------------------------------------------------------
// §D.6 Space members (PM biriktiruvi)
// ---------------------------------------------------------------------------

/**
 * Uzbek message for the `last_manager` conflict. The server refuses to leave a
 * private space without a manager — otherwise nobody could ever add a member
 * back and the space would lock itself shut.
 */
const LAST_MANAGER_MESSAGE =
  "Bu yopiq bo'limning oxirgi menejeri — avval boshqa menejer tayinlang.";

function spaceMemberError(err: unknown): string {
  if (isApiError(err)) {
    if (err.details?.reason === "last_manager") return LAST_MANAGER_MESSAGE;
    if (err.code === "conflict") return "Bu foydalanuvchi allaqachon bo'lim a'zosi.";
    const fieldError = err.fieldError("user_id") ?? err.fieldError("remove");
    if (fieldError) return fieldError;
  }
  return errorMessage(err);
}

/** `POST spaces/{id}/members/` — add one person to the space. */
export function useAddSpaceMember(spaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AddSpaceMemberRequest) =>
      api.post<SpaceMember>(`spaces/${spaceId}/members/`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.spaceMembers(spaceId) });
      toast.success("Bo'limga qo'shildi");
    },
    onError: (err) => toast.error(spaceMemberError(err)),
  });
}

/** `PATCH spaces/{id}/members/{userId}/` — change one person's access level. */
export function useUpdateSpaceMember(spaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, access }: { userId: string; access: SpaceAccess }) =>
      api.patch<SpaceMember>(`spaces/${spaceId}/members/${userId}/`, { access }),
    onSuccess: (row) => {
      queryClient.setQueryData<Paginated<SpaceMember>>(
        keys.spaceMembers(spaceId),
        (old) =>
          old
            ? { ...old, results: old.results.map((m) => (m.id === row.id ? row : m)) }
            : old,
      );
    },
    onError: (err) => toast.error(spaceMemberError(err)),
  });
}

/** `DELETE spaces/{id}/members/{userId}/`. */
export function useRemoveSpaceMember(spaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => api.delete(`spaces/${spaceId}/members/${userId}/`),
    onSuccess: (_data, userId) => {
      queryClient.setQueryData<Paginated<SpaceMember>>(
        keys.spaceMembers(spaceId),
        (old) =>
          old
            ? {
                ...old,
                count: Math.max(0, old.count - 1),
                results: old.results.filter((m) => m.user.id !== userId),
              }
            : old,
      );
      toast.success("Bo'limdan olib tashlandi");
    },
    onError: (err) => toast.error(spaceMemberError(err)),
  });
}

/**
 * `POST spaces/{id}/members/bulk/` — the PM panel's "Saqlash" button.
 * One transaction on the server: either every change lands or none does, so
 * the client can safely replace its whole roster with `results`.
 */
export function useBulkSpaceMembers(spaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BulkSpaceMembersRequest) =>
      api.post<BulkSpaceMembersResponse>(`spaces/${spaceId}/members/bulk/`, body),
    onSuccess: (data) => {
      queryClient.setQueryData<Paginated<SpaceMember>>(keys.spaceMembers(spaceId), {
        count: data.results.length,
        next: null,
        previous: null,
        results: data.results,
      });
      const parts: string[] = [];
      if (data.added) parts.push(`${data.added} ta qo'shildi`);
      if (data.removed) parts.push(`${data.removed} ta olib tashlandi`);
      toast.success(parts.length ? parts.join(", ") : "O'zgarishlar saqlandi");
    },
    onError: (err) => toast.error(spaceMemberError(err)),
  });
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export function useCreateChannel(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateChannelRequest) =>
      api.post<Conversation>(`workspaces/${workspaceId}/chat/channels/`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.conversations(workspaceId) });
      toast.success("Kanal yaratildi");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

/** DM ochadi yoki mavjudini qaytaradi — ikkalasi ham bir xil javob. */
export function useOpenDirect(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      api.post<Conversation>(`workspaces/${workspaceId}/chat/direct/`, { user_id: userId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.conversations(workspaceId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useJoinConversation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) =>
      api.post(`chat/conversations/${conversationId}/join/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.conversations(workspaceId) });
      toast.success("Kanalga qo'shildingiz");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useSendMessage(workspaceId: string, conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) =>
      api.post<ChatMessage>(`chat/conversations/${conversationId}/messages/`, { body }),
    onSuccess: (message) => {
      // Javobni darhol keshka yozamiz — broadcast o'z aks-sadosini
      // yubormaydi, shuning uchun kutib o'tirish kerak emas.
      queryClient.setQueryData<Paginated<ChatMessage>>(
        keys.chatMessages(conversationId),
        (old) =>
          old && !old.results.some((m) => m.id === message.id)
            ? { ...old, count: old.count + 1, results: [message, ...old.results] }
            : old,
      );
      queryClient.invalidateQueries({ queryKey: keys.conversations(workspaceId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}
