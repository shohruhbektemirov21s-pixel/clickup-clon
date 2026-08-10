"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { useMe, useMyPermissions } from "@/hooks/queries";
import { can } from "@/lib/permissions";
import type { Task } from "@/types/api";

/**
 * Board-level permission facade.
 *
 * The default matrix no longer lets a plain `member` touch *any* task: moving
 * a foreign card needs `task.move`, while a card the caller is assigned to only
 * needs `task.update_assigned`. The board therefore has to decide draggability
 * **per card**, not once for the whole view.
 *
 * ⚠️ UI-only. The server re-checks `task.move` / `task.update_assigned` on every
 * `PATCH tasks/{id}/move/`; a `true` here is an affordance, never authorisation.
 */
export interface BoardPermissions {
  /** `task.create` — gates the column `＋` and the empty-column CTA. */
  canCreate: boolean;
  /** `task.move` — the caller may move *any* card in the list. */
  canMoveAny: boolean;
  /** True when at least one drag path exists, so `DndContext` gets sensors. */
  canDragSome: boolean;
  /** Per-card check: `task.move`, or `task.update_assigned` on an own card. */
  canMoveTask: (task: Task) => boolean;
}

export function useBoardPermissions(canEdit: boolean): BoardPermissions {
  const params = useParams<{ workspaceId?: string | string[] }>();
  const rawWorkspaceId = params?.workspaceId;
  const workspaceId = Array.isArray(rawWorkspaceId)
    ? (rawWorkspaceId[0] ?? "")
    : (rawWorkspaceId ?? "");

  const { data: my } = useMyPermissions(workspaceId);
  const { data: me } = useMe();

  // `canEdit` is the coarse gate the page already applies (guests are read-only);
  // the permission codes refine it.
  const canMoveAny = canEdit && can(my, "task.move");
  const canUpdateAssigned = canEdit && can(my, "task.update_assigned");
  const canCreate = canEdit && can(my, "task.create");
  const myUserId = me?.id;

  const canMoveTask = React.useCallback(
    (task: Task) => {
      if (canMoveAny) return true;
      if (!canUpdateAssigned || !myUserId) return false;
      return task.assignees.some((a) => a.id === myUserId);
    },
    [canMoveAny, canUpdateAssigned, myUserId],
  );

  return {
    canCreate,
    canMoveAny,
    canDragSome: canMoveAny || canUpdateAssigned,
    canMoveTask,
  };
}
