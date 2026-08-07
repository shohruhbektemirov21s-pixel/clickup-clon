# API Contract — Clickish (ClickUp clone) MVP

| | |
|---|---|
| **Document** | API_CONTRACT.md |
| **Version** | 1.0.0 |
| **Date** | 2026-08-07 |
| **Status** | **Binding** — backend and frontend implement against this document in parallel. Changes require a PR that updates this file in the same commit. |
| **Authority** | This doc > PRD.md for API surface. `docs/DATA_MODEL.md` is authoritative for field names/types; this doc mirrors it field-for-field. |
| **Upstream** | `docs/DATA_MODEL.md`, `docs/PRD.md`, `backend/config/{settings,pagination,exceptions}.py`, `backend/apps/realtime/middleware.py` |

**Inventory: 64 REST endpoints + 2 WebSocket channels.** Adding an endpoint requires amending this doc in the same commit.

---

## 1. Global conventions

### 1.1 Base path & URLs

- Base path: **`/api/v1/`**. Every path below is relative to it.
- **Every path ends with a trailing slash.** `GET /api/v1/tasks/{id}` (no slash) is not part of the contract; clients must always send the slash.
- All request/response bodies are `application/json` (UTF-8), except `POST me/avatar/` (`multipart/form-data`).
- Every JSON key is `snake_case`. Enum values are lowercase English and are never localized.
- The list resource is named **`list`** in every path and field (`/lists/{id}/`, `list_id`) even though the Django model is `TaskList`. `task_list` never appears in JSON.

### 1.2 IDs and timestamps

- **Every primary key is a UUIDv4**, serialized as the canonical lowercase hex string.
- **Client-generated ids:** any `POST` creating a resource MAY include `"id"` (a client-generated UUIDv4) to support optimistic creation. If the id is already in use the server responds `409 conflict` and creates nothing (this makes network retries safe to detect).
- Every resource carries `created_at` and `updated_at`.
- **All timestamps are ISO-8601 UTC with a trailing `Z`** (`"2026-08-07T09:15:00Z"`). The API never emits a non-`Z` offset. Clients render in the user's `timezone` (from `GET me/`); storage and transport are always UTC.
- Soft-deleted resources (Task, Comment only) serialize a derived boolean `is_deleted`; the raw `deleted_at` column is not serialized. The only write of `deleted_at` is the admin restore (`PATCH tasks/{id}/` with `{"deleted_at": null}`, §9.6).

### 1.3 Authentication

JWT via `djangorestframework-simplejwt`.

- Header on every authenticated request: `Authorization: Bearer <access>`.
- Access tokens carry claims `user_id` and `email`.
- Token lifetimes are environment-configured (`ACCESS_TOKEN_LIFETIME_MINUTES`, `REFRESH_TOKEN_LIFETIME_DAYS`; dev defaults **60 min / 7 days**). Clients MUST NOT hard-code lifetimes — decode `exp` and refresh proactively (~2 min before expiry).
- Refresh rotation is ON with blacklist: every `POST auth/refresh/` returns a **new** `access` AND a **new** `refresh`; the used refresh token is blacklisted. Replaying it returns `401 token_not_valid`.
- Refresh tokens are returned in the JSON body, not cookies (flagged review item OQ-1; if this changes, this doc changes).
- Unauthenticated requests to any endpoint except `auth/register/`, `auth/login/`, `auth/refresh/`, `invitations/lookup/`, `health/` return `401`.

### 1.4 Client id header (realtime echo suppression)

Every **mutating** request (`POST`/`PATCH`/`PUT`/`DELETE`) SHOULD carry `X-Client-Id: <per-tab uuid>`. The server echoes it as `actor.client_id` in the WebSocket frame for that mutation; a client ignores frames whose `actor.client_id` equals its own. A missing header is not an error — it just degrades to a visible echo.

### 1.5 Pagination envelope (all collections)

Matches `config/pagination.py` (`StandardPagination`, DRF `PageNumberPagination`):

```json
{
  "count": 130,
  "next": "https://host/api/v1/lists/{id}/tasks/?page=3",
  "previous": "https://host/api/v1/lists/{id}/tasks/?page=1",
  "results": [ ... ]
}
```

- Query params: `?page=` (1-based) and `?page_size=` (default **50**, max **200**).
- `page_size > 200` → `400 validation_error`. A `page` past the end → `404 not_found` (DRF default).
- Every collection endpoint is paginated; no unbounded endpoint exists. Exceptions that return non-paginated bodies: `workspaces/{id}/tree/` (nested tree) and the `?group_by=status` grouped payload (§9.4).
- Single resources are bare JSON objects (no envelope).

> Ruling: the PRD's `{"count","page","page_size","total_pages",...}` envelope is superseded by the implemented `StandardPagination` shape above. Clients derive page/total_pages from `count`, `page_size` and the `next`/`previous` URLs.

### 1.6 Error envelope (all errors)

