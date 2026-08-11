import * as React from "react";
import { useMe, useMyPermissions } from "@/hooks/queries";
import { contentPermissions, type ContentPermissions } from "@/lib/permissions";

/**
 * Board-level permission facade.
 *
 * The default matrix no longer lets a plain `member` touch *any* task: moving
 * a foreign card needs `task.move`, while a card the caller is assigned to only
 * needs `task.update_assigned`. The board therefore has to decide draggability
 * **per card**, not once for the whole view.
 *
 * The codes are resolved inside the list's own space (`canInSpace`), exactly
 * like the server's `has_space_perm`: a space `viewer` holding a workspace
 * `task.move` still gets a frozen board (§B.5).
 *
 * ⚠️ UI-only. The server re-checks `task.move` / `task.update_assigned` on every
 * `PATCH tasks/{id}/move/`; a `true` here is an affordance, never authorisation.
 */
export type BoardPermissions = ContentPermissions;

/**
 * @param workspaceId `my-permissions` so'rovi uchun.
 * @param spaceId Doska tegishli bo'lim (`List.space_id`); `undefined` bo'lsa
 *   fasad `isLoading` holatida qoladi va sudrash umuman yoqilmaydi.
 */
export function useBoardPermissions(
  workspaceId: string,
  spaceId: string | undefined,
): BoardPermissions {
  const { data: my } = useMyPermissions(workspaceId);
  const { data: me } = useMe();
  const meId = me?.id;

  return React.useMemo(
    () => contentPermissions(my, spaceId, meId),
    [my, spaceId, meId],
  );
}
