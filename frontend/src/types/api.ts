/**
 * API payload types — mirrors docs/API_CONTRACT.md v1.0.0 field-for-field.
 * All timestamps are ISO-8601 UTC strings with a trailing "Z".
 * All ids are UUIDv4 strings.
 */

// ---------------------------------------------------------------------------
// Global conventions
// ---------------------------------------------------------------------------

export type Role = "owner" | "admin" | "member" | "guest";
export type InvitableRole = Exclude<Role, "owner">;
export type Priority = "urgent" | "high" | "normal" | "low" | "none";
export type StatusType = "open" | "active" | "closed";
export type ViewKind = "list" | "board";

/** §1.5 pagination envelope for every collection endpoint. */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** §1.6 closed error-code vocabulary. */
export type ApiErrorCode =
  | "validation_error"
  | "bad_request"
  | "invalid_status_for_list"
  | "authentication_failed"
  | "token_not_valid"
  | "permission_denied"
  | "not_found"
  | "method_not_allowed"
  | "conflict"
  | "position_conflict"
  | "unsupported_media_type"
  | "throttled"
  | "server_error";

/** §1.6 error envelope: every non-2xx body has exactly this shape. */
export interface ApiErrorEnvelope {
  error: {
    code: ApiErrorCode;
    message: string;
    details: Record<string, unknown>;
    /** Reserved — may appear later; tolerate absence and presence. */
    request_id?: string;
  };
}

// ---------------------------------------------------------------------------
// §2 Auth & profile
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar: string | null;
  avatar_color: string;
  timezone: string;
  date_joined: string;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Embedded everywhere a user appears inside another resource. */
export interface UserSummary {
  id: string;
  email: string;
  full_name: string;
  avatar: string | null;
  avatar_color: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
  workspace_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface TokenPair {
  access: string;
  refresh: string;
}

export interface UpdateMeRequest {
  full_name?: string;
  timezone?: string;
  avatar_color?: string;
}

// ---------------------------------------------------------------------------
// §3 Workspaces
// ---------------------------------------------------------------------------

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description: string;
  color: string;
  avatar: string | null;
  owner_id: string;
  member_count: number;
  /** Serializer-derived, read-only: the caller's role (contract R16). */
  my_role: Role;
  /**
   * Optimistic-concurrency counter for the role/permission matrix (§18).
   * Bumped server-side on every matrix write; read-only for clients.
   */
  permissions_version: number;
  created_at: string;
  updated_at: string;
}

export interface CreateWorkspaceRequest {
  id?: string;
  name: string;
  description?: string;
  color?: string;
}

/** `workspaces/{id}/tree/` — nested sidebar structure, no envelope. */
export interface WorkspaceTree {
  id: string;
  name: string;
  spaces: TreeSpace[];
}

export interface TreeSpace {
  id: string;
  name: string;
  color: string;
  icon: string | null;
  is_private: boolean;
  archived: boolean;
  position: string;
  folders: TreeFolder[];
  /** Folderless lists of this space (`folder_id: null`). */
  lists: TreeList[];
}

export interface TreeFolder {
  id: string;
  name: string;
  color: string;
  archived: boolean;
  position: string;
  lists: TreeList[];
}

export interface TreeList {
  id: string;
  name: string;
  color: string;
  folder_id: string | null;
  archived: boolean;
  position: string;
  task_count: number;
  open_task_count: number;
}

// ---------------------------------------------------------------------------
// §4 Workspace members
// ---------------------------------------------------------------------------