Matches `config/exceptions.py`. Every non-2xx response has exactly this shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request payload is invalid.",
    "details": { "email": ["A user with this email already exists."] }
  }
}
```

- `details` is an object; for validation errors it maps field name → array of messages. For non-field errors it may be `{}` or `{"detail": "..."}`.
- `request_id` is **reserved**: servers MAY add `"request_id": "req_..."` to the `error` object later; clients MUST tolerate its absence and presence. (Not emitted by the current handler.)

**Error code vocabulary (closed set):**

| HTTP | `code` | When |
|---|---|---|
| 400 | `validation_error` | Any serializer/field validation failure |
| 400 | `bad_request` | Malformed request that is not field-mappable |
| 400 | `invalid_status_for_list` | `status_id` not in the list's effective status set (task create/update/move) |
| 401 | `authentication_failed` | Missing/invalid credentials; no or malformed `Authorization` header |
| 401 | `token_not_valid` | Expired/blacklisted/invalid JWT (login again or refresh) |
| 403 | `permission_denied` | Authenticated, in the workspace, but role forbids the action |
| 404 | `not_found` | Missing resource, soft-deleted resource, **or any resource outside the caller's workspaces** (existence is never disclosed cross-tenant — never 403) |
| 405 | `method_not_allowed` | Wrong verb |
| 409 | `conflict` | Duplicate client-supplied `id`, duplicate pending invite, last-owner violations, PROTECT violations, terminal-state transitions |
| 409 | `position_conflict` | Stale `before_id`/`after_id` neighbours on a move; client refetches neighbours and retries once |
| 415 | `unsupported_media_type` | Wrong content type |
| 429 | `throttled` | Rate limit (login, register, comment spam, invite resend) |
| 500 | `server_error` | Unhandled server failure |

Every authenticated endpoint may return `401`, `404`, `405`, `429`, `500`; per-endpoint tables below list only the codes specific to that endpoint.

### 1.7 Roles

Per-workspace role on `WorkspaceMember.role`: **`owner` > `admin` > `member` > `guest`**. "admin+" below means owner or admin; "member+" means owner/admin/member. Special cases:
- `guest` may **PATCH/move only tasks where they are in the assignees** ("Assignee" below), may create comments, may watch/unwatch, everything else read-only. Guests cannot read the member roster or invitations, and cannot see private spaces (`is_private=true`).
- Everyone edits/deletes **their own** comments; admin+ may delete (not edit) any comment.
- Permission is checked before validation. In-workspace denial → `403`; out-of-workspace → `404`.

### 1.8 Common query params on task collections

See §9.5 for the full filter vocabulary. Defaults everywhere: `archived=false`, soft-deleted excluded (`include_deleted=true` is admin+ only, else `403`).

---

## 2. Auth & profile — `apps.accounts`

| # | Method | Path | Auth | Roles | Success |
|---|---|---|---|---|---|
| 1 | POST | `auth/register/` | public | — | `201` `{access, refresh, user}` |
| 2 | POST | `auth/login/` | public | — | `200` `{access, refresh, user}` |
| 3 | POST | `auth/refresh/` | public (needs refresh token) | — | `200` `{access, refresh}` |
| 4 | POST | `auth/logout/` | required | any | `204` empty |
| 5 | POST | `auth/password/change/` | required | any | `200` `{access, refresh}` |
| 6 | GET | `me/` | required | any | `200` User |
| 7 | PATCH | `me/` | required | any | `200` User |
| 8 | POST | `me/avatar/` | required | any | `200` User |

**Request bodies**

- `register`: `{"email", "password", "full_name"?, "workspace_name"?}`. Email stored lowercase; uniqueness is case-insensitive. Password runs Django's default validators. If `workspace_name` is present the server bootstraps a full workspace in the same transaction (workspace + owner membership + "Team Space" + default status set `TO DO/IN PROGRESS/COMPLETE` + "Getting Started" list + 3 sample tasks — DATA_MODEL §11). If absent, no workspace is created.
- `login`: `{"email", "password"}`. Failure → `401 authentication_failed`. Updates `last_login`.
- `refresh`: `{"refresh"}`. Rotates; old token blacklisted.
- `logout`: `{"refresh"}` — blacklists that refresh token only (other devices unaffected).
- `password/change`: `{"current_password", "new_password"}`. Wrong current password → `400 validation_error` on `current_password`. On success all the user's other refresh tokens are blacklisted and a fresh pair is returned.
- `PATCH me/`: any of `{"full_name", "timezone", "avatar_color"}`. `timezone` must be a valid IANA name (validated against `zoneinfo.available_timezones()`), else `400 validation_error`. Email change is out of MVP scope.
- `me/avatar/`: multipart field `avatar` — jpeg/png/webp, max 2 MB, resized server-side to 256×256. This is the **only** file upload in MVP.

**Errors:** register/login are throttled (`429 throttled`). Duplicate email on register → `400 validation_error` with `details.email`.

**User object** (full, from `me/` and auth responses):

```json
{
  "id": "8f14e45f-ea2b-4d1c-9d2c-6f1a2b3c4d5e",
  "email": "maya@acme.io",
  "full_name": "Maya Chen",
  "avatar": "https://host/media/avatars/2026/08/maya.webp",
  "avatar_color": "#7B68EE",
  "timezone": "Europe/Berlin",
  "date_joined": "2026-08-07T09:00:00Z",
  "last_seen_at": "2026-08-07T09:15:00Z",
  "created_at": "2026-08-07T09:00:00Z",
  "updated_at": "2026-08-07T09:15:00Z"
}
```

**UserSummary** (embedded everywhere a user appears inside another resource): `{"id", "email", "full_name", "avatar", "avatar_color"}`.

---

## 3. Workspaces — `apps.workspaces`

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 9 | GET | `workspaces/` | any authenticated (own memberships only) | `200` paginated Workspace[] |
| 10 | POST | `workspaces/` | any authenticated (caller becomes owner) | `201` Workspace |
| 11 | GET | `workspaces/{id}/` | owner/admin/member/guest | `200` Workspace |
| 12 | PATCH | `workspaces/{id}/` | **owner** | `200` Workspace |
| 13 | DELETE | `workspaces/{id}/` | **owner** | `204` empty |
| 14 | GET | `workspaces/{id}/tree/` | owner/admin/member/guest | `200` Tree |

- `POST workspaces/` body: `{"id"?, "name", "description"?, "color"?}`. Triggers the full bootstrap (DATA_MODEL §11). `slug` is server-derived from `name` (unique, immutable in MVP).
- `PATCH workspaces/{id}/`: `{"name"?, "description"?, "color"?}`. (Per PRD OQ-1 ruling: workspace settings are owner-only.)
- `DELETE workspaces/{id}/` body: `{"confirm_name": "<exact workspace name>"}` — mismatch → `400 validation_error`. Hard-cascades everything, irreversible.
- `tree/` returns the nested sidebar structure (no tasks), everything ordered `position ASC`, archived containers excluded unless `?archived=true`. For guests, private spaces are omitted.

**Workspace object:**

```json
{
  "id": "0f0e1d2c-3b4a-4596-8778-99aabbccddee",
  "name": "Acme Inc.",
  "slug": "acme-inc",
  "description": "",
  "color": "#7B68EE",
  "avatar": null,
  "owner_id": "8f14e45f-ea2b-4d1c-9d2c-6f1a2b3c4d5e",
  "member_count": 9,
  "my_role": "admin",
  "created_at": "2026-08-07T09:00:05Z",
  "updated_at": "2026-08-07T09:00:05Z"
}
```

`my_role` is derived per caller (read-only) so the frontend can gate affordances without reading the roster.

**Tree shape** (`workspaces/{id}/tree/`):

```json
{
  "id": "…workspace id…",
  "name": "Acme Inc.",
  "spaces": [
    {
      "id": "…", "name": "Product", "color": "#7B68EE", "icon": "rocket",
      "is_private": false, "archived": false, "position": "n",
      "folders": [
        { "id": "…", "name": "Q3 Roadmap", "color": "#7B68EE", "archived": false, "position": "n",
          "lists": [ { "id": "…", "name": "Sprint 24", "color": "#7B68EE", "folder_id": "…",
                        "archived": false, "position": "n", "task_count": 14, "open_task_count": 12 } ] }
      ],
      "lists": [ /* folderless lists of this space, same list shape with "folder_id": null */ ]
    }
  ]
}
```

---

## 4. Workspace members

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 15 | GET | `workspaces/{id}/members/` | owner/admin/**member** (guest → `403`) | `200` paginated Member[] |
| 16 | PATCH | `workspaces/{id}/members/{user_id}/` | owner; admin (non-owner targets, non-owner roles only) | `200` Member |
| 17 | DELETE | `workspaces/{id}/members/{user_id}/` | owner; admin (non-owner targets) | `204` empty |
| 18 | POST | `workspaces/{id}/members/leave/` | any member | `204` empty |

- `{user_id}` in the path is the **user's** id, not the membership row id.
- `PATCH` body: `{"role": "owner"|"admin"|"member"|"guest"}`. Rules: only an owner may grant `owner` or touch an owner; admin may change roles among `admin`/`member`/`guest` for non-owners; member/guest → `403`.
- Last-owner invariants → `409 conflict`: demoting the last owner, removing the last owner, or the last owner calling `leave/`. Ownership transfer = promote someone to `owner`, then demote/leave.
- Removing a member deletes their assignee/watcher rows in this workspace, keeps their comments and `created_by`/`updated_by` attributions, closes their live WebSocket subscriptions, and all their subsequent requests in this workspace return `404`.
- Roster ordering: rank `owner, admin, member, guest`, then email.

**Member object:**

```json
{
  "id": "…membership uuid…",
  "user": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null, "avatar_color": "#49CCF9" },
  "role": "member",
  "invited_by_id": "…user uuid or null…",
  "joined_at": "2026-08-07T10:00:00Z",
  "last_active_at": "2026-08-07T12:41:00Z",
  "created_at": "2026-08-07T10:00:00Z",
  "updated_at": "2026-08-07T10:00:00Z"
}
```

---

## 5. Invitations

| # | Method | Path | Auth | Roles | Success |
|---|---|---|---|---|---|
| 19 | GET | `workspaces/{id}/invitations/` | required | admin+ | `200` paginated Invitation[] |
| 20 | POST | `workspaces/{id}/invitations/` | required | admin+ | `201` Invitation |
| 21 | DELETE | `invitations/{id}/` | required | admin+ (revoke) | `204` empty |
| 22 | POST | `invitations/{id}/resend/` | required | admin+ | `200` Invitation |
| 23 | GET | `invitations/lookup/?token=<t>` | **public** | — | `200` lookup object |
| 24 | POST | `invitations/accept/` | required | invited email only | `200` `{workspace_id, member}` |
| 25 | POST | `invitations/decline/` | required | invited email only | `204` empty |

- `POST` body: `{"email", "role": "admin"|"member"|"guest"}` (`owner` is not invitable → `400 validation_error`). A second **pending** invite for the same `(workspace, email)`, or inviting an existing member → `409 conflict`.
- The raw `token` never appears in any API response (it travels only in the invitation email). `lookup/` is the sole token-based read: returns `{"workspace_name", "email", "role", "expires_at"}` and nothing else. Unknown/expired/revoked token → `404 not_found`.
- `accept/` / `decline/` body: `{"token"}`. Caller must be authenticated with the invited email, else `403 permission_denied`. Accept creates the `WorkspaceMember` with the invited role. Replay of a consumed token → `409 conflict`; unknown/expired → `404`. Decline marks the invitation `revoked` (no separate `declined` status exists in the data model).
- Expiry: `created_at + INVITATION_TTL_DAYS` (**7 days**, env-configurable). `resend/` refreshes `expires_at`, throttled to 1/5 min, max `sent_count` 5 (`429 throttled` / `409 conflict` past the cap). Revoking a non-pending invitation → `409 conflict`.

**Invitation object:**

```json
{
  "id": "…", "workspace_id": "…",
  "email": "carlos@client.com",
  "role": "guest",
  "status": "pending",
  "invited_by": { "id": "…", "email": "maya@acme.io", "full_name": "Maya Chen", "avatar": null, "avatar_color": "#7B68EE" },
  "expires_at": "2026-08-14T09:15:00Z",
  "accepted_at": null, "revoked_at": null,
  "sent_count": 1, "last_sent_at": "2026-08-07T09:15:00Z",
  "created_at": "2026-08-07T09:15:00Z", "updated_at": "2026-08-07T09:15:00Z"
}
```

`status` ∈ `pending | accepted | revoked | expired` (terminal states immutable; reads also treat `expires_at < now` as expired).

---

## 6. Spaces

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 26 | GET | `workspaces/{id}/spaces/` | any member (guests: non-private only) | `200` paginated Space[] |
| 27 | POST | `workspaces/{id}/spaces/` | admin+ | `201` Space |
| 28 | GET | `spaces/{id}/` | any member | `200` Space |
| 29 | PATCH | `spaces/{id}/` | admin+ | `200` Space |
| 30 | DELETE | `spaces/{id}/` | admin+ | `204` empty |

- `POST` body: `{"id"?, "name", "description"?, "color"?, "icon"?, "is_private"?}`. Creation auto-creates the space's default `StatusSet` (TO DO / IN PROGRESS / COMPLETE). Name is CI-unique per workspace (`409 conflict` on duplicate). Position auto-assigned at end of scope.
- `PATCH`: same fields plus `"archived"`.
- `DELETE` body: `{"confirm_name": "<exact space name>"}`; hard-cascades status set, folders, lists, tasks, comments.
- Collections accept `?archived=true|false` (default `false`).

**Space object:**

```json
{
  "id": "…", "workspace_id": "…",
  "name": "Engineering", "description": "", "color": "#2ECD6F", "icon": "rocket",
  "is_private": false, "archived": false, "position": "n",
  "created_by_id": "…user uuid…",
  "created_at": "2026-08-07T09:20:00Z", "updated_at": "2026-08-07T09:20:00Z"
}
```

---

## 7. Folders

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 31 | GET | `spaces/{id}/folders/` | any member | `200` paginated Folder[] |
| 32 | POST | `spaces/{id}/folders/` | member+ | `201` Folder |
| 33 | GET | `folders/{id}/` | any member | `200` Folder |
| 34 | PATCH | `folders/{id}/` | member+ | `200` Folder |
| 35 | DELETE | `folders/{id}/?strategy=cascade\|detach` | admin+ for `cascade`; member+ for `detach` | `204` empty |

- `POST` body: `{"id"?, "name", "color"?}`. Name CI-unique per space (`409`). Folders are pure grouping nodes: no statuses, no tasks, never nested.
- `DELETE`: `strategy=cascade` (default) deletes the folder and all its lists/tasks; `strategy=detach` moves its lists to the space root (`folder_id = null`, fresh positions at end of the space-root scope) then deletes the folder.

**Folder object:** `{"id", "space_id", "name", "color", "archived", "position", "created_by_id", "created_at", "updated_at"}`.

---

## 8. Lists

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 36 | GET | `spaces/{id}/lists/` | any member | `200` paginated List[] |
| 37 | POST | `spaces/{id}/lists/` | member+ | `201` List |
| 38 | GET | `lists/{id}/` | any member | `200` List |
| 39 | PATCH | `lists/{id}/` | member+ | `200` List |
| 40 | DELETE | `lists/{id}/` | member+ | `204` empty |
| 41 | PATCH | `lists/{id}/move/` | member+ | `200` List |

- `POST` body: `{"id"?, "name", "description"?, "color"?, "folder_id"?}`. **`folder_id` is optional** — omitted/`null` means the list sits directly under the space. A `folder_id` from another space → `400 validation_error`. Name CI-unique within its `(space, folder)` scope (`409`).
- `GET spaces/{id}/lists/` returns **all** lists of the space (folderless and foldered); filter client-side or with `?folder={folder_id}` / `?folder=none`.
- `PATCH`: `{"name"?, "description"?, "color"?, "archived"?, "default_view"?("list"|"board")}`. `folder_id` is NOT patchable — re-parenting goes through `move/`.
- `DELETE`: hard-cascades the list's own status set (if any), its tasks and their comments. No confirmation body (UI confirms).
- **`move/`** body: `{"folder_id": "<uuid|null>", "before_id"?, "after_id"?}` — re-parents within the **same space only** (a `space_id` in the body → `400 validation_error`, per OQ-2 ruling). `before_id`/`after_id` are sibling list ids in the destination scope (see §9.3 semantics); the server computes the new fractional `position`. Stale neighbours → `409 position_conflict`.

**List object:**

```json
{
  "id": "…", "space_id": "…", "folder_id": null,
  "name": "Sprint 24", "description": "", "color": "#7B68EE",
  "archived": false, "default_view": "list",
  "task_count": 14, "open_task_count": 12,
  "position": "n",
  "created_by_id": "…",
  "created_at": "2026-08-07T09:25:00Z", "updated_at": "2026-08-07T09:25:00Z"
}
```

---

## 9. Status sets & statuses

A `StatusSet` belongs to exactly one of a Space (default, always exists) or a List (optional override). A list's **effective** set = its own if present, else its space's. Statuses use an integer `order` (0-based, contiguous, assigned from array index), **not** the fractional `position` scheme.

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 42 | GET | `spaces/{id}/status-set/` | any member | `200` StatusSet |
| 43 | PUT | `spaces/{id}/status-set/` | admin+ | `200` StatusSet |
| 44 | GET | `lists/{id}/status-set/` | any member | `200` StatusSet (the **effective** set — the list's own if it exists, else the space's) |
| 45 | PUT | `lists/{id}/status-set/` | admin+ | `200` StatusSet (creates/replaces the list override) |
| 46 | DELETE | `lists/{id}/status-set/` | admin+ | `200` StatusSet (removes the override; returns the space set now in effect) |

**PUT body** (both scopes):

```json
{
  "name": "Bug workflow",
  "statuses": [
    { "id": "…keep-existing-uuid…", "name": "TO DO", "color": "#87909E", "type": "open",   "is_default": true },
    {                                "name": "IN REVIEW", "color": "#4194F6", "type": "active", "is_default": false },
    { "id": "…", "name": "SHIPPED", "color": "#6BC950", "type": "closed", "is_default": false }
  ],
  "status_mapping": { "<removed-or-old-status-id>": "<status-id-in-new-set>" }
}
```

- Array order defines `order` (0..n-1); a client-sent `order` is ignored. Reusing an existing status `id` updates that row; omitting an existing id deletes it; entries without `id` are created.
- Invariants (else `400 validation_error`): 1–30 statuses; exactly one `is_default: true` (and it must not be `closed`-type); ≥1 `closed`-type status; CI-unique names ≤60 chars.
- `status_mapping` must cover **every** old status still referenced by any task (incl. archived and soft-deleted) that is not present in the new set. Missing mapping for an in-use status → `409 conflict` with `error.details.status_mapping` (Task.status is PROTECT). Re-pointing happens in one transaction; a `task.updated` event is emitted per re-pointed task. Re-pointed tasks keep their `position` (ties resolved by `position ASC, created_at ASC` — never renumbered).
- `DELETE lists/{id}/status-set/` requires body `{"status_mapping": {...}}` mapping the list's statuses to the space's, same completeness rule.
- Changing a space's set affects only lists **without** an override.

**StatusSet object** (worked example for this group):

```json
{
  "id": "…", "name": "Default",
  "space_id": "…uuid or null…", "list_id": null,
  "statuses": [
    { "id": "…", "name": "TO DO",       "color": "#87909E", "type": "open",   "order": 0, "is_default": true  },
    { "id": "…", "name": "IN PROGRESS", "color": "#4194F6", "type": "active", "order": 1, "is_default": false },
    { "id": "…", "name": "COMPLETE",    "color": "#6BC950", "type": "closed", "order": 2, "is_default": false }
  ],
  "created_at": "2026-08-07T09:20:00Z", "updated_at": "2026-08-07T09:20:00Z"
}
```

`type` ∈ `open | active | closed`. Exactly one of `space_id`/`list_id` is non-null.

---

## 10. Tasks — `apps.tasks`

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 47 | GET | `lists/{id}/tasks/` | any member | `200` paginated Task[] (or grouped, §10.4) |
| 48 | POST | `lists/{id}/tasks/` | member+ (guest → `403`) | `201` Task |
| 49 | GET | `tasks/{id}/` | any member | `200` Task |
| 50 | PATCH | `tasks/{id}/` | member+; guest **Assignee** only | `200` Task |
| 51 | DELETE | `tasks/{id}/` | member+ (guest → `403`) | `204` empty (soft delete) |
| 52 | PATCH | `tasks/{id}/move/` | member+; guest **Assignee** only | `200` Task (+ `rebalanced`) |
| 53 | POST | `tasks/{id}/watch/` | any member | `201` Task (`200` if already watching — idempotent) |
| 54 | DELETE | `tasks/{id}/watch/` | any member | `204` empty (idempotent) |

### 10.1 Task object (worked example for this group)

```json
{
  "id": "3f2a9c1e-7b4d-4e2f-a1b2-c3d4e5f6a091",
  "list_id": "…",
  "title": "Fix login redirect",
  "description_html": "<p>Repro steps…</p>",
  "description_json": { "type": "doc", "content": [ … ] },
  "status_id": "…status uuid in the list's effective set…",
  "priority": "urgent",
  "position": "aV",
  "due_date": "2026-08-12T21:59:59Z",
  "start_date": null,
  "time_estimate_minutes": 90,
  "archived": false,
  "is_deleted": false,
  "completed_at": null,
  "comment_count": 3,
  "assignees": [ { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null, "avatar_color": "#49CCF9" } ],
  "watchers":  [ { "id": "…", "email": "maya@acme.io", "full_name": "Maya Chen", "avatar": null, "avatar_color": "#7B68EE" } ],
  "tags":      [ { "id": "…", "name": "backend", "color": "#FD71AF" } ],
  "created_by": { "id": "…", "email": "maya@acme.io", "full_name": "Maya Chen", "avatar": null, "avatar_color": "#7B68EE" },
  "updated_by": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null, "avatar_color": "#49CCF9" },
  "created_at": "2026-08-07T09:30:00Z",
  "updated_at": "2026-08-07T11:02:00Z"
}
```

Read-only fields: `position`, `comment_count`, `completed_at` (set/cleared by the server on transitions into/out of a `closed`-type status), `is_deleted`, `created_by`, `updated_by`, `watchers` (managed only via `watch/`), timestamps. `priority_order` is never serialized — it exists only as the `?ordering=priority_order` sort key.

### 10.2 Create / update

- `POST lists/{id}/tasks/` body: `{"id"?, "title"}` plus optionally `description_html` + `description_json` (both or neither — one without the other → `400 validation_error`), `status_id`, `priority`, `due_date`, `start_date`, `time_estimate_minutes`, `assignee_ids`, `tag_ids`.
  - Defaults: `status_id` → the effective set's `is_default` status; `priority` → `"none"`; `position` → end of the `(list_id, status_id)` column; empty arrays elsewhere. Creator is auto-added as a watcher.
- `PATCH tasks/{id}/` accepts the same writable fields. **Write field names:** `assignee_ids: [uuid]` and `tag_ids: [uuid]` (full-replace arrays); reads return the embedded `assignees`/`tags` arrays. `watcher_ids` is NOT patchable — use `watch/`. `list_id`/`position` are NOT patchable — use `move/`.
- Validation: `title` required, trimmed, non-empty, ≤500 chars. `priority` ∈ `urgent|high|normal|low|none`. `status_id` outside the list's effective set → `400 invalid_status_for_list`. `start_date > due_date` → `400 validation_error` (DB check constraint). Non-member ids in `assignee_ids` → `400 validation_error`; tags from another workspace → `400 validation_error`. `description_json` ≤ 256 KB; HTML sanitized server-side (nh3 allow-list).
- Assigning a user auto-adds them as a watcher; commenting auto-adds the commenter (self-removal is remembered against re-add by comments, not against re-assignment).
- `DELETE` is a **soft delete** (`deleted_at` set); the task disappears from all collections and `GET tasks/{id}/` → `404`. No restore endpoint; admin+ may restore within 30 days via `PATCH tasks/{id}/` with `{"deleted_at": null}` (the only accepted write of that field; others → `400`).

### 10.3 Move / reorder (fractional position — BINDING)

`PATCH tasks/{id}/move/`:

```json
{ "list_id": "…destination list…", "status_id": "…status valid in destination's effective set…",
  "before_id": "…task that ends up ABOVE the moved task, or null…",
  "after_id":  "…task that ends up BELOW it, or null…" }
