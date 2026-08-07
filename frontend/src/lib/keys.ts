/** Canonical TanStack Query cache keys (docs/UI_SPEC.md §5). */
export const keys = {
  me: ["me"] as const,
  workspaces: ["workspaces"] as const,
  workspace: (id: string) => ["workspace", id] as const,
  tree: (workspaceId: string) => ["workspace", workspaceId, "tree"] as const,
  members: (workspaceId: string) => ["workspace", workspaceId, "members"] as const,
  invitations: (workspaceId: string) =>
    ["workspace", workspaceId, "invitations"] as const,
  tags: (workspaceId: string) => ["workspace", workspaceId, "tags"] as const,
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
};