export interface Member {
  /** Membership row uuid (the path param is the *user* id, not this). */
  id: string;
  user: UserSummary;
  role: Role;
  invited_by_id: string | null;
  joined_at: string;
  last_active_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// §5 Invitations
// ---------------------------------------------------------------------------

export type InvitationStatus = "pending" | "accepted" | "revoked" | "expired";

export interface Invitation {
  id: string;
  workspace_id: string;
  email: string;
  role: InvitableRole;
  status: InvitationStatus;
  invited_by: UserSummary;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  sent_count: number;
  last_sent_at: string;
  created_at: string;
  updated_at: string;
}

/** `invitations/lookup/?token=` — the sole token-based read. */
export interface InvitationLookup {
  workspace_name: string;
  email: string;
  role: InvitableRole;
  expires_at: string;
}

export interface AcceptInvitationResponse {
  workspace_id: string;
  member: Member;
}

// ---------------------------------------------------------------------------
// §6 Spaces
// ---------------------------------------------------------------------------

export interface Space {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  color: string;
  icon: string | null;
  is_private: boolean;
  archived: boolean;
  position: string;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// §7 Folders
// ---------------------------------------------------------------------------

export interface Folder {
  id: string;
  space_id: string;
  name: string;
  color: string;
  archived: boolean;
  position: string;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// §8 Lists
// ---------------------------------------------------------------------------

export interface List {
  id: string;
  space_id: string;
  folder_id: string | null;
  name: string;
  description: string;
  color: string;
  archived: boolean;
  default_view: ViewKind;
  task_count: number;
  open_task_count: number;
  position: string;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface MoveListRequest {
  folder_id: string | null;
  before_id?: string | null;
  after_id?: string | null;
}

// ---------------------------------------------------------------------------
// §9 Status sets & statuses
// ---------------------------------------------------------------------------

export interface Status {
  id: string;
  name: string;
  color: string;
  type: StatusType;
  /** Integer, 0-based, contiguous — NOT the fractional position scheme. */
  order: number;
  is_default: boolean;
}

export interface StatusSet {
  id: string;
  name: string;
  space_id: string | null;
  list_id: string | null;
  statuses: Status[];
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// §10 Tasks
// ---------------------------------------------------------------------------

export interface Task {
  id: string;
  list_id: string;
  title: string;
  description_html: string | null;
  description_json: unknown | null;
  status_id: string;
  priority: Priority;
  /** Server-computed fractional base-62 key; never written by clients. */
  position: string;
  due_date: string | null;
  start_date: string | null;
  time_estimate_minutes: number | null;
  archived: boolean;
  is_deleted: boolean;
  completed_at: string | null;
  comment_count: number;
  assignees: UserSummary[];
  watchers: UserSummary[];
  tags: TagSummary[];
  created_by: UserSummary | null;
  updated_by: UserSummary | null;
  created_at: string;
  updated_at: string;
}

/** Tag shape as embedded on a Task. */
export interface TagSummary {
  id: string;
  name: string;
  color: string;
}

/** Writable fields for POST lists/{id}/tasks/ and PATCH tasks/{id}/. */
export interface TaskWriteRequest {
  id?: string;
  title?: string;
  description_html?: string | null;
  description_json?: unknown | null;
  status_id?: string;
  priority?: Priority;
  due_date?: string | null;
  start_date?: string | null;
  time_estimate_minutes?: number | null;
  assignee_ids?: string[];
  tag_ids?: string[];
  archived?: boolean;
}

/** §10.3 — client never sends a raw position. */
export interface MoveTaskRequest {
  list_id: string;
  status_id: string;
  before_id: string | null;
  after_id: string | null;
}

export interface MoveTaskResponse extends Task {
  /** true → the (list_id, status_id) scope was renumbered; refetch, don't patch. */
  rebalanced: boolean;
}

/** §10.4 grouped Board payload — NOT the standard envelope. */
export interface GroupedTasksResponse {
  group_by: "status";
  groups: TaskGroup[];
}

export interface TaskGroup {
  status_id: string;
  count: number;
  results: Task[];
}

// ---------------------------------------------------------------------------
// §11 Tags
// ---------------------------------------------------------------------------

export interface Tag {
  id: string;
  workspace_id: string;
  name: string;
  color: string;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// §12 Comments
// ---------------------------------------------------------------------------

export interface Comment {
  id: string;
  task_id: string;
  parent_id: string | null;
  /** null for hard-deleted users — render "Deleted user". */
  author: UserSummary | null;
  body_html: string;
  body_json: unknown;
  is_edited: boolean;
  edited_at: string | null;
  reply_count: number;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateCommentRequest {
  id?: string;
  body_html: string;
  body_json: unknown;
  parent_id?: string | null;
}

// ---------------------------------------------------------------------------
// §13 Search
// ---------------------------------------------------------------------------

export type SearchResultItem =
  | { type: "task"; item: Task }
  | { type: "list"; item: List }
  | { type: "folder"; item: Folder }
  | { type: "space"; item: Space };

export type SearchResponse = Paginated<SearchResultItem>;

// ---------------------------------------------------------------------------
// §15 WebSocket contract
// ---------------------------------------------------------------------------

export type WsEventType =
  | "connection.ack"
  | "permission.updated"
  | "access.revoked"
  | "task.created"
  | "task.updated"
  | "task.moved"
  | "task.deleted"
  | "comment.created"
  | "comment.updated"
  | "comment.deleted"
  | "list.updated"
  | "presence.join"
  | "presence.leave"
  | "presence.sync"
  | "error";

export interface WsActor {
  id: string;
  /** Echo of the X-Client-Id header for the mutation, or null. */
  client_id: string | null;
}

export interface WsPayload<TData = unknown> {
  event_id: string;
  ts: string;
  list_id?: string;
  workspace_id?: string;
  actor?: WsActor;
  data: TData;
  /** Only on task.moved. */
  rebalanced?: boolean;
}

export interface WsFrame<TData = unknown> {
  type: WsEventType;
  payload: WsPayload<TData>;
}

export interface WsTaskDeletedData {
  id: string;
  list_id: string;
}

export interface WsCommentDeletedData {
  id: string;
  task_id: string;
}

export interface WsConnectionAckData {
  channel: string;
  user_id: string;
}

export interface WsErrorData {
  code: ApiErrorCode;
  message: string;
}

export interface WsPresenceData {
  user?: UserSummary;
  users?: UserSummary[];
}

export interface WsPermissionUpdatedData {
  workspace_id: string;
  version: number;
}

export interface WsAccessRevokedData {
  workspace_id: string;
  space_id: string | null;
}

// ---------------------------------------------------------------------------
// §18 Granular permission matrix (docs/DESIGN_PERMISSIONS.md §D, §E)
// ---------------------------------------------------------------------------

/**
 * The closed catalog of permission codes — 44 codes across 8 groups.
 * Codes are never removed from the catalog, only flagged `deprecated`
 * server-side, so this union only ever grows.
 */
export type PermissionCode =
  | "workspace.read"
  | "workspace.update"
  | "workspace.delete"
  | "workspace.manage_permissions"
  | "workspace.transfer_ownership"
  | "member.read"
  | "member.invite"
  | "member.remove"
  | "member.role_change"
  | "invitation.read"
  | "invitation.manage"
  | "space.read"
  | "space.read_private"
  | "space.create"
  | "space.update"
  | "space.delete"
  | "space.manage_members"
  | "space.manage_statuses"
  | "folder.create"
  | "folder.update"
  | "folder.delete"
  | "folder.delete_cascade"
  | "list.create"
  | "list.update"
  | "list.delete"
  | "list.move"
  | "list.manage_statuses"
  | "task.read"
  | "task.create"
  | "task.update"
  | "task.update_assigned"
  | "task.delete"
  | "task.move"
  | "task.assign"
  | "task.watch"
  | "task.restore"
  | "task.view_deleted"
  | "comment.create"
  | "comment.update_own"
  | "comment.delete_own"
  | "comment.delete_any"
  | "tag.create"
  | "tag.update"
  | "tag.delete";

export type PermissionGroupKey =
  | "workspace"
  | "member"
  | "space"
  | "folder"
  | "list"
  | "task"
  | "comment"
  | "tag";

/** Roles a matrix row can exist for. `owner` is never stored (AD-3). */
export type AssignableRole = Exclude<Role, "owner">;

/** Access level of a `SpaceMember` row (§B.1). */
export type SpaceAccess = "viewer" | "contributor" | "manager";

export interface PermissionDef {
  code: PermissionCode;
  label: string;
  description: string;
  /** Default grants. `owner` is NEVER present here. */
  default_roles: AssignableRole[];
  /** Never grantable to a non-owner role — the server rejects it with 400. */
  owner_only: boolean;
  /** Destructive / far-reaching — the UI shows a warning marker. */
  sensitive: boolean;
}

export interface PermissionGroup {
  key: PermissionGroupKey;
  label: string;
  permissions: PermissionDef[];
}

/** `GET permissions/` — static catalog, no pagination envelope. */
export interface PermissionCatalog {
  catalog_version: number;
  groups: PermissionGroup[];
}

/** One stored deviation from the default matrix. */
export interface RolePermissionRow {
  role: AssignableRole;
  permission: PermissionCode;
  allowed: boolean;
  updated_by_id: string | null;
  updated_at: string;
}

/** `GET|PUT workspaces/{id}/role-permissions/`. */
export interface RolePermissionMatrix {
  workspace_id: string;
  /** Optimistic-concurrency token — echo it back as `expected_version`. */
  version: number;
  catalog_version: number;
  roles: Record<Role, { locked: boolean; permissions: PermissionCode[] }>;
  /** Cells differing from the default matrix — drives the "changed" marker. */
  overrides: RolePermissionRow[];
}

/** Sparse patch: only the cells that actually changed are sent. */
export interface UpdateRolePermissionsRequest {
  expected_version: number;
  roles: Partial<Record<AssignableRole, Partial<Record<PermissionCode, boolean>>>>;
}

/** `null` resets every role back to the catalog defaults. */
export interface ResetRolePermissionsRequest {
  role: AssignableRole | null;
}

/** `GET workspaces/{id}/my-permissions/` — the single source for UI gating. */
export interface MyPermissions {
  workspace_id: string;
  role: Role;
  version: number;
  permissions: PermissionCode[];
  spaces: { space_id: string; access: SpaceAccess }[];
}