```

- **The client never sends a raw `position`.** The server computes a base-62 lexicographic key strictly between the neighbours (`midstring`), compared as plain strings; first item in an empty column is `"n"`. Exactly one row is written — the server **never renumbers rows on a move**.
- Both neighbours `null` → empty column (or explicit "only item"); one `null` → top/bottom of column.
- `list_id` + `status_id` are always required; cross-list moves are supported (destination `status_id` must be valid for the destination's effective set, else `400 invalid_status_for_list`). Task position scope is `(list_id, status_id)`.
- Stale/reordered neighbours → `409 position_conflict`; client refetches neighbours and retries once.
- Response is the full Task plus a top-level `"rebalanced": boolean`. When a generated key would exceed 48 chars the server rebalances the whole `(list_id, status_id)` scope in one transaction and returns `"rebalanced": true`; clients (and WebSocket subscribers seeing it on `task.moved`) must refetch the column instead of patching locally.
- Guests may move only tasks where they are an assignee (`403` otherwise).

### 10.4 Reading tasks: flat and grouped

- `GET lists/{id}/tasks/` — flat, paginated. Default ordering: `status.order ASC, position ASC, created_at ASC`.
- `GET lists/{id}/tasks/?group_by=status` — Board payload, **not** the standard envelope:

```json
{
  "group_by": "status",
  "groups": [
    { "status_id": "…", "count": 57, "results": [ /* first page_size Tasks, position ASC, created_at ASC */ ] }
  ]
}
```

Groups appear for **every** status in the effective set (empty ones included), ordered by `status.order`. Each group carries its total `count`; "load more" for a column = `GET lists/{id}/tasks/?status=<status_id>&page=2` (flat envelope). Filters/ordering apply identically inside each group, and the union of groups equals the flat result for the same filters.

### 10.5 Filter & ordering vocabulary (exact, closed)

Applies to `lists/{id}/tasks/` and `workspaces/{id}/tasks/`. Different keys AND; repeated values of one key OR.

| Param | Values |
|---|---|
| `status` | status uuid, repeatable |
| `status_type` | `open` \| `active` \| `closed` |
| `assignee` | user uuid (repeatable) \| `me` \| `none` |
| `priority` | `urgent`\|`high`\|`normal`\|`low`\|`none`, repeatable |
| `tag` | tag uuid, repeatable |
| `due` | `overdue` \| `today` \| `this_week` \| `none` (`today`/`this_week` computed in the **caller's** timezone; `overdue` excludes closed-type tasks) |
| `due_before`, `due_after` | ISO-8601 UTC instant |
| `created_by`, `watcher` | user uuid |
| `q` | text search over `title` + description text; `q` < 2 chars → empty result set |
| `archived` | `true`\|`false`, default `false` |
| `include_deleted` | `true` — **admin+ only**, else `403 permission_denied` |
| `group_by` | `status` (list-tasks endpoint only) |
| `ordering` | one of `position`, `due_date`, `priority_order`, `created_at`, `updated_at`, `title`, each with optional `-` prefix. Default `position`. Anything else → `400 validation_error` |

---

## 11. Tags

Workspace-scoped; the same tag may label tasks across spaces.

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 55 | GET | `workspaces/{id}/tags/` | any member | `200` paginated Tag[] |
| 56 | POST | `workspaces/{id}/tags/` | member+ | `201` Tag |
| 57 | PATCH | `tags/{id}/` | member+ | `200` Tag |
| 58 | DELETE | `tags/{id}/` | member+ | `204` empty (hard delete; `TaskTag` rows cascade, tasks untouched) |

- Bodies: `{"id"?, "name", "color"?}`. Name CI-unique per workspace → `409 conflict` on duplicate. `usage_count` is read-only (drives "most used" ordering; default collection ordering `name ASC`, `?ordering=-usage_count` supported).

**Tag object:** `{"id", "workspace_id", "name", "color", "usage_count", "created_at", "updated_at"}`.

---

## 12. Comments — `apps.comments`

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 59 | GET | `tasks/{id}/comments/` | any member (incl. guest) | `200` paginated Comment[] |
| 60 | POST | `tasks/{id}/comments/` | any member (incl. guest) | `201` Comment |
| 61 | PATCH | `comments/{id}/` | **author only** (all roles; admins may NOT edit others') | `200` Comment |
| 62 | DELETE | `comments/{id}/` | author; admin+ may delete anyone's | `204` empty (soft delete) |

- `POST` body: `{"id"?, "body_html", "body_json", "parent_id"?}`. Both body fields required together (`400 validation_error` otherwise); `body_html` non-empty after sanitisation, ≤20 000 chars.
- **Replies:** one level deep. `parent_id` must be a top-level comment on the same task, else `400 validation_error`. Deleting a parent leaves replies visible under a "deleted" tombstone.
- Ordering: `created_at ASC` (chat-like), default `page_size` 50. Deleted comments are excluded from listings and from `comment_count` (which the server maintains on the task).
- Editing sets `is_edited: true` and `edited_at`. Creation is throttled (`429`).

**Comment object (worked example):**

```json
{
  "id": "…", "task_id": "…", "parent_id": null,
  "author": { "id": "…", "email": "carlos@client.com", "full_name": "Carlos Vega", "avatar": null, "avatar_color": "#FFC800" },
  "body_html": "<p>Looks good — can we ship Friday?</p>",
  "body_json": { "type": "doc", "content": [ … ] },
  "is_edited": false, "edited_at": null,
  "reply_count": 0, "is_deleted": false,
  "created_at": "2026-08-07T12:00:00Z", "updated_at": "2026-08-07T12:00:00Z"
}
```

`author` is `null` for hard-deleted users (render "Deleted user").

---

## 13. Search & cross-list queries

| # | Method | Path | Roles | Success |
|---|---|---|---|---|
| 63 | GET | `workspaces/{id}/tasks/` | any member (results permission-scoped) | `200` paginated Task[] |
| 64 | GET | `workspaces/{id}/search/?q=<text>` | any member (results permission-scoped) | `200` paginated mixed results |

- `workspaces/{id}/tasks/` = the cross-list task query; identical filter/ordering vocabulary as §10.5.
- `search/` returns mixed entities. `q` is required (empty → `400 validation_error`; 1 char → empty results). Result item shape:

```json
{ "count": 3, "next": null, "previous": null,
  "results": [
    { "type": "task",   "item": { …Task object… } },
    { "type": "list",   "item": { …List object… } },
    { "type": "folder", "item": { …Folder object… } },
    { "type": "space",  "item": { …Space object… } }
  ] }
