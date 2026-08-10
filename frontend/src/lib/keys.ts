/** Canonical TanStack Query cache keys (docs/UI_SPEC.md §5). */
export const keys = {
  me: ["me"] as const,
  workspaces: ["workspaces"] as const,
  workspace: (id: string) => ["workspace", id] as const,
  tree: (workspaceId: string) => ["workspace", workspaceId, "tree"] as const,
  members: (workspaceId: string) => ["workspace", workspaceId, "members"] as const,
  /** A'zo profili (§4.1) — bitta a'zoning statistikasi va bo'limlari. */
  memberProfile: (workspaceId: string, userId: string) =>
    ["workspace", workspaceId, "member-profile", userId] as const,
  /** Ish maydoni faoliyat tasmasi (§10.8). `actorId: null` — hamma aktyorlar. */
  activity: (workspaceId: string, actorId: string | null) =>
    ["workspace", workspaceId, "activity", actorId ?? "all"] as const,
  invitations: (workspaceId: string) =>
    ["workspace", workspaceId, "invitations"] as const,
  tags: (workspaceId: string) => ["workspace", workspaceId, "tags"] as const,
  /**
   * Workspace-wide task reads (dashboard, member profile). `scope` keeps the
   * filter sets apart: `all`, `mine`, or `user:<uuid>` for one assignee.
   */
  workspaceTasks: (workspaceId: string, scope: "all" | "mine" | `user:${string}`) =>
    ["workspace", workspaceId, "tasks", scope] as const,
  /** Prefix of every `workspaceTasks` scope — one invalidation covers them all. */
  workspaceTasksRoot: (workspaceId: string) =>
    ["workspace", workspaceId, "tasks"] as const,
  search: (workspaceId: string, q: string) =>
    ["workspace", workspaceId, "search", q] as const,
  list: (listId: string) => ["list", listId] as const,
  statusSet: (listId: string) => ["list", listId, "status-set"] as const,
  /** All task queries of a list share the ['tasks', listId] prefix. */
  tasksRoot: (listId: string) => ["tasks", listId] as const,
  tasksGrouped: (listId: string) =>
    ["tasks", listId, {}, { groupBy: "status" }] as const,
  task: (taskId: string) => ["task", taskId] as const,
  comments: (taskId: string) => ["comments", taskId] as const,
  attachments: (taskId: string) => ["attachments", taskId] as const,
  /** Static permission catalog — workspace-independent, effectively immutable. */
  permissionCatalog: ["permissions", "catalog"] as const,
  myPermissions: (workspaceId: string) =>
    ["workspace", workspaceId, "my-permissions"] as const,
  rolePermissions: (workspaceId: string) =>
    ["workspace", workspaceId, "role-permissions"] as const,
  /** Bo'lim jamoasi (§D.6) — `GET spaces/{id}/members/`. */
  spaceMembers: (spaceId: string) => ["space", spaceId, "members"] as const,
  /** Public taklif ko'rinishi — `/invite/[token]`. */
  invitationLookup: (token: string) => ["invitation-lookup", token] as const,
};
