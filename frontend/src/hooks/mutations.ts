"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
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
  Comment,
  CreateCommentRequest,
  GroupedTasksResponse,
  Invitation,
  InvitableRole,
  Member,
  MoveTaskRequest,
  MoveTaskResponse,
  Paginated,
  Role,
  Task,
  TaskWriteRequest,
  Workspace,
} from "@/types/api";

function errorMessage(err: unknown): string {
  if (isApiError(err)) return err.message;
  return "Nimadir xato ketdi. Internet aloqasini tekshirib, qayta urinib ko'ring.";
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export function useCreateTask(listId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TaskWriteRequest & { title: string }) =>
      api.post<Task>(`lists/${listId}/tasks/`, { ...body, id: crypto.randomUUID() }),
    onSuccess: (task) => {
      queryClient.setQueryData<GroupedTasksResponse>(
        keys.tasksGrouped(listId),
        (old) => upsertTaskInGroups(old, task) ?? old,
      );
      queryClient.invalidateQueries({ queryKey: keys.tasksGrouped(listId) });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

/** Optimistic field update (status change, priority, title, dates, …). */
export function useUpdateTask(listId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, patch }: { taskId: string; patch: TaskWriteRequest }) =>
      api.patch<Task>(`tasks/${taskId}/`, patch),
    onMutate: async ({ taskId, patch }) => {
      const groupedKey = keys.tasksGrouped(listId);
      await queryClient.cancelQueries({ queryKey: groupedKey });
      await queryClient.cancelQueries({ queryKey: keys.task(taskId) });
      const previousGrouped =
        queryClient.getQueryData<GroupedTasksResponse>(groupedKey);
      const previousTask = queryClient.getQueryData<Task>(keys.task(taskId));

      // Only simple scalar fields are applied optimistically; embedded arrays
      // (assignees/tags) reconcile from the response.
      const scalarPatch: Partial<Task> = {};
      if (patch.title !== undefined) scalarPatch.title = patch.title;
      if (patch.status_id !== undefined) scalarPatch.status_id = patch.status_id;
      if (patch.priority !== undefined) scalarPatch.priority = patch.priority;
      if (patch.due_date !== undefined) scalarPatch.due_date = patch.due_date;
      if (patch.start_date !== undefined) scalarPatch.start_date = patch.start_date;

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
    onSuccess: (task) => writeTaskEverywhere(queryClient, task),
  });
}

export function useDeleteTask(listId: string) {
  const queryClient = useQueryClient();
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
  });
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
    onSuccess: (task) => {
      if (task.rebalanced) {
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
      toast.success("Taklif yuborildi");
    },
    onError: (err) => {
      if (isApiError(err) && err.code === "conflict") {
        toast.error("Bu foydalanuvchi allaqachon a'zo yoki taklif qilingan.");
        return;
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
    onError: (err) => toast.error(errorMessage(err)),
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