```

- Permission scoping happens **before** pagination — `count` never leaks unreadable records. Guests never see private-space content. Never returns soft-deleted or (by default) archived items. Ranking may differ between SQLite (dev, icontains) and PostgreSQL (prod, full-text); result *sets* must be equivalent.

---

## 14. Health

| Method | Path | Auth | Success |
|---|---|---|---|
| GET | `health/` | **public** | `200` `{"status": "ok"}` |

(Endpoint 64 of 64 counting `health/`; see inventory note at top.)

---

## 15. WebSocket contract — `apps.realtime`

### 15.1 Channels & auth

| Channel | URL | Who may connect | Carries |
|---|---|---|---|
| List | `ws(s)://<host>/ws/list/{list_id}/?token=<access>` | anyone with read access to the list | `task.*`, `comment.*` for that list; presence for that list |
| Workspace | `ws(s)://<host>/ws/workspaces/{workspace_id}/?token=<access>` | any workspace member | `list.updated` and hierarchy-level changes for the sidebar |

- **Auth is the JWT access token as the `token` query parameter** (browsers cannot set WS headers) — exactly what `apps/realtime/middleware.py` (`JWTAuthMiddleware`) implements. No cookie auth.
- Invalid/expired token, or no read permission on the target: the server sends one `error` frame (or nothing for bad tokens) and closes the socket. No `connection.ack` is ever sent on a rejected socket.
- On success the first server frame is `connection.ack`. Group names server-side: `list.<list_id>`, `workspace.<workspace_id>`, `user.<user_id>`.
- Reconnect: exponential backoff 1s → 30s with jitter; on `connection.ack` the client **refetches** the affected queries. There is no server-side replay/backfill — refetch is authoritative.

