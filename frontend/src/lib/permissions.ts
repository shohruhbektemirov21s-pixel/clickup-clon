import type { MyPermissions, PermissionCode, SpaceAccess } from "@/types/api";

/**
 * Permission helpers for UI affordances.
 *
 * ⚠️ SECURITY: `can()` / `canInSpace()` decide only what the UI *shows*.
 * They are a convenience layer over `GET workspaces/{id}/my-permissions/`
 * and can be trivially bypassed from the browser. The server re-checks every
 * permission independently on every request (DESIGN_PERMISSIONS §C.4:
 * 404 → 403 → 400). Never treat a `true` here as authorisation.
 */

/**
 * Local grants a space `manager` (PM) gains inside their own space.
 * Mirrors `SPACE_MANAGER_GRANTS` on the server (DESIGN_PERMISSIONS §B.5).
 * `space.delete`, `member.*`, `workspace.*` and `tag.*` are never included.
 */
const SPACE_MANAGER_GRANTS: ReadonlySet<PermissionCode> = new Set<PermissionCode>([
  "space.update",
  "space.manage_members",
  "space.manage_statuses",
  "folder.create",
  "folder.update",
  "folder.delete",
  "folder.delete_cascade",
  "list.create",
  "list.update",
  "list.delete",
  "list.move",
  "list.manage_statuses",
  "task.read",
  "task.create",
  "task.update",
  "task.update_assigned",
  "task.delete",
  "task.move",
  "task.assign",
  "task.watch",
  "task.restore",
  "task.view_deleted",
  "attachment.read",
  "attachment.create",
  "attachment.delete_own",
  // `attachment.delete_any` is deliberately absent — moderation stays global.
]);

/** Codes a space `viewer` keeps; everything else is cut (§B.5). */
const SPACE_VIEWER_GRANTS: ReadonlySet<PermissionCode> = new Set<PermissionCode>([
  "workspace.read",
  "space.read",
  "task.read",
  "attachment.read",
]);

/** Workspace-level check. The owner short-circuits to `true` (AD-3). */
export function can(my: MyPermissions | undefined, code: PermissionCode): boolean {
  if (!my) return false;
  if (my.role === "owner") return true;
  return my.permissions.includes(code);
}

/** Access level the caller holds in a given space, or `undefined` if none. */
export function spaceAccess(
  my: MyPermissions | undefined,
  spaceId: string,
): SpaceAccess | undefined {
  return my?.spaces.find((s) => s.space_id === spaceId)?.access;
}

/**
 * Space-scoped check: the lowest privilege wins (§B.5).
 * - `viewer` → every write is cut, regardless of the workspace role.
 * - `manager` → workspace grants plus the fixed local PM grant set.
 * - otherwise → the plain workspace check.
 */
export function canInSpace(
  my: MyPermissions | undefined,
  spaceId: string,
  code: PermissionCode,
): boolean {
  if (!my) return false;
  if (my.role === "owner") return true;
  const access = spaceAccess(my, spaceId);
  if (access === "viewer") {
    // Read-only membership: only the read codes survive.
    return SPACE_VIEWER_GRANTS.has(code) && can(my, code);
  }
  if (access === "manager" && SPACE_MANAGER_GRANTS.has(code)) return true;
  return can(my, code);
}