### 15.2 Frame format

Every server→client message:

```json
{
  "type": "task.moved",
  "payload": {
    "event_id": "evt_01J4X6…",
    "ts": "2026-08-07T09:15:00.120Z",
    "list_id": "…",
    "workspace_id": "…",
    "actor": { "id": "…user uuid…", "client_id": "…value of X-Client-Id or null…" },
    "data": { …full resource object, identical to the REST serializer output… },
    "rebalanced": false
  }
}
```

- `payload.data` is always shape-identical to the corresponding REST `GET` (events are emitted from the service/serializer layer, never from views).
- `event_id` is unique per event; clients apply events idempotently (same `event_id` twice = no-op).
- Echo suppression: drop any frame where `payload.actor.client_id` equals this tab's own client id.
- `rebalanced` appears only on `task.moved`; `true` means "positions in this `(list_id, status_id)` scope were renumbered — refetch, don't patch."
- For `*.deleted` events, `data` is `{"id": "…", "list_id": "…"}` (task) / `{"id": "…", "task_id": "…"}` (comment).

### 15.3 Event types (closed set, v1.0.0)

| `type` | Channel | `data` |
|---|---|---|
| `connection.ack` | both | `{"channel", "user_id"}` |
| `task.created` | list | Task |
| `task.updated` | list | Task (also emitted per task re-pointed by a status-set replacement, and on soft-delete restore) |
| `task.moved` | list | Task (+ `rebalanced` flag in payload) |
| `task.deleted` | list | `{"id", "list_id"}` |
| `comment.created` | list | Comment |
| `comment.updated` | list | Comment |
| `comment.deleted` | list | `{"id", "task_id"}` |
| `list.updated` | workspace | List (rename/recolor/archive/move/counts changed) |
| `presence.join` / `presence.leave` | list | `{"user": UserSummary}` |
| `presence.sync` | list | `{"users": [UserSummary]}` (sent to a client right after its own ack) |
| `error` | both | `{"code", "message"}` (mirrors §1.6 codes, e.g. `permission_denied`), then the socket closes |

Client→server messages (closed set): `{"type": "presence.ping"}`, `{"type": "presence.typing"}`. Presence liveness is ping-driven; a client that misses its ping window gets a `presence.leave` broadcast on its behalf. Anything else from the client is ignored.

A mutation that fails validation/permission emits **no** event. Every successful mutation emits exactly one event (except status-set replacement: one `task.updated` per re-pointed task).

---

## 16. Endpoint inventory (64)

| Group | Count | Endpoints |
|---|---|---|
| Auth | 5 | register, login, refresh, logout, password/change |
| Profile | 3 | me GET/PATCH, me/avatar POST |
| Workspaces | 6 | list, create, retrieve, update, delete, tree |
| Members | 4 | list, role PATCH, remove, leave |
| Invitations | 7 | list, create, revoke, resend, lookup, accept, decline |
| Spaces | 5 | list, create, retrieve, update, delete |
| Folders | 5 | list, create, retrieve, update, delete |
| Lists | 6 | list, create, retrieve, update, delete, move |
| Status sets | 5 | space GET/PUT, list GET/PUT/DELETE |
| Tasks | 8 | list, create, retrieve, update, delete, move, watch POST/DELETE |
| Tags | 4 | list, create, update, delete |
| Comments | 4 | list, create, update, delete |
| Search | 2 | workspace tasks, workspace search |
| Misc | 1 | health |

WebSocket: `/ws/list/{list_id}/`, `/ws/workspaces/{workspace_id}/`.

---

## 17. Rulings where upstream documents conflicted

| # | Conflict | Ruling in this contract |
|---|---|---|
| R1 | DATA_MODEL puts Space/Folder/TaskList/StatusSet/Status in an `apps.spaces` app (+ `apps.core`); CLAUDE.md puts them in `apps.workspaces` | **CLAUDE.md wins** — all hierarchy models live in `apps.workspaces`. No API-visible impact. |
| R2 | PRD pagination envelope (`page`, `page_size`, `total_pages`) vs implemented `config/pagination.py` | **Implementation wins**: `{"count","next","previous","results"}` (§1.5). |
| R3 | PRD error envelope includes `request_id`; `config/exceptions.py` emits `{code,message,details}` | **Implementation wins**; `request_id` reserved as an optional future field (§1.6). |
| R4 | PRD JWT lifetimes 30 min / 14 days vs settings.py env defaults 60 min / 7 days | Lifetimes are env-configured; contract binds behavior (rotation + blacklist), not TTLs. Clients read `exp`. |
| R5 | PRD WS channels `ws/list/` + `ws/space/`; realtime middleware & UI_SPEC use `ws/list/…?token=` | `ws/list/{list_id}/` kept (matches implemented middleware); the space channel is **replaced** by `ws/workspaces/{workspace_id}/` so one socket serves the whole sidebar. |
| R6 | PRD closes the WS vocabulary without `comment.updated`, `comment.deleted`, `list.updated` (D-9) | **Extended** (required for this contract): those three events are in the v1.0.0 vocabulary (§15.3). PRD D-9/OQ-5 are resolved accordingly. |
| R7 | PRD frame `{type,event_id,ts,list_id,actor,data}` vs required `{type,payload}` | Frames are `{"type", "payload"}`; `event_id`/`ts`/`actor`/`data` live inside `payload` (§15.2). |
| R8 | PRD F1 register asserts a workspace is always bootstrapped; UI_SPEC treats `workspace_name` as optional with a no-workspace state | Register bootstraps a workspace **only when `workspace_name` is supplied**; `POST workspaces/` runs the same bootstrap otherwise. |
| R9 | PRD task payload is ids-only (`assignee_ids`, `created_by_id`, `deleted_at`); DATA_MODEL specifies embedded objects and derived `is_deleted` | **DATA_MODEL wins**: reads embed `assignees`/`watchers`/`tags`/`created_by`/`updated_by`; writes use `assignee_ids`/`tag_ids`; `is_deleted` is serialized, `deleted_at` is not (§10.1). |
| R10 | PRD says comments are flat; DATA_MODEL defines `parent` replies (depth 1) with `reply_count` | **DATA_MODEL wins**: `parent_id` (one level) and `reply_count` are in the contract (§12). |
| R11 | PRD allows `start_date > due_date` (UI warning only); DATA_MODEL has a DB check constraint | **DATA_MODEL wins**: `400 validation_error`. |
| R12 | PRD invitation expiry 14 days; DATA_MODEL 7 days | **DATA_MODEL wins**: 7 days (`INVITATION_TTL_DAYS`, env-configurable). |
| R13 | Invitation "decline" required by this contract; PRD has no decline and the model has no `declined` status | `POST invitations/decline/` added; it marks the invitation `revoked`. |
| R14 | PRD register example returns user `name`; the User model field is `full_name` | `full_name` everywhere. |
| R15 | `token_not_valid` (PRD) vs the current handler mapping all 401s to `authentication_failed` | Both codes are in the vocabulary; the exception handler must map simplejwt `InvalidToken`/`TokenError` to `token_not_valid` (small backend amendment) so clients can trigger silent refresh. |
| R16 | `my_role` on Workspace is not in DATA_MODEL | Added as a serializer-derived read-only field — the frontend needs the caller's role to gate UI and guests cannot read the roster. Not a column. |
| R17 | Subtasks | Out of scope (no `Task.parent` in DATA_MODEL); no subtask endpoints exist. |

*End of contract — version 1.0.0, 2026-08-07.*
