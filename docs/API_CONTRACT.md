# API Contract — Clickish (ClickUp clone) MVP

| | |
|---|---|
| **Document** | API_CONTRACT.md |
| **Version** | 1.3.4 |
| **Date** | 2026-08-10 |
| **Status** | **Binding** — backend and frontend implement against this document in parallel. Changes require a PR that updates this file in the same commit. |
| **Authority** | This doc > PRD.md for API surface. `docs/DATA_MODEL.md` is authoritative for field names/types; this doc mirrors it field-for-field. |
| **Upstream** | `docs/DATA_MODEL.md`, `docs/PRD.md`, `docs/DESIGN_PERMISSIONS.md`, `backend/config/{settings,pagination,exceptions}.py`, `backend/apps/realtime/middleware.py` |

**Inventory: 84 REST endpoints + 2 WebSocket channels** (§16 — the authoritative count). Adding an endpoint requires amending this doc in the same commit.

> **v1.1.0 changelog.** Adds §18 (granular permission matrix, `docs/DESIGN_PERMISSIONS.md` §A–D.5) and rulings R18–R23. The role table in §1.7 now describes the **default** matrix, not a hard-coded one. The extended `invitations/lookup/` payload (§D.7) is specified there but **not yet implemented**; it will land with its own contract bump. (Space-member endpoints landed in v1.3.0 — see §6.1.)
>
> **v1.1.1 changelog (§2 only).** Register-with-invite (`DESIGN_PERMISSIONS.md` §D.8) is now **implemented**: `auth/register/` accepts `invite_token` and may answer with `workspace_id` (R21). The `User`/`UserSummary` objects gain `profession` — a **profile label, never a permission**. New dev-only endpoint `POST auth/demo/` (endpoint #70).

> **v1.3.4 changelog (realtime scoping, broadcast privacy, and a doc-integrity fix — §1.7, §15, §16, §17).** No new endpoints and no new error codes; two **observable client behaviour changes** and one correction of this document against the code.
>
> **(a) WebSocket frames are now space-scoped.** A frame is serialised once and fanned out to a whole group, so the group *is* the authorisation boundary. `workspace.<id>` used to carry `task.*` and `list.updated` and every member joins it — including a guest who gets `404` for the very same list over REST, so private-space titles and task content leaked over the socket. A third group, **`space.<space_id>`**, is introduced (`apps/realtime/events.py`). `task.*` now goes to `list.<id>` **and** `space.<id>`; `list.updated` goes to `space.<id>` **only**; `workspace.<id>` keeps only `permission.updated`, which carries no space content. `WorkspaceConsumer` joins exactly the `space.<id>` groups that `apps.core.access.visible_spaces_q()` returns for that membership — the same predicate REST uses — and re-evaluates that set on every `permission.updated` / `access.revoked` (`BaseConsumer.resync_scope`). **Client impact:** a workspace socket no longer receives `task.*`/`list.updated` for spaces the caller cannot read, and a caller who loses a space stops receiving its frames without the socket closing. Clients that assumed "workspace socket sees everything" must refetch on `permission.updated`.
>
> **(b) Every embedded `email` in a broadcast is `null`.** `UserSummary.email` is per-caller masked over REST (v1.3.2), but a broadcast has no caller — one payload reaches recipients with different authority, so per-recipient masking is impossible. `events._payload()` therefore runs a recursive `_mask()` over `data` and nulls `email` in **every** embedded `UserSummary` of **every** frame (assignees, watchers, `created_by`/`updated_by`, comment authors, attachment uploaders). The key stays, the value is `null` — exactly the shape a guest already sees over REST. **Clients must read emails from `workspaces/{id}/members/`, never from a socket frame.**
>
> **(c) Document integrity.** The per-endpoint **"Roles" columns were describing the pre-v1.3.1 policy**: v1.3.1 narrowed `member` to 14 codes and v1.3.2 opened `member.read` to guests, but **both changelogs amended §1.7 and nothing else**, leaving twelve endpoint rows contradicting the code they bind. Those columns now name the **permission code the view actually resolves** (verified against the `perm=`/`require_*_perm` argument at each view) instead of a hand-maintained role name, and the role→code defaults live in exactly one **generated** block (§1.7.1). The inventory is corrected **83 → 84**: `POST realtime/ticket/` was specified in §15.1 prose but appeared in no table (it is **#84**), and the five §18 permission endpoints (**#65–69**) plus `health/` (**#78**) were unnumbered, which is what produced the 83/84 disagreement between the header and the §16 heading. New rulings **R25–R32** (§17).
>
> **v1.3.3 changelog (AppSec hardening — §1.7, §6, §10.2, §18).** No new endpoints and no new error codes. Three authority holes are closed. **(a)** New permission code **`space.change_visibility`** (catalog v5, 48 → 49 codes; `admin` default, `sensitive`): `PATCH spaces/{id}/` now needs it *in addition to* `space.update` when `is_private` actually changes, so a **space manager can no longer open a private space to the whole workspace** (or close an open one). **(b)** `assignee_ids` is now genuinely governed by `task.assign`: `POST lists/{id}/tasks/` and `PATCH tasks/{id}/` require it whenever the assignee set changes for anyone other than the caller (self-assign and self-unassign stay open), and the AD-7 auto-`SpaceMember` grant only happens when the caller also holds `space.manage_members` — otherwise `400 validation_error` on `assignee_ids`. **(c)** Removing a member (`DELETE members/{user_id}/`) and leaving (`POST members/leave/`) now emit `access.revoked` on the private `user.<id>` channel with `space_id: null`, which closes both the list and the workspace socket with `4403` (§15.3). A missing `RolePermission` row falls back to the catalog default, so **no data migration is needed** for the new code.
>
> **v1.3.2 changelog (team visibility + email privacy).** `member.read` is now a `guest` default: the member roster (§4) and the member profile (§4.1) are open to **every** role. To keep that from turning into a company-wide email harvest, the `UserSummary` object now returns **`email: null` to a `guest` for every user other than themselves** — everywhere it appears (roster, assignees, watchers, `created_by`/`updated_by`, comment authors, attachment uploaders, activity actors). `full_name`, `avatar`, `avatar_color` and `profession` are unaffected, and non-guest callers see emails exactly as before. `/me/` is never masked. No endpoint, status code or field-name changes — only the value of `UserSummary.email`.
>
> **v1.3.1 changelog (default permission matrix — §1.7 only).** No endpoint, payload or error code changes. The **default** role matrix (`DEFAULT_MATRIX`, catalog v3) narrows `member` to "read + work on what is assigned to me": `task.update`, `task.delete`, `task.move`, `task.assign`, `folder.create/update/delete`, `list.create/update/delete/move`, `tag.update` and `tag.delete` are no longer member defaults. `owner`, `admin` and `guest` are unchanged. Per-workspace `RolePermission` overrides (§18) can restore any of them, and a **space manager** (`SpaceAccess.manager`, §6.1) still gets them back inside their own space. See `DESIGN_PERMISSIONS.md` §A.
>
> **v1.3.0 changelog (space members / PM assignment).** Adds §6.1 — the five space-member endpoints of `DESIGN_PERMISSIONS.md` §D.6 (#79–#83), previously specified but unimplemented. `SpaceMember` rows now also gate nothing new on their own: visibility still follows R20's staged rule. Assigning a task auto-creates a `SpaceMember(access=viewer, source=auto_assignee)` row **only for a user who cannot already see the space** (AD-7, see §6.1). Inventory 78 → **83**.
>
> **v1.2.0 changelog (member profile & activity feed).** Adds §4.1 `GET workspaces/{id}/members/{user_id}/profile/` (endpoint #75) and §10.8 `GET workspaces/{id}/activity/` (endpoint #77), and **documents §10.6 `GET tasks/{id}/activity/`** (endpoint #76), which shipped in the code but was missing from this file. The §4 Member object now shows `profession` explicitly (it always travelled inside `UserSummary`). The inventory is corrected to **78** — the previous header said 70 while the §16 table summed to 75.

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
- Unauthenticated requests to any endpoint except `auth/register/`, `auth/login/`, `auth/refresh/`, `invitations/lookup/`, `health/`, `public/showcase/` (§14.1) return `401`.

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

Per-workspace role on `WorkspaceMember.role`: **`owner` > `admin` > `member` > `guest`**. "admin+" below means owner or admin; "member+" means owner/admin/member.

> **R18 (v1.1.0):** the table below is the **default** permission matrix, not a fixed one. Effective authority is `DEFAULT_MATRIX` (catalog in `backend/apps/core/permissions.py`) overlaid with the workspace's `RolePermission` rows — see §18. `owner` is always the full set and can never be edited. The matrix is monotonic: `guest ⊆ member ⊆ admin ⊆ owner`.

> **Default matrix (v1.3.1, BINDING).** The defaults are now:
>
> | Role | Default authority |
> |---|---|
> | `owner` | the full catalog, locked — 49 codes |
> | `admin` | everything except the 4 owner-locked codes — 45 codes |
> | `member` | **read + own work** — 14 codes: `workspace.read`, `member.read`, `space.read`, `task.read`, `task.create`, `task.update_assigned`, `task.watch`, `comment.create`, `comment.update_own`, `comment.delete_own`, `attachment.read`, `attachment.create`, `attachment.delete_own`, `tag.create` |
> | `guest` | read + comment + watch + edit tasks assigned to them + **read the member roster** — 10 codes (v1.3.2) |
>
> A `member` therefore **cannot** edit, move or delete a task that is not assigned
> to them, cannot create or edit spaces/folders/lists, and cannot edit or delete
> tags. They **can** create a task, edit a task assigned to them
> (`task.update_assigned`), comment, and upload/delete their own attachments.
>
> **"Project manager" is not a workspace role.** It is `SpaceAccess.manager` on a
> `SpaceMember` row (§6.1): inside that one space the caller gets
> `space.update`, `space.manage_members/statuses`, the whole `folder.*` and
> `list.*` groups and `task.update/delete/move/assign/restore` back. It never
> grants `space.delete`, **`space.change_visibility`**, `member.*`,
> `workspace.*` or `tag.*` — a PM rules *inside* their space but cannot move
> its boundary relative to the workspace.

### 1.7.1 Default matrix, per code — GENERATED

> **Do not hand-edit the block below, and do not restate role defaults anywhere else in this file.**
> Every "Roles" column in §2–§13 names the **permission code the view resolves**, not a role,
> precisely so that a matrix change cannot silently falsify thirty endpoint rows again
> (it did: see the v1.3.4 changelog note (c)). The role↔code mapping exists here and nowhere else.

Regenerate from the repo root and replace everything between the two markers:

```bash
.venv/Scripts/python.exe - <<'PY'
import importlib.util, sys
sys.stdout.reconfigure(encoding="utf-8")  # the table uses ✓; Windows consoles default to cp1251
spec = importlib.util.spec_from_file_location("perms", "backend/apps/core/permissions.py")
m = importlib.util.module_from_spec(spec); sys.modules["perms"] = m; spec.loader.exec_module(m)
tick = lambda ok: "✓" if ok else ""
print(f"`catalog_version = {m.CATALOG_VERSION}` — {len(m.ALL_CODES)} codes in {len(m.PERMISSION_GROUPS)} groups.")
print(f"Default totals: owner {len(m.ALL_CODES)} (locked), "
      + ", ".join(f"{r} {len(m.DEFAULT_MATRIX[r])}" for r in m.ASSIGNABLE_ROLES) + ".")
print()
print("| Code | Group | admin | member | guest | Flags |")
print("|---|---|---|---|---|---|")
for p in m.PERMISSIONS:
    if p.deprecated:
        continue
    flags = " ".join(f for f, on in (("owner-only", p.owner_only), ("sensitive", p.sensitive)) if on) or "—"
    print(f"| `{p.code}` | {p.group} | {tick('admin' in p.defaults)} | {tick('member' in p.defaults)} "
          f"| {tick('guest' in p.defaults)} | {flags} |")
PY
```

`owner` has no column: it is never stored and never editable (AD-3 — `has_perm()` short-circuits before
the table is read), so it holds every non-deprecated code by definition.

<!-- BEGIN GENERATED: default-permission-matrix -->
<!-- source: backend/apps/core/permissions.py — PERMISSIONS / DEFAULT_MATRIX / CATALOG_VERSION -->

`catalog_version = 5` — 49 codes in 9 groups.
Default totals: owner 49 (locked), admin 45, member 14, guest 10.

| Code | Group | admin | member | guest | Flags |
|---|---|---|---|---|---|
| `workspace.read` | workspace | ✓ | ✓ | ✓ | — |
| `workspace.update` | workspace |  |  |  | — |
| `workspace.delete` | workspace |  |  |  | sensitive |
| `workspace.manage_permissions` | workspace |  |  |  | owner-only sensitive |
| `workspace.transfer_ownership` | workspace |  |  |  | owner-only sensitive |
| `member.read` | member | ✓ | ✓ | ✓ | — |
| `member.invite` | member | ✓ |  |  | — |
| `member.remove` | member | ✓ |  |  | sensitive |
| `member.role_change` | member | ✓ |  |  | sensitive |
| `invitation.read` | member | ✓ |  |  | — |
| `invitation.manage` | member | ✓ |  |  | — |
| `space.read` | space | ✓ | ✓ | ✓ | — |
| `space.read_private` | space | ✓ |  |  | sensitive |
| `space.create` | space | ✓ |  |  | — |
| `space.update` | space | ✓ |  |  | — |
| `space.change_visibility` | space | ✓ |  |  | sensitive |
| `space.delete` | space | ✓ |  |  | sensitive |
| `space.manage_members` | space | ✓ |  |  | — |
| `space.manage_statuses` | space | ✓ |  |  | — |
| `folder.create` | folder | ✓ |  |  | — |
| `folder.update` | folder | ✓ |  |  | — |
| `folder.delete` | folder | ✓ |  |  | — |
| `folder.delete_cascade` | folder | ✓ |  |  | sensitive |
| `list.create` | list | ✓ |  |  | — |
| `list.update` | list | ✓ |  |  | — |
| `list.delete` | list | ✓ |  |  | sensitive |
| `list.move` | list | ✓ |  |  | — |
| `list.manage_statuses` | list | ✓ |  |  | — |
| `task.read` | task | ✓ | ✓ | ✓ | — |
| `task.create` | task | ✓ | ✓ |  | — |
| `task.update` | task | ✓ |  |  | — |
| `task.update_assigned` | task | ✓ | ✓ | ✓ | — |
| `task.delete` | task | ✓ |  |  | — |
| `task.move` | task | ✓ |  |  | — |
| `task.assign` | task | ✓ |  |  | — |
| `task.watch` | task | ✓ | ✓ | ✓ | — |
| `task.restore` | task | ✓ |  |  | — |
| `task.view_deleted` | task | ✓ |  |  | — |
| `comment.create` | comment | ✓ | ✓ | ✓ | — |
| `comment.update_own` | comment | ✓ | ✓ | ✓ | — |
| `comment.delete_own` | comment | ✓ | ✓ | ✓ | — |
| `comment.delete_any` | comment | ✓ |  |  | sensitive |
| `attachment.read` | attachment | ✓ | ✓ | ✓ | — |
| `attachment.create` | attachment | ✓ | ✓ |  | — |
| `attachment.delete_own` | attachment | ✓ | ✓ |  | — |
| `attachment.delete_any` | attachment | ✓ |  |  | sensitive |
| `tag.create` | tag | ✓ | ✓ |  | — |
| `tag.update` | tag | ✓ |  |  | — |
| `tag.delete` | tag | ✓ |  |  | — |

<!-- END GENERATED: default-permission-matrix -->

> **Enforcement (v1.1.0).** Views no longer test the role rank; every guarded endpoint resolves a **permission code** through `require_perm` / `require_membership_perm` / `require_space_perm` (`backend/apps/core/access.py`). Changing the matrix therefore changes REST behaviour immediately (`DESIGN_PERMISSIONS.md` §B.7, cache invalidated by `permissions_version`). The role names below are shorthand for "roles holding that code by default".

| Endpoint group | Code(s) enforced |
|---|---|
| `GET workspaces/{id}/`, `…/tree/`, `…/search/` | `workspace.read` |
| `GET lists/{id}/tasks/`, `tasks/{id}/`, `tasks/{id}/activity/`, `workspaces/{id}/tasks/`, `workspaces/{id}/activity/` | `task.read` |
| `PATCH/DELETE workspaces/{id}/` | `workspace.update` / `workspace.delete` |
| `GET workspaces/{id}/members/`, `…/{user_id}/profile/` | `member.read` |
| `PATCH/DELETE members/{user_id}/` | `member.role_change` / `member.remove` |
| `GET/POST workspaces/{id}/invitations/` | `invitation.read` / `member.invite` |
| `DELETE invitations/{id}/`, `…/resend/` | `invitation.manage` |
| `POST spaces/`, `PATCH/DELETE spaces/{id}/` | `space.create` / `space.update` / `space.delete` |
| `PATCH spaces/{id}/` with a **changed** `is_private` | `space.update` **and** `space.change_visibility` |
| `PUT spaces/{id}/status-set/` | `space.manage_statuses` |
| `POST/PATCH folders/` | `folder.create` / `folder.update` |
| `DELETE folders/{id}/?strategy=` | `cascade` → `folder.delete_cascade`; `detach` → `folder.delete` |
| `POST/PATCH/DELETE lists/`, `lists/{id}/move/` | `list.create` / `list.update` / `list.delete` / `list.move` |
| `PUT/DELETE lists/{id}/status-set/` | `list.manage_statuses` |
| `POST lists/{id}/tasks/` | `task.create`; **plus `task.assign` when `assignee_ids` names anyone other than the caller** |
| `PATCH tasks/{id}/` | `task.update`, else `task.update_assigned` **and** caller is an assignee; **plus `task.assign` when the `assignee_ids` set changes for anyone other than the caller** |
| `PATCH tasks/{id}/move/` | `task.move`, else `task.update_assigned` **and** caller is an assignee |
| `DELETE tasks/{id}/`, `PATCH {"deleted_at": null}` | `task.delete` / `task.restore` |
| `?include_deleted=true` | `task.view_deleted` |
| `POST tasks/{id}/comments/` | `comment.create` |
| `PATCH comments/{id}/` | `comment.update_own` **and** caller is the author |
| `DELETE comments/{id}/` | author → `comment.delete_own`; otherwise `comment.delete_any` |
| `POST/PATCH/DELETE tags/` | `tag.create` / `tag.update` / `tag.delete` |
| `GET/POST spaces/{id}/members/…` | read: none; every write: `space.manage_members` |
| `POST/GET/DELETE attachments…` | `attachment.create` / `attachment.read` / `attachment.delete_own` \| `attachment.delete_any` |

> **Which reads are code-gated, and which are not (v1.3.4, re-verified against the views).**
> Three of the four read codes are now real endpoint gates: **`workspace.read`** (`GET workspaces/{id}/`,
> `…/tree/`, `…/search/`), **`task.read`** (`GET tasks/{id}/`, `lists/{id}/tasks/`, `tasks/{id}/activity/`,
> `workspaces/{id}/tasks/`, `workspaces/{id}/activity/`) and **`member.read`** (the roster and the
> member profile). Revoking any of those three in §18.3 genuinely returns `403`.
>
> **`space.read` is the exception: it is not an endpoint gate.** No view resolves it. It is an *input
> to visibility* — `visible_spaces_q()` and `space_is_visible()` consult it to decide which spaces a
> caller may see, and `SPACE_VIEWER_GRANTS` includes it. Revoking `space.read` therefore does not
> produce `403` on `GET spaces/{id}/`; it makes non-private spaces **invisible**, which surfaces as
> `404` and as absences from every collection. That is a stronger effect than a `403`, not a weaker
> one, but it is a different one — do not test for the wrong status code.
>
> A handful of reads still resolve no code at all and are gated only by membership plus space
> visibility: `GET spaces/{id}/`, `GET workspaces/{id}/spaces/`, the folder and list reads,
> both `status-set` reads, `GET tasks/{id}/comments/`, `GET spaces/{id}/members/`,
> `GET workspaces/{id}/tags/`, `POST members/leave/` and `GET my-permissions/`. Rows marked
> "membership only — **no code**" in §2–§13 are exactly these. The rule they follow is
> "if you can see the container, you can read this about it" — deliberate for `my-permissions/` and
> `leave/` (a member must always be able to discover their own authority and to leave), and simply
> not yet split out for the rest.

Special cases (these **outrank** the matrix — granting a code cannot unlock them):
- `member` (default) may **PATCH/move only tasks where they are in the assignees** — the same resolution order as `guest`, because `task.update`/`task.move` are no longer member defaults (v1.3.1).
- `guest` may **PATCH/move only tasks where they are in the assignees** ("Assignee" below), may create comments, may watch/unwatch, everything else read-only. Guests **can** read the member roster and member profiles (v1.3.2, `member.read`) but every `UserSummary` they receive has `email: null` except their own; they still cannot read invitations, and cannot see private spaces (`is_private=true`).
- Everyone edits/deletes **their own** comments; admin+ may delete (not edit) any comment. There is deliberately **no `comment.update_any` code** — not even the owner can edit someone else's comment (§12).
- The **last owner** cannot be demoted, removed, or leave → `409 conflict`, regardless of who holds `member.role_change` / `member.remove`.
- A caller who is not an `owner` can neither modify an `owner` member nor grant the `owner` role → `403`, even with `member.role_change`.
- Permission is checked before validation. In-workspace denial → `403`; out-of-workspace → `404`. Strict order: resource missing → `404`; not a member → `404`; space not visible → `404`; missing permission → `403`; invalid payload → `400`.

### 1.8 Common query params on task collections

See §9.5 for the full filter vocabulary. Defaults everywhere: `archived=false`, soft-deleted excluded (`include_deleted=true` requires `task.view_deleted` — admin+ by default — else `403`).

---

## 2. Auth & profile — `apps.accounts`

| # | Method | Path | Auth | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|---|
| 1 | POST | `auth/register/` | public | — | `201` `{access, refresh, user, workspace_id?}` |
| 2 | POST | `auth/login/` | public | — | `200` `{access, refresh, user}` |
| 3 | POST | `auth/refresh/` | public (needs refresh token) | — | `200` `{access, refresh}` |
| 4 | POST | `auth/logout/` | required | any | `204` empty |
| 5 | POST | `auth/password/change/` | required | any | `200` `{access, refresh}` |
| 6 | GET | `me/` | required | any | `200` User |
| 7 | PATCH | `me/` | required | any | `200` User |
| 8 | POST | `me/avatar/` | required | any | `200` User |
| 70 | POST | `auth/demo/` | public | — | `200` `{access, refresh, user, workspace_id?}` |

**Request bodies**

- `register`: `{"email", "password", "full_name"?, "workspace_name"?, "profession"?, "invite_token"?}`. Email stored lowercase; uniqueness is case-insensitive. Password runs Django's default validators (failures land on `details.password`, message text is Uzbek). If `workspace_name` is present the server bootstraps a full workspace in the same transaction (workspace + owner membership + "Team Space" + default status set `TO DO/IN PROGRESS/COMPLETE` + "Getting Started" list + 3 sample tasks — DATA_MODEL §11). If absent, no workspace is created. `workspace_id` is returned **only** when a workspace was actually created or joined (R21); the key is absent otherwise.

**`register` with `invite_token` (DESIGN_PERMISSIONS §D.8, implemented):**

| Rule | Behaviour |
|---|---|
| `invite_token` + `workspace_name` together | `400 validation_error`, `details.workspace_name` |
| Unknown or expired token | `404 not_found` (never `403` — existence is not disclosed) |
| Token already `accepted`/`revoked` | `409 conflict` (same semantics as `invitations/accept/`) |
| `email` ≠ invitation email (case-insensitive) | `400 validation_error`, `details.email` |
| `full_name` shorter than 2 chars | `400 validation_error`, `details.full_name` |
| Success | one transaction: User → invitation `accepted` → `WorkspaceMember(role=invitation.role, invited_by=…)` → `refresh_member_count()`; response carries `workspace_id` |

The new member's role comes **only** from `Invitation.role`. A client-supplied `role` field is ignored and never read. The client's `email` is used solely to prove it matches the invitation; the account is created for `Invitation.email`. Concurrency is guarded by `SELECT … FOR UPDATE` plus a status-conditional `UPDATE … WHERE status='pending'` (SQLite makes the former a no-op), so a second racing request gets `409` and no second membership.

- `auth/demo/`: no body. Returns a token pair for `DEMO_USER_EMAIL` so the UI can offer a "Demo rejimda kirish" button without shipping a password to the client. Returns `404 not_found` when `DEMO_MODE` is off, when the account is missing/inactive, or when the account is `is_staff`/`is_superuser` (escalation guard). Throttled by the `demo` scope (default 10/hour per IP). **Off by default; local development only.**
- `login`: `{"email", "password"}`. Failure → `401 authentication_failed`. Updates `last_login`.
- `refresh`: `{"refresh"}`. Rotates; old token blacklisted.
- `logout`: `{"refresh"}` — blacklists that refresh token only (other devices unaffected).
- `password/change`: `{"current_password", "new_password"}`. Wrong current password → `400 validation_error` on `current_password`. On success all the user's other refresh tokens are blacklisted and a fresh pair is returned.
- `PATCH me/`: any of `{"full_name", "timezone", "avatar_color", "profession"}`. `timezone` must be a valid IANA name (validated against `zoneinfo.available_timezones()`), else `400 validation_error`. Email change is out of MVP scope.
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
  "profession": "project_manager",
  "timezone": "Europe/Berlin",
  "date_joined": "2026-08-07T09:00:00Z",
  "last_seen_at": "2026-08-07T09:15:00Z",
  "created_at": "2026-08-07T09:00:00Z",
  "updated_at": "2026-08-07T09:15:00Z"
}
```

**UserSummary** (embedded everywhere a user appears inside another resource): `{"id", "email", "full_name", "avatar", "avatar_color", "profession"}`.

> **`email` is role-dependent (v1.3.2, BINDING).** When the caller's role in the workspace being served is `guest`, `email` is **`null`** for every user except the caller themselves. Every other role sees the real address. This holds wherever `UserSummary` is embedded — roster, assignees, watchers, `created_by`/`updated_by`, comment authors, attachment uploaders and activity actors — so clients must treat `email` as nullable and fall back to `full_name`. `GET me/` is never masked.

**`profession`** — closed set: `""` (unset) | `project_manager` | `developer` | `designer` | `qa` | `analyst` | `marketing` | `other`. It is a **profile label only**: it exists so a PM can pick the right people, and it is deliberately independent of `WorkspaceMember.role` and of §18's permission matrix. No permission check reads it; writing it grants and removes nothing. Writable on `register` and `PATCH me/`; read-only inside `UserSummary`.

---

## 3. Workspaces — `apps.workspaces`

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 9 | GET | `workspaces/` | any authenticated (own memberships only) | `200` paginated Workspace[] |
| 10 | POST | `workspaces/` | any authenticated (caller becomes owner) | `201` Workspace |
| 11 | GET | `workspaces/{id}/` | `workspace.read` | `200` Workspace |
| 12 | PATCH | `workspaces/{id}/` | `workspace.update` — no role holds it by default → **owner** | `200` Workspace |
| 13 | DELETE | `workspaces/{id}/` | `workspace.delete` — no role holds it by default → **owner** | `204` empty |
| 14 | GET | `workspaces/{id}/tree/` | `workspace.read`; spaces filtered by `visible_spaces_q` | `200` Tree |

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
  "permissions_version": 1,
  "created_at": "2026-08-07T09:00:05Z",
  "updated_at": "2026-08-07T09:00:05Z"
}
```

`my_role` is derived per caller (read-only) so the frontend can gate affordances without reading the roster. `permissions_version` (v1.1.0, read-only) is the optimistic-concurrency token for §18.3 and the cache key for the permission matrix; it increments on every matrix write.

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

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 15 | GET | `workspaces/{id}/members/` | `member.read` — **every role by default, guests included** (v1.3.2) | `200` paginated Member[] |
| 16 | PATCH | `workspaces/{id}/members/{user_id}/` | `member.role_change` + the owner guards below (they outrank the code) | `200` Member |
| 17 | DELETE | `workspaces/{id}/members/{user_id}/` | `member.remove` + the owner guards below | `204` empty |
| 18 | POST | `workspaces/{id}/members/leave/` | membership only — **no code** (last-owner guard applies) | `204` empty |
| 75 | GET | `workspaces/{id}/members/{user_id}/profile/` | `member.read` (every role by default, v1.3.2) | `200` MemberProfile |

- `{user_id}` in the path is the **user's** id, not the membership row id.
- `PATCH` body: `{"role": "owner"|"admin"|"member"|"guest"}`. Rules: only an owner may grant `owner` or touch an owner; admin may change roles among `admin`/`member`/`guest` for non-owners; member/guest → `403`.
- Last-owner invariants → `409 conflict`: demoting the last owner, removing the last owner, or the last owner calling `leave/`. Ownership transfer = promote someone to `owner`, then demote/leave.
- Removing a member deletes their assignee/watcher rows **and their `SpaceMember` rows** in this workspace, keeps their comments and `created_by`/`updated_by` attributions, and makes all their subsequent requests in this workspace return `404`. It also **closes their live WebSocket subscriptions**: on commit the server emits `access.revoked` with `space_id: null` on the private `user.<id>` channel, which closes both the workspace socket and every list socket of this workspace with `4403` (§15.3). `POST members/leave/` takes exactly the same path (v1.3.3 — before it, a removed member's open socket kept receiving `task.*`/`comment.*`/`attachment.*`/`list.updated` frames indefinitely, because a consumer only checks membership once, at `connect()`).
- Roster ordering: rank `owner, admin, member, guest`, then email.

**Member object:**

```json
{
  "id": "…membership uuid…",
  "user": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null, "avatar_color": "#49CCF9", "profession": "developer" },
  "role": "member",
  "invited_by_id": "…user uuid or null…",
  "joined_at": "2026-08-07T10:00:00Z",
  "last_active_at": "2026-08-07T12:41:00Z",
  "created_at": "2026-08-07T10:00:00Z",
  "updated_at": "2026-08-07T10:00:00Z"
}
```

`user` is the standard `UserSummary` and therefore carries `profession` (v1.1.1) — a **profile label, never a permission**. Clients render it next to the role; authority is decided solely by `role` + the §18 matrix.

### 4.1 Member profile (endpoint 75)

`GET workspaces/{id}/members/{user_id}/profile/` — one request answering "what is this person working on": role, tenure, counters, and a per-space breakdown. Backs the member profile page.

```json
{
  "user": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null,
            "avatar_color": "#7B68EE", "profession": "developer" },
  "role": "member",
  "joined_at": "2026-01-05T09:00:00Z",
  "last_active_at": "2026-08-10T07:00:00Z",
  "stats": {
    "open_tasks": 12, "overdue_tasks": 2, "due_today": 3,
    "completed_tasks": 41, "created_tasks": 30, "comments": 87
  },
  "spaces": [ { "id": "…", "name": "Marketing", "color": "#7B68EE", "open_tasks": 5 } ]
}
```

- **Visibility is the CALLER's, not the target's (BINDING).** `spaces` lists only spaces the caller can see (`visible_spaces_q`, §1.7 / `DESIGN_PERMISSIONS.md` §C.5), and **every counter is computed inside that same set**. A guest who cannot see a private space must not learn it exists from a larger number — a server that counts tasks outside the caller's visibility violates this contract.
- `{user_id}` is the **user's** id. A user who is not a member of this workspace — including a member of another workspace, and including a user who exists but was removed — → `404 not_found`, never `403`. A caller outside the workspace → `404`. A caller inside the workspace without `member.read` → `403 permission_denied`; since v1.3.2 `member.read` is a default for **every** role, so this only happens when a workspace revokes it through §18.
- Counter semantics (mirroring §10.5): "open" = not archived and status type ≠ `closed`; `overdue_tasks` = open **and** `due_date < now`; `due_today` = open **and** due between `now` and the end of the caller's local day — so `overdue_tasks` and `due_today` never overlap. `completed_tasks` counts assigned tasks with `completed_at != null`. `created_tasks` counts tasks the member created; `comments` counts their comments. Soft-deleted tasks are excluded everywhere.
- `spaces[].open_tasks` is the **target member's** open task count in that space, ordered by the space `position`.
- Every aggregate is computed with `annotate`/`aggregate`; the query count does not grow with the number of spaces, members or tasks.

---

## 5. Invitations

| # | Method | Path | Auth | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|---|
| 19 | GET | `workspaces/{id}/invitations/` | required | `invitation.read` | `200` paginated Invitation[] |
| 20 | POST | `workspaces/{id}/invitations/` | required | `member.invite` | `201` Invitation |
| 21 | DELETE | `invitations/{id}/` | required | `invitation.manage` (revoke) | `204` empty |
| 22 | POST | `invitations/{id}/resend/` | required | `invitation.manage` | `200` Invitation |
| 23 | GET | `invitations/lookup/?token=<t>` | **public** | — | `200` lookup object |
| 24 | POST | `invitations/accept/` | required | invited email only | `200` `{workspace_id, member}` |
| 25 | POST | `invitations/decline/` | required | invited email only | `204` empty |

- `POST` body: `{"email", "role": "admin"|"member"|"guest"}` (`owner` is not invitable → `400 validation_error`). A second **pending** invite for the same `(workspace, email)`, or inviting an existing member → `409 conflict`.
- The raw `token` never appears in any API response (it travels only in the invitation email). `lookup/` is the sole token-based read: returns `{"workspace_name", "email", "role", "expires_at"}` and nothing else. Unknown/expired/revoked token → `404 not_found`.
- `accept/` / `decline/` body: `{"token"}`. Caller must be authenticated with the invited email, else `403 permission_denied`. Accept creates the `WorkspaceMember` with the invited role. Replay of a consumed token → `409 conflict`; unknown/expired → `404`. Decline marks the invitation `revoked` (no separate `declined` status exists in the data model).
- Expiry: `created_at + INVITATION_TTL_DAYS` (**7 days**, env-configurable). `resend/` refreshes `expires_at`, throttled to 1/5 min, max `sent_count` 5 (`429 throttled` / `409 conflict` past the cap). Revoking a non-pending invitation → `409 conflict`.
- **Throttling (F-6).** `POST workspaces/{id}/invitations/` runs under the `invite` scope (`INVITE_THROTTLE_RATE`, default 20/hour per user); the public `invitations/lookup/` runs under `invite_lookup` (`INVITE_LOOKUP_THROTTLE_RATE`, default 30/hour per IP) so tokens cannot be brute-forced. Listing invitations is not throttled. Over the limit → `429 throttled`.

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

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 26 | GET | `workspaces/{id}/spaces/` | membership only — **no code**; results filtered by `visible_spaces_q` | `200` paginated Space[] |
| 27 | POST | `workspaces/{id}/spaces/` | `space.create` | `201` Space |
| 28 | GET | `spaces/{id}/` | membership only — **no code**; invisible space → `404` | `200` Space |
| 29 | PATCH | `spaces/{id}/` | `space.update`; a **changed** `is_private` also needs `space.change_visibility` | `200` Space |
| 30 | DELETE | `spaces/{id}/` | `space.delete` | `204` empty |

- `POST` body: `{"id"?, "name", "description"?, "color"?, "icon"?, "is_private"?}`. Creation auto-creates the space's default `StatusSet` (TO DO / IN PROGRESS / COMPLETE). Name is CI-unique per workspace (`409 conflict` on duplicate). Position auto-assigned at end of scope.
- `PATCH`: same fields plus `"archived"`.
  - **`is_private` is gated separately (v1.3.3).** Changing it needs `space.change_visibility` *on top of* `space.update`; a `SpaceAccess.manager` (PM) holds `space.update` locally but **not** `space.change_visibility`, so a PM gets `403 permission_denied` when they try to open or close their space. The check fires **only when the value actually changes** — resending the current value (as a full-object PATCH does) is not a change and is allowed. Ordering follows §1.7: the permission is resolved before payload validation.
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

### 6.1 Space members (PM assignment)

Upstream: `docs/DESIGN_PERMISSIONS.md` §D.6 / §B.4 / §B.5 / F-5. This is how a project manager picks the right people for a project.

| # | Method | Path | Permission | Success |
|---|---|---|---|---|
| 79 | GET | `spaces/{id}/members/` | membership only — **no code** — whoever can see the space sees its team | `200` paginated SpaceMember[] |
| 80 | POST | `spaces/{id}/members/` | `space.manage_members` **or** local `manager` | `201` SpaceMember |
| 81 | PATCH | `spaces/{id}/members/{user_id}/` | same | `200` SpaceMember |
| 82 | DELETE | `spaces/{id}/members/{user_id}/` | same | `204` empty |
| 83 | POST | `spaces/{id}/members/bulk/` | same | `200` BulkSpaceMembersResponse |

Reading the roster needs **no** permission code: anyone who can see the space can see who is on it. Writing needs one of two things — the workspace-level `space.manage_members` code (admin by default), or a local `SpaceMember(access="manager")` row in *this* space. A local `manager` never gains `space.delete`, `member.*`, `workspace.*` or `tag.*` (F-5).

**SpaceMember object:**

```json
{
  "id": "…", "space_id": "…",
  "user": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz",
            "avatar": null, "avatar_color": "#49CCF9", "profession": "developer" },
  "access": "contributor", "source": "manual", "added_by_id": "…",
  "created_at": "2026-08-10T09:20:00Z", "updated_at": "2026-08-10T09:20:00Z"
}
```

- `access` ∈ `viewer` | `contributor` | `manager`. **Lowest privilege wins**: a `viewer` row cuts every write inside the space regardless of the workspace role; `contributor` defers to the workspace role; `manager` adds the fixed local PM grant set (§B.5).
- `source` ∈ `manual` | `auto_creator` | `auto_assignee` | `backfill` — provenance only, never authority.
- Rows are ordered `manager`, `contributor`, `viewer`, then by email.

**POST body:** `{"user_id": "…", "access"?: "viewer"|"contributor"|"manager"}` — `access` defaults to `contributor`.

**PATCH body:** `{"access": "viewer"|"contributor"|"manager"}`.

**Bulk body:** `{"add": [{"user_id", "access"}], "remove": ["…user uuid…"]}`. One transaction, no partial success. `add` is an **upsert** (an existing row has its `access` updated, keeping `source`), which is what the PM panel's single "Saqlash" button needs. A `user_id` in both arrays → `400`. **Bulk response:** `{"added": <int>, "removed": <int>, "results": SpaceMember[]}` where `results` is the space's **full** roster after the transaction, so the client can replace its state in one step.

| HTTP | `code` | When |
|---|---|---|
| 400 | `validation_error` | `user_id` is not a member of this workspace (`details.user_id`), or a bulk payload contradicts itself |
| 403 | `permission_denied` | Neither `space.manage_members` nor a local `manager` row |
| 404 | `not_found` | The space is not visible to the caller, **or** the `user_id` has no `SpaceMember` row (PATCH/DELETE) |
| 409 | `conflict` | Duplicate `(space, user)` on POST |
| 409 | `conflict` | Removing/demoting the last `manager` of a **private** space → `details.reason = "last_manager"` |

The `last_manager` guard applies to private spaces only: an open space stays reachable through the workspace role, whereas a private space with no manager could never have a member added back.

**Lifecycle rules (binding):**

- `create_space()` writes `SpaceMember(access=manager, source=auto_creator)` for the creator (§B.6).
- Removing someone from the workspace (`DELETE workspaces/{id}/members/{user_id}/`, `members/leave/`) deletes their `SpaceMember` rows — a `SpaceMember` never outlives its `WorkspaceMember` (§B.4).
- **AD-7:** assigning a task writes `SpaceMember(access=viewer, source=auto_assignee)` for the assignee **only when that user cannot already see the space**. Writing it unconditionally would be self-defeating: `viewer` is the lowest privilege and wins over the workspace role, so an assignee in an open space would lose the right to edit the very task they were assigned (`task.update_assigned` → `403`). Scoped this way the row only ever *grants* visibility and never removes authority.
- Dropping to `access = "viewer"` or removing a row emits `access.revoked` on the `user.<id>` channel (§18.6).

---

---

## 7. Folders

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 31 | GET | `spaces/{id}/folders/` | membership only — **no code** | `200` paginated Folder[] |
| 32 | POST | `spaces/{id}/folders/` | `folder.create` — **admin by default** (not member) | `201` Folder |
| 33 | GET | `folders/{id}/` | membership only — **no code** | `200` Folder |
| 34 | PATCH | `folders/{id}/` | `folder.update` — **admin by default** | `200` Folder |
| 35 | DELETE | `folders/{id}/?strategy=cascade\|detach` | `cascade` → `folder.delete_cascade`; `detach` → `folder.delete`. **Both are admin by default**; `cascade` is the more dangerous of the two and is the one flagged `sensitive` | `204` empty |

- `POST` body: `{"id"?, "name", "color"?}`. Name CI-unique per space (`409`). Folders are pure grouping nodes: no statuses, no tasks, never nested.
- `DELETE`: `strategy=cascade` (default) deletes the folder and all its lists/tasks; `strategy=detach` moves its lists to the space root (`folder_id = null`, fresh positions at end of the space-root scope) then deletes the folder.

**Folder object:** `{"id", "space_id", "name", "color", "archived", "position", "created_by_id", "created_at", "updated_at"}`.

---

## 8. Lists

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 36 | GET | `spaces/{id}/lists/` | membership only — **no code** | `200` paginated List[] |
| 37 | POST | `spaces/{id}/lists/` | `list.create` — **admin by default** | `201` List |
| 38 | GET | `lists/{id}/` | membership only — **no code** | `200` List |
| 39 | PATCH | `lists/{id}/` | `list.update` — **admin by default** | `200` List |
| 40 | DELETE | `lists/{id}/` | `list.delete` — **admin by default** | `204` empty |
| 41 | PATCH | `lists/{id}/move/` | `list.move` — **admin by default** | `200` List |

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

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 42 | GET | `spaces/{id}/status-set/` | membership only — **no code** | `200` StatusSet |
| 43 | PUT | `spaces/{id}/status-set/` | `space.manage_statuses` | `200` StatusSet |
| 44 | GET | `lists/{id}/status-set/` | membership only — **no code** | `200` StatusSet (the **effective** set — the list's own if it exists, else the space's) |
| 45 | PUT | `lists/{id}/status-set/` | `list.manage_statuses` | `200` StatusSet (creates/replaces the list override) |
| 46 | DELETE | `lists/{id}/status-set/` | `list.manage_statuses` | `200` StatusSet (removes the override; returns the space set now in effect) |

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

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 47 | GET | `lists/{id}/tasks/` | `task.read`; `?include_deleted=true` also needs `task.view_deleted` | `200` paginated Task[] (or grouped, §10.4) |
| 48 | POST | `lists/{id}/tasks/` | `task.create`; an `assignee_ids` naming anyone but the caller also needs `task.assign` (admin by default) | `201` Task |
| 49 | GET | `tasks/{id}/` | `task.read` | `200` Task |
| 50 | PATCH | `tasks/{id}/` | `task.update`, **else** `task.update_assigned` + caller is an assignee; an `assignee_ids` change touching anyone but the caller also needs `task.assign`. `{"deleted_at": null}` is the restore path → `task.restore` | `200` Task |
| 51 | DELETE | `tasks/{id}/` | `task.delete` — **admin by default** (no assignee fallback) | `204` empty (soft delete) |
| 52 | PATCH | `tasks/{id}/move/` | `task.move` (**admin by default**), **else** `task.update_assigned` + caller is an assignee — **checked against the source space and, when the move crosses spaces, against the destination space too**. The destination list must also be readable | `200` Task (+ `rebalanced`) |
| 53 | POST | `tasks/{id}/watch/` | `task.watch` | `201` Task (`200` if already watching — idempotent) |
| 54 | DELETE | `tasks/{id}/watch/` | `task.watch` | `204` empty (idempotent) |
| 76 | GET | `tasks/{id}/activity/` | `task.read` — the same code that gates the task itself, so history is never more visible than the task | `200` paginated TaskActivity[] |
| 77 | GET | `workspaces/{id}/activity/` | `task.read` | `200` paginated WorkspaceActivity[] |
| 71 | GET | `tasks/{id}/attachments/` | `attachment.read` (every role by default) | `200` paginated Attachment[] |
| 72 | POST | `tasks/{id}/attachments/` | `attachment.create` (admin+member by default; guest → `403`) | `201` Attachment |
| 73 | GET | `attachments/{id}/download/` | `attachment.read` | `200` file stream |
| 74 | DELETE | `attachments/{id}/` | uploader → `attachment.delete_own`; anyone else → `attachment.delete_any` (admin by default) | `204` empty (hard delete) |

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
  "attachment_count": 2,
  "assignees": [ { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null, "avatar_color": "#49CCF9" } ],
  "watchers":  [ { "id": "…", "email": "maya@acme.io", "full_name": "Maya Chen", "avatar": null, "avatar_color": "#7B68EE" } ],
  "tags":      [ { "id": "…", "name": "backend", "color": "#FD71AF" } ],
  "created_by": { "id": "…", "email": "maya@acme.io", "full_name": "Maya Chen", "avatar": null, "avatar_color": "#7B68EE" },
  "updated_by": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null, "avatar_color": "#49CCF9" },
  "created_at": "2026-08-07T09:30:00Z",
  "updated_at": "2026-08-07T11:02:00Z"
}
```

Read-only fields: `position`, `comment_count`, `attachment_count` (server-maintained counters — see §12 and §10.7), `completed_at` (set/cleared by the server on transitions into/out of a `closed`-type status), `is_deleted`, `created_by`, `updated_by`, `watchers` (managed only via `watch/`), timestamps. `priority_order` is never serialized — it exists only as the `?ordering=priority_order` sort key.

### 10.2 Create / update

- `POST lists/{id}/tasks/` body: `{"id"?, "title"}` plus optionally `description_html` + `description_json` (both or neither — one without the other → `400 validation_error`), `status_id`, `priority`, `due_date`, `start_date`, `time_estimate_minutes`, `archived`, `assignee_ids`, `tag_ids`.
  - Defaults: `status_id` → the effective set's `is_default` status; `priority` → `"none"`; `position` → end of the `(list_id, status_id)` column; empty arrays elsewhere. Creator is auto-added as a watcher.
- `archived` is a **writable boolean on both `POST` and `PATCH`** (`TaskInputSerializer.archived`); archiving a task is an ordinary update, not a separate endpoint, and it needs the same authority as any other edit (row 50). Collections default to `archived=false`, so archiving removes the task from the default list view without deleting it.
- `PATCH tasks/{id}/` accepts the same writable fields. **Write field names:** `assignee_ids: [uuid]` and `tag_ids: [uuid]` (full-replace arrays); reads return the embedded `assignees`/`tags` arrays. `watcher_ids` is NOT patchable — use `watch/`. `list_id`/`position` are NOT patchable — use `move/`.
- Validation: `title` required, trimmed, non-empty, ≤500 chars. `priority` ∈ `urgent|high|normal|low|none`. `status_id` outside the list's effective set → `400 invalid_status_for_list`. `start_date > due_date` → `400 validation_error` (DB check constraint). Non-member ids in `assignee_ids` → `400 validation_error`; tags from another workspace → `400 validation_error`. `description_json` ≤ 256 KB; HTML sanitized server-side (nh3 allow-list).
- **`assignee_ids` is gated by `task.assign` (v1.3.3).** Required whenever the assignee set changes for **anyone other than the caller** — on `POST` when the list names someone else, on `PATCH` when the symmetric difference against the current set contains anyone but the caller. Two things are deliberately *not* a change: resending the identical set (a full-object PATCH does this), and self-assign / self-unassign ("I'll take it" / "I'm dropping it" must work without an admin). Neither can widen anyone's access — `_grant_assignee_space_access` never writes a `SpaceMember` row for someone who already sees the space, and the caller demonstrably does. Everything else needs the code: `PATCH tasks/{id}/` also passes for a caller holding only `task.update_assigned`, and without this gate that guest-level code would have let an assignee hand out assignments — or silently unassign every colleague.
- **AD-7 auto-access is gated by `space.manage_members` (v1.3.3).** Assigning a user who cannot yet see the task's space normally auto-creates `SpaceMember(access=viewer, source=auto_assignee)` (§6.1). That row is now written **only if the caller also holds `space.manage_members` in that space**; otherwise the whole request fails with `400 validation_error`, `details.assignee_ids = ["Bu foydalanuvchi bo'limni ko'rmaydi; avval uni bo'limga qo'shing."]` and nothing is persisted. Without this, `space.manage_members` (admin-only) was reachable through `task.update_assigned` (guest-level).
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

### 10.6 Task activity (endpoint 76)

`GET tasks/{id}/activity/` — the task's own history, newest first, standard §1.5 envelope. Rows are **immutable**: written from `apps.tasks.services` only, never updated, never deleted except by the task's cascade.

```json
{
  "id": "…", "verb": "status_changed",
  "actor": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null, "avatar_color": "#49CCF9", "profession": "developer" },
  "from_value": "TO DO", "to_value": "IN PROGRESS",
  "metadata": { "from_status_id": "…", "to_status_id": "…" },
  "created_at": "2026-08-07T11:02:00Z"
}
```

**`verb` vocabulary (closed set)** — `apps.core.enums.ActivityVerb`:

| `verb` | `from_value` | `to_value` |
|---|---|---|
| `created` | — | task title |
| `renamed` | old title | new title |
| `status_changed` | old status name | new status name |
| `completed` | — | closing status name |
| `assignee_added` | — | assignee display name |
| `assignee_removed` | assignee display name | — |
| `priority_changed` | old priority value | new priority value |
| `due_date_changed` | old ISO instant or `null` | new ISO instant or `null` |
| `moved` | source list name | destination list name |
| `deleted` | task title | — |
| `restored` | — | task title |
| `attachment_added` | — | attachment `original_name` |
| `attachment_removed` | attachment `original_name` | — |

`actor` is `null` when the acting user was hard-deleted — history outlives the user. Values are plain display strings, not ids; ids that matter live in `metadata`.

The two `attachment_*` rows are written from `apps.tasks.attachments` (the only
exception to "services only" — they use the same `services.activity()` builder)
and carry `metadata = {"attachment_id", "content_type", "size_bytes"}`. The
`attachment_id` may already be gone: an `attachment_removed` row outlives the
file it describes. **Clients must tolerate unknown verbs** — render a generic
sentence instead of failing when the vocabulary grows.

### 10.8 Workspace activity feed (endpoint 77)

`GET workspaces/{id}/activity/` — the same rows across the whole workspace, newest first, standard §1.5 envelope. Backs the member profile "Faoliyat" tab and any workspace-wide feed.

```json
{
  "id": "…", "verb": "status_changed",
  "actor": { "id": "…", "email": "dan@acme.io", "full_name": "Dan Ortiz", "avatar": null, "avatar_color": "#49CCF9", "profession": "developer" },
  "task": { "id": "…", "title": "Q3 hisobot", "list_id": "…", "list_name": "Sprint 12" },
  "from_value": "TO DO", "to_value": "IN PROGRESS",
  "created_at": "2026-08-07T11:02:00Z"
}
```

| Param | Values |
|---|---|
| `actor` | user uuid — only that actor's rows. Not a UUID → `400 validation_error` |
| `verb` | one value from the §10.6 vocabulary. Anything else → `400 validation_error` |

- Different keys AND. Ordering is fixed at `-created_at` (no `ordering` param).
- **Visibility (BINDING).** Only activity on tasks in spaces the caller can see (`visible_spaces_q`). Rows of soft-deleted tasks are excluded too: if `GET tasks/{id}/` would answer `404`, its history must not surface here either.
- `metadata` is deliberately **not** serialized in this payload (it is an internal field); use §10.6 when a client needs it.
- Caller outside the workspace → `404`; inside without `task.read` → `403`.

### 10.7 Attachments (files & documents)

Endpoints 71–74. Files are attached to a task, never to a list or comment.

**Attaching to a completed task is explicitly allowed (BINDING).** Neither
`POST tasks/{id}/attachments/` nor `DELETE attachments/{id}/` looks at
`completed_at` or at `status.type == "closed"` — a task that is already done
still accepts the final report, the signed contract or the invoice. A server
that returns `409`/`403` for a closed task violates this contract.

**Attachment object:**

```json
{
  "id": "…",
  "task_id": "…",
  "original_name": "yakuniy-hisobot.pdf",
  "content_type": "application/pdf",
  "size_bytes": 248117,
  "download_url": "https://api.example.com/api/v1/attachments/…/download/",
  "uploaded_by": { "id": "…", "email": "maya@acme.io", "full_name": "Maya Chen", "avatar": null, "avatar_color": "#7B68EE", "profession": "" },
  "created_at": "2026-08-10T09:30:00Z",
  "updated_at": "2026-08-10T09:30:00Z"
}
```

- The storage path is **never** serialized. `download_url` is the only read
  path and it re-checks `attachment.read`; a direct `MEDIA_URL` link would not.
- `uploaded_by` is `null` for hard-deleted users (render "Deleted user").
- Ordering: `created_at DESC` (newest first), standard pagination envelope.

**Upload** — `POST tasks/{id}/attachments/`, `multipart/form-data`, single
part named `file`. A JSON body → `415 unsupported_media_type`.

| Rule | Value / behaviour |
|---|---|
| Max size | `MAX_ATTACHMENT_MB` (default **10 MB**); over → `400 validation_error`, `details.file` |
| Empty file | `400 validation_error` |
| Extension allow-list | `pdf, doc, docx, xls, xlsx, ppt, pptx, txt, md, csv, png, jpg, jpeg, webp, gif, zip` |
| Rejected outright | `svg`, `html`, `js`, `exe`, `bat`, `sh` and every other executable/active type → `400 validation_error` (an inline SVG is a stored-XSS vector) |
| Declared MIME | must be in the allow-list or neutral (`application/octet-stream`); anything else → `400` |
| Stored `content_type` | derived **server-side from the extension** — the client's value is never trusted |
| Stored filename | generated server-side as `<uuid4>.<ext>`; the client's name is sanitized and kept only in `original_name` (path traversal and double extensions cannot reach storage) |
| **File signature** | the first bytes must match the declared extension → otherwise `400 validation_error`. `png`/`jpg`/`jpeg`/`webp`/`gif` are checked strictly, `pdf` must start with `%PDF-`, `zip`/`docx`/`xlsx`/`pptx` must start with `PK\x03\x04`, `doc`/`xls`/`ppt` must be OLE2 (or RTF for `doc`) |
| **Text types** | `txt`/`md`/`csv` have no signature: the first 8 KB must decode as UTF-8 and contain no null byte → otherwise `400` |
| **Archive contents** | for every zip-family upload the central directory is inspected without extracting: an entry with a `..` segment or an absolute path (zip-slip) → `400`; total uncompressed / compressed ratio above **100** or more than 5000 entries (decompression bomb) → `400` |
| Throttle | `attachment` scope, `ATTACHMENT_THROTTLE_RATE` (default `30/hour`) → `429 throttled` |

**Download** — `GET attachments/{id}/download/` streams the bytes with:

- `Content-Disposition: attachment; filename="<ascii>"; filename*=UTF-8''<pct-encoded>` (RFC 6266 + RFC 5987) — never `inline`;
- `X-Content-Type-Options: nosniff`;
- `Content-Type` = the stored canonical type;
- `Cache-Control: private, no-store`.

**Delete** — `DELETE attachments/{id}/` is a **hard** delete (row + stored
file). The uploader needs `attachment.delete_own`; deleting somebody else's
file needs `attachment.delete_any` (admin+ by default).

**Tenant isolation:** an attachment or task outside the caller's workspaces —
or inside a private space they cannot see — is always `404 not_found`, never
`403` (§1.7). `attachment_count` on the Task object is maintained by the
server on every upload/delete.

**History:** every successful upload writes an `attachment_added` row and every
successful delete an `attachment_removed` row to the task history (§10.6), so a
file that appeared and vanished is still traceable.

**Orphaned files (operations).** A cascade delete (task → list → space →
workspace) removes `TaskAttachment` rows without touching the bytes on disk;
only `DELETE attachments/{id}/` deletes both. The
`python manage.py prune_attachments` command reconciles
`MEDIA_ROOT/attachments/` against the table. It is **dry-run by default**
(`--delete` to actually unlink) and ignores files younger than
`--older-than-days` (default `7`) so an upload whose transaction has not
committed yet is never removed.

---

## 11. Tags

Workspace-scoped; the same tag may label tasks across spaces.

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 55 | GET | `workspaces/{id}/tags/` | membership only — **no code** | `200` paginated Tag[] |
| 56 | POST | `workspaces/{id}/tags/` | `tag.create` (admin+member by default) | `201` Tag |
| 57 | PATCH | `tags/{id}/` | `tag.update` — **admin by default** | `200` Tag |
| 58 | DELETE | `tags/{id}/` | `tag.delete` — **admin by default** | `204` empty (hard delete; `TaskTag` rows cascade, tasks untouched) |

- Bodies: `{"id"?, "name", "color"?}`. Name CI-unique per workspace → `409 conflict` on duplicate. `usage_count` is read-only (drives "most used" ordering; default collection ordering `name ASC`, `?ordering=-usage_count` supported).

**Tag object:** `{"id", "workspace_id", "name", "color", "usage_count", "created_at", "updated_at"}`.

---

## 12. Comments — `apps.comments`

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 59 | GET | `tasks/{id}/comments/` | membership only — **no code** | `200` paginated Comment[] |
| 60 | POST | `tasks/{id}/comments/` | `comment.create` (every role by default) | `201` Comment |
| 61 | PATCH | `comments/{id}/` | `comment.update_own` **and** caller is the author. The author check runs **first** and outranks the matrix — there is no `comment.update_any` | `200` Comment |
| 62 | DELETE | `comments/{id}/` | author → `comment.delete_own`; anyone else → `comment.delete_any` (admin by default) | `204` empty (soft delete) |

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

| # | Method | Path | Authority — code enforced (§1.7.1) | Success |
|---|---|---|---|---|
| 63 | GET | `workspaces/{id}/tasks/` | `task.read`; rows further restricted to `visible_spaces_q` | `200` paginated Task[] |
| 64 | GET | `workspaces/{id}/search/?q=<text>` | `workspace.read`; rows further restricted to `visible_spaces_q` | `200` paginated mixed results |

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

| # | Method | Path | Auth | Success |
|---|---|---|---|---|
| 78 | GET | `health/` | **public** | `200` `{"status": "ok"}` |

Unauthenticated and unthrottled; it touches no database. It is endpoint **#78** of the 84 in §16.

---

## 14.1 Public landing content

| # | Method | Path | Auth | Success |
|---|---|---|---|---|
| 85 | GET | `public/showcase/` | **public** | `200` (body below) |

The marketing landing at `/` is rendered **only for signed-out visitors** (an
authenticated visitor is redirected to their workspace), so it has no token to
call the rest of the API with. This is the one endpoint that feeds it, and it
exists so the landing renders **database rows instead of hardcoded sample
data**. Throttled per source address (`showcase` scope, default `60/min`);
it is anonymous, uncached and runs several `COUNT(*)` queries.

```jsonc
{
  "stats": {                      // aggregate counts only, never row content
    "permission_codes": 49, "roles": 4, "workspaces": 11,
    "spaces": 12, "tasks": 33, "members": 21
  },
  "matrix": {                     // the catalog's DEFAULT_MATRIX (§1.7.1)
    "roles": ["Egasi", "Admin", "A'zo", "Mehmon"],
    "rows": [{ "code": "task.create", "label": "Vazifa yaratish",
               "allow": [true, true, true, false] }]   // index 0 = owner, always true
  },
  "workspace": null               // see the disclosure rule below
}
```

**Disclosure rule (binding).** `stats` and `matrix` are always returned: the
permission catalog is already public in `docs/DESIGN_PERMISSIONS.md` and the
counts carry no row content. The `workspace` block — space names, task titles,
assignee initials, activity feed, position keys — is returned **only when
`SHOWCASE_WORKSPACE_ID` names a workspace**, and is `null` otherwise. The
setting is empty by default, so the out-of-the-box behaviour is that **no
record of anyone's is readable anonymously**. Within a configured workspace:

- user emails are **never** serialised — initials (`"AK"`) and avatar colour only;
- **private spaces are never named**; they collapse into one `locked` row that
  carries a count and nothing else;
- an unknown or malformed id yields `workspace: null`, not a `500`.

Anything named by `SHOWCASE_WORKSPACE_ID` must be treated as world-readable.

---

## 14.2 Chat — `apps.chat`

| # | Method | Path | Auth | Authority | Success |
|---|---|---|---|---|---|
| 86 | GET | `workspaces/{id}/chat/channels/` | required | membership | `200` `Paginated<Conversation>` |
| 87 | POST | `workspaces/{id}/chat/channels/` | required | membership | `201` `Conversation` |
| 88 | POST | `workspaces/{id}/chat/direct/` | required | membership | `200` `Conversation` |
| 89 | POST | `chat/conversations/{id}/join/` | required | visible + open channel | `204` |
| 90 | GET | `chat/conversations/{id}/messages/` | required | conversation visible | `200` `Paginated<Message>` |
| 91 | POST | `chat/conversations/{id}/messages/` | required | conversation **member** | `201` `Message` |

Channels and direct messages share one `Conversation` row, split by `kind`
(`channel` \| `direct`). `GET .../chat/channels/` returns **both** — it is the
caller's full conversation list, ordered by `last_message_at` descending.

**Visibility.** An open channel (`is_private: false`) is listed for every
workspace member. A private channel and every DM are listed **only for their
own members**; to everyone else they are `404`, never `403` — same
existence-oracle rule as §1.7. `POST .../messages/` additionally requires
membership of the conversation: a member who can *read* an open channel gets
`403` until they `join/`.

**DM identity.** `direct/` is idempotent: the pair `(A, B)` is keyed by an
order-independent `dm_key`, unique per workspace, so `A→B` and `B→A` resolve
to the same conversation. The peer must be a member of the same workspace
(`404` otherwise), and a DM with yourself is `400`.

**`body` is plain text, never HTML.** The chat composer is the highest-traffic
input in the product; accepting rich text there is the widest stored-XSS door
in the app. Clients render it as text.

```jsonc
// Conversation
{
  "id": "…", "workspace_id": "…", "kind": "channel",
  "name": "umumiy",            // "" for a DM
  "title": "umumiy",           // DM: the other person's name
  "topic": "", "is_private": false,
  "peer": null,                // DM: the other UserSummary
  "last_message": { "id": "…", "body": "Salom", "author": {…}, "created_at": "…" },
  "last_message_at": "2026-08-11T06:58:26Z",
  "unread": 3,                 // other people's messages since your last read
  "is_member": true,
  "created_at": "…"
}
```

Reading `GET .../messages/` marks the conversation read for the caller.

**Realtime.** `ws/chat/{conversation_id}/` (§15.1 ticket handshake, same as the
other channels). The socket is **read-only**: it emits `chat.message.created`
and answers `ping` with `pong`; sending happens over REST so validation,
throttling and broadcast stay in one place. The group `chat.<id>` is the
authorisation boundary — the handshake runs the same visibility predicate as
the REST list, and embedded `email` is nulled in every frame (§15.2).

---

## 15. WebSocket contract — `apps.realtime`

### 15.1 Channels & auth

| Channel | URL | Who may connect | Carries |
|---|---|---|---|
| List | `ws(s)://<host>/ws/list/{list_id}/?ticket=<ticket>` | anyone with read access to the list (same predicate as REST: `space_is_visible`) | `task.*`, `comment.*`, `attachment.*` and presence **for that one list** |
| Workspace | `ws(s)://<host>/ws/workspaces/{workspace_id}/?ticket=<ticket>` | any workspace member | `task.*` and `list.updated` **for the spaces this caller can see**, plus `permission.updated` and `access.revoked` |

**Server-side groups (v1.3.4).** A frame is serialised once and fanned out to a whole group, so the
group *is* the authorisation boundary — there is no per-recipient filtering. Four groups exist:

| Group | Carries | Membership |
|---|---|---|
| `list.<list_id>` | `task.*`, `comment.*`, `attachment.*`, `presence.*` | every open list socket for that list |
| `space.<space_id>` | `task.*` and `list.updated` | every workspace socket whose caller can see that space |
| `workspace.<workspace_id>` | **only** `permission.updated` | every workspace socket |
| `user.<user_id>` | `access.revoked` | every socket of that user, both channels |

A **workspace socket subscribes to exactly the `space.<id>` groups that `visible_spaces_q()` returns
for its membership** — the same predicate `GET spaces/` uses — so the socket and REST can never
disagree about what the caller may see. Before v1.3.4 `workspace.<id>` itself carried `task.*` and
`list.updated`, so a guest holding a sidebar socket received task titles and list names from private
spaces that REST answered `404` for. `workspace.<id>` now carries only `permission.updated`, which
contains a workspace id and a version integer and no space content.

**Scope is re-evaluated, not just checked at handshake.** A socket outlives a permission change, so
on `permission.updated` **or** `access.revoked` every consumer recomputes its own scope
(`BaseConsumer.resync_scope`): a list socket re-runs the read check and closes with `4403` if it
fails; a workspace socket recomputes its visible-space set and silently joins/leaves `space.<id>`
groups. Losing one space therefore stops the frames without closing the sidebar socket; losing
workspace membership closes everything.

**Handshake ticket (v1.3.0, BINDING).** Browsers cannot set headers on a WebSocket handshake, so the credential has to travel in the query string — where every proxy, load-balancer access log, APM trace and browser history entry records it verbatim. The credential is therefore a **single-use ticket**, not an access token:

```
POST realtime/ticket/          Auth: Bearer <access>       throttle scope `realtime_ticket` (60/min)
200 → {"ticket": "…opaque…", "expires_in": 30}
```

This is **endpoint #84** (`apps/accounts/urls.py`). Until v1.3.4 it was specified only in this paragraph and appeared in no table, which is how the inventory came to disagree with itself.

- The ticket is opaque (no claims), lives **30 seconds**, and is destroyed the moment it is redeemed. A ticket recovered from a log is worthless: it is either expired or already spent. The server stores only a SHA-256 of it, so a cache dump does not hand out live tickets either.
- Two handshakes racing on the same ticket: exactly one wins, the other is rejected.
- `?token=<access>` **remains accepted for backwards compatibility but is DEPRECATED** and will be removed in a later version. Clients must prefer `?ticket=`, falling back to `?token=` only when `realtime/ticket/` is unavailable. When both params are present, `ticket` wins and `token` is not read.
- No cookie auth in either mode — `apps/realtime/middleware.py` (`JWTAuthMiddleware`) is deliberately not stacked on channels' `AuthMiddlewareStack`.
- Invalid/expired/replayed ticket, invalid token, or no read permission on the target: the server sends one `error` frame (or nothing at all for a bad credential) and closes the socket. No `connection.ack` is ever sent on a rejected socket.
- On success the first server frame is `connection.ack`. Group names server-side: `list.<list_id>`, `workspace.<workspace_id>`, `user.<user_id>`.
- Reconnect: exponential backoff 1s → 30s with jitter, and a **fresh ticket per attempt**; on `connection.ack` the client **refetches** the affected queries. There is no server-side replay/backfill — refetch is authoritative.

**Close codes (application range).**

| Code | Meaning | Client behaviour |
|---|---|---|
| `4403` | Access to this workspace/space was revoked while the socket was open (§15.3 `access.revoked`) | **Terminal** — do not reconnect; invalidate the affected queries and let the REST layer (`404`/`403`) drive the UI |
| `4029` | Inbound rate limit exceeded (see below) | Reconnect with the normal backoff; fix the client's send loop |

**Inbound rate limit (BINDING).** Each socket carries a token bucket of **30 client→server frames per 10 seconds** (burst 30, refill 3/s). Exceeding it produces one `error` frame with code `throttled` and then a `4029` close. `presence.ping` cadence must stay well inside this budget.

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

- `payload.data` is shape-identical to the corresponding REST `GET` — same serializer, same keys, same types (events are emitted from the service/serializer layer, never from views). **Two deliberate value-level exceptions, both because a broadcast has no requesting user:**
  - **`email` is always `null`** in every embedded `UserSummary` of every frame (v1.3.4). REST masks `email` per caller (v1.3.2); one broadcast payload reaches recipients of differing authority, so it is masked for everyone. The key is always present — this is exactly the shape a guest already receives over REST. Read emails from `workspaces/{id}/members/`, never from a frame.
  - **`attachment.added` → `data.download_url`** is built without a request. REST returns an absolute URL (`request.build_absolute_uri`); the broadcast prepends `PUBLIC_BASE_URL`, falling back to `CSRF_TRUSTED_ORIGINS[0]`. **When neither is configured — which is the case in dev and in the test suite today — the broadcast URL stays root-relative (`/api/v1/attachments/{id}/download/`) while REST is absolute.** Clients must therefore resolve `download_url` against the API origin rather than assuming it is absolute. Set `PUBLIC_BASE_URL` in any deployment that wants the two byte-identical.
- `event_id` is unique per event; clients apply events idempotently (same `event_id` twice = no-op).
- Echo suppression: drop any frame where `payload.actor.client_id` equals this tab's own client id.
- `rebalanced` appears only on `task.moved`; `true` means "positions in this `(list_id, status_id)` scope were renumbered — refetch, don't patch."
- For `*.deleted` events, `data` is `{"id": "…", "list_id": "…"}` (task) / `{"id": "…", "task_id": "…"}` (comment). `attachment.removed` uses the same `{"id", "task_id"}` shape.

### 15.3 Event types (closed set; channels revised in v1.3.4)

| `type` | Channel | `data` |
|---|---|---|
| `connection.ack` | both | `{"channel", "user_id"}` |
| `task.created` | list **+ space** | Task |
| `task.updated` | list **+ space** | Task (also emitted per task re-pointed by a status-set replacement, and on soft-delete restore) |
| `task.moved` | list **+ space** | Task (+ `rebalanced` flag in payload) |
| `task.deleted` | list **+ space** | `{"id", "list_id"}` |
| `comment.created` | list | Comment |
| `comment.updated` | list | Comment |
| `comment.deleted` | list | `{"id", "task_id"}` |
| `attachment.added` | list | Attachment (v1.2.0 — see §10.7; `download_url` caveat in §15.2) |
| `attachment.removed` | list | `{"id", "task_id"}` (v1.2.0) |
| `list.updated` | **space** (was: workspace) | List (rename/recolor/archive/move/counts changed) |
| `permission.updated` | workspace | `{"workspace_id", "version"}` (v1.1.0, R23 — see §18.6) |
| `access.revoked` | `user.<id>` | `{"workspace_id", "space_id"\|null}` (v1.1.0, R23 — see §18.6) |
| `presence.join` / `presence.leave` | list | `{"user": PresenceUser}` |
| `presence.sync` | list | `{"users": [PresenceUser]}` (sent to a client right after its own ack) |
| `error` | both | `{"code", "message"}` (mirrors §1.6 codes, e.g. `permission_denied`), then the socket closes |

`PresenceUser` is a **strict subset** of `UserSummary`: `{"id", "full_name", "avatar", "avatar_color"}` — **no `email`, no `profession`** (v1.3.0, BINDING). Presence is readable by anyone who can open the list channel, including guests, and a work-email roster must not be harvestable from it. Clients that need an email read it from `workspaces/{id}/members/` — readable by every role since v1.3.2, but a guest receives `email: null` there too.

**Reading the "Channel" column (v1.3.4).** It names the *group* a frame is published to, not the
socket that receives it. A `task.*` frame is published twice — once to `list.<id>` and once to
`space.<id>` — so a client with both a list socket and a sidebar socket open receives it on each and
must deduplicate on `event_id` (it already must, §15.2). `comment.*` and `attachment.*` are
**list-only**: a sidebar socket never sees them, so a client showing comment or attachment counts
outside a list view has to refetch rather than listen. `list.updated` moved from the workspace group
to the space group — a list's *name alone* discloses the contents of a private space — so a client
that subscribed to the workspace channel expecting sidebar updates for every space now gets them
only for spaces it can actually see, which is the same set the sidebar is allowed to render.

`access.revoked` on a socket whose scope it covers is **not** a hint: the server emits the frame and then closes that socket with `4403`. A list socket is covered by a workspace-level revoke (`space_id: null`) and by a space-level revoke naming its own space; a workspace socket is covered only by a workspace-level revoke, because losing access to one space does not end workspace membership.

Client→server messages (closed set): `{"type": "presence.ping"}`, `{"type": "presence.typing"}`. Presence liveness is ping-driven; a client that misses its ping window gets a `presence.leave` broadcast on its behalf. Anything else from the client is ignored, and more than 30 inbound frames per 10s closes the socket with `4029` (§15.1).

A mutation that fails validation/permission emits **no** event. Every successful mutation emits exactly one event (except status-set replacement: one `task.updated` per re-pointed task).

---

## 16. Endpoint inventory (91)

**91 method+path pairs under `/api/v1/`.** This table is the authoritative count; the header at the
top of the file quotes it. Verified by walking Django's URL resolver, not by counting rows by hand.

> **v1.3.5 adds #85, `GET public/showcase/` (§14.1).** It is the second public
> read endpoint after `health/` and the only one that reads the database
> without a token, so the disclosure rule in §14.1 is part of this contract,
> not an implementation detail.

> **The `#` column in §2–§15 is a stable identifier, not a dense sequence.** Numbers are assigned
> once and never reused, so the ordering reflects the order features landed, not the order they are
> documented in. v1.3.4 closed the four holes that made the inventory unauditable: **#65–69** are the
> five §18 permission endpoints, **#78** is `health/`, and **#84** is `POST realtime/ticket/` — all of
> them were specified in prose but numbered nowhere, which is why the header said 83, this heading
> said 84, and the table below summed to 83. There are now no gaps in 1–84.

| Group | Count | Endpoints |
|---|---|---|
| Permissions | 5 | catalog, matrix GET/PUT, matrix reset, my-permissions |
| Auth | 6 | register, login, refresh, logout, password/change, demo (dev-only, `DEMO_MODE`) |
| Profile | 3 | me GET/PATCH, me/avatar POST |
| Workspaces | 6 | list, create, retrieve, update, delete, tree |
| Members | 5 | list, profile, role PATCH, remove, leave |
| Invitations | 7 | list, create, revoke, resend, lookup, accept, decline |
| Spaces | 5 | list, create, retrieve, update, delete |
| Space members | 5 | list, add, update access, remove, bulk |
| Folders | 5 | list, create, retrieve, update, delete |
| Lists | 6 | list, create, retrieve, update, delete, move |
| Status sets | 5 | space GET/PUT, list GET/PUT/DELETE |
| Tasks | 10 | list, create, retrieve, update, delete, move, watch POST/DELETE, task activity, workspace activity |
| Attachments | 4 | list, upload, download, delete |
| Tags | 4 | list, create, update, delete |
| Comments | 4 | list, create, update, delete |
| Search | 2 | workspace tasks, workspace search |
| Realtime | 1 | handshake ticket (`POST realtime/ticket/`, §15.1) |
| Chat | 6 | conversations list/create, direct, join, messages list/post (§14.2) |
| Misc | 2 | health, public showcase (§14.1) |

Sum: 5+6+3+6+5+7+5+5+5+6+5+10+4+4+4+2+1+6+2 = **91**.

WebSocket: `/ws/list/{list_id}/`, `/ws/workspaces/{workspace_id}/`, `/ws/chat/{conversation_id}/` — 3 client-facing channels over 5 server-side groups (§15.1, plus `chat.<conversation_id>`).

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
| R18 | §1.7's static role table vs the editable matrix (`DESIGN_PERMISSIONS.md` §A) | **Matrix wins.** §1.7 now describes the *default*; effective authority is `DEFAULT_MATRIX` + the workspace's `RolePermission` overrides (§18). `owner` is locked to the full catalog. |
| R19 | DATA_MODEL D8 (no per-space membership) vs the PM requirement | **D8 is superseded**: `SpaceMember(space, user, access, source)` is introduced (`space_members` table). `Space.is_private` becomes the "ACL is mandatory" flag rather than a role cut-off. |
| R20 | Private-space visibility: role-based (guest cut-off) vs ACL-based | Target rule: a private space is visible only via `space.read_private` **or** a `SpaceMember` row; migration `workspaces.0004` backfills so nobody loses access. **Staged**: the ACL rule ships behind `SPACE_ACL_ENABLED` (default off); until it is enabled the v1.0.0 rule (guest × private → `404`) stands, extended so an explicit `SpaceMember` row also grants visibility. |
| R21 | Register response has no workspace reference when joining via invite | `AuthResponse.workspace_id` is reserved as an optional field (`DESIGN_PERMISSIONS.md` §D.8). **Not implemented yet.** |
| R22 | `invitations/lookup/` returns a minimal payload | To be extended with workspace colour, inviter summary and `account_exists`, never exposing `id` fields, plus an `invite_lookup` 30/min per-IP throttle (§D.7). **Not implemented yet.** |
| R23 | WS event vocabulary was closed at v1.0.0 | Extended with `permission.updated` (workspace channel) and `access.revoked` (`user.<id>` channel) — see §15.3. |
| R24 | Should a completed task still accept files? | **Yes, binding.** Attachment endpoints never inspect `completed_at`/`status.type`; the whole point of the feature is filing the deliverable after the work is done (§10.7). |
| R25 | `DATA_MODEL.md` still describes an **`apps.spaces` Django app** (§1, every §5 heading, its `INSTALLED_APPS` block) that has never existed. R1 ruled against it in v1.0.0 but nobody amended the file, so it kept telling readers to create a phantom app. | **R1 restated and DATA_MODEL amended (v1.3.4).** `Space`, `Folder`, `TaskList`, `StatusSet`, `Status` and `SpaceMember` live in **`apps.workspaces`**; `apps.core` holds only abstract bases and the permission catalog. A ruling that is not carried into the ruled-on document is not a ruling — R1 is now applied at every one of the six sites. |
| R26 | `DATA_MODEL.md:12` claimed **"if code and this document disagree, the document wins"**, while this contract's Authority row calls it authoritative for field names and types. The file had meanwhile drifted by one non-existent app and four missing models. | **The blanket clause is withdrawn (v1.3.4).** Precedence is now scoped: DATA_MODEL is authoritative for **intended shape** — field names, types, nullability, constraints, the ordering strategy — and **the code is authoritative for what exists**. A disagreement is a bug in the document until someone proves otherwise. A "document wins" rule is only safe on a document with a drift gate, and this one has none. |
| R27 | `catalog_version` had **three different values in three binding documents**: code `5`, this contract `2` (§18.1/§18.2), `DESIGN_PERMISSIONS.md` `1` (§D examples). `frontend/src/types/api.ts:695` carried a comment saying `2`. | **Code wins — `CATALOG_VERSION` in `backend/apps/core/permissions.py` is the only source.** It is **5** (49 codes). Documents must not restate it in prose; §1.7.1 is generated from the catalog and every other mention is now either generated or an example labelled as such. |
| R28 | Endpoint count: the header said **83**, the §16 heading said **84**, and the §16 table summed to **83**. The numbered rows had holes at 65–69 and 78, and `POST realtime/ticket/` was specified in §15.1 prose but appeared in no table. | **84**, and **§16 is the authoritative count** (verified against Django's URL resolver, not by hand). `#65–69` = the five §18 permission endpoints, `#78` = `health/`, `#84` = `POST realtime/ticket/`. The `#` column is a stable id, never reused; there are now no gaps in 1–84. |
| R29 | `WorkspaceSerializer.get_my_role` can `return None`, but `Workspace.my_role` is non-nullable in `frontend/src/types/api.ts:153`. | **The TypeScript type wins — `my_role` is never `null` on the wire.** Every call site supplies either a `roles` map built from the caller's own memberships or a `membership` matching the workspace, and the one construction without context (`WorkspaceListCreateView.post`) is used for input validation only and its `.data` is never returned. The `None` branch is unreachable defensive code, not a documented state. **If a future call site can reach it, that is a bug to fix in the serializer, not a nullable field to add to the contract.** |
| R30 | Read codes: `workspace.read`, `task.read`, `space.read` and `member.read` are in the catalog and editable in §18.3, but for several versions almost no endpoint resolved one — revoking `task.read` did not stop anyone reading tasks. | **Closed in code, not in prose (2026-08-10).** `workspace.read`, `task.read` and `member.read` are now real gates on the reads listed in §1.7 and return `403` when revoked. **`space.read` remains deliberately different**: it is an input to *visibility* (`visible_spaces_q`, `space_is_visible`, `SPACE_VIEWER_GRANTS`), so revoking it yields `404`/absence rather than `403`. A short list of reads is still gated by membership + space visibility alone; §1.7 enumerates them exactly rather than implying blanket coverage. |
| R31 | `docs/UI_SPEC.md` is stamped **"Status: Binding"** but predates Tailwind v4, the Uzbek UI, handshake-ticket auth, the permission-code gating model and six shipped screens, and it ends mid-document at §6.8 while forward-referencing §7–§18. | **Demoted to historical (v1.3.4).** It is no longer binding on anything. Where it disagrees with this contract or with the code, it loses — silently and always. Its header now says so; see the superseded banner in that file. |
| R32 | `docs/SPRINT_PLAN.md` mandates that `frontend/src/types/api.ts` be **generated** by `openapi-typescript` from `docs/openapi.json` and "never hand-edited". No `docs/openapi.json` exists, there is no `gen:api` script, and the file is hand-written. | **The hand-written file wins.** It is accurate — its `PermissionCode` union matched the catalog exactly — and `CLAUDE.md` already describes it correctly as hand-maintained mirroring this contract. The generation pipeline is an unbuilt aspiration and SPRINT_PLAN is marked accordingly; **it must not be cited as a reason to reject a hand edit to that file.** (It does now need one: `space.change_visibility` is missing from the union — see §1.7.1.) |

---

## 18. Permissions — granular matrix

Upstream: `docs/DESIGN_PERMISSIONS.md` §A–§D.5. The permission **catalog lives in code** (`backend/apps/core/permissions.py`, 49 codes in 9 groups, `catalog_version = 5`); **grants live in the database** (`RolePermission`). A missing row falls back to the catalog default, so new codes need no backfill.

- `owner` is never stored: `role == "owner"` short-circuits to allow, and the table carries `CheckConstraint(role != 'owner')`.
- `Workspace.permissions_version` (read-only, serialized on the Workspace object) is both the optimistic-concurrency token and the permission cache key.
- Codes are `<resource>.<action>`, `[a-z_]+\.[a-z_]+`, max 64 chars. Codes are never removed, only deprecated.

### 18.1 `GET permissions/` (endpoint 65)

Auth required, no role required, **not paginated**.

```json
{
  "catalog_version": 5,
  "groups": [{
    "key": "task", "label": "Vazifalar",
    "permissions": [{
      "code": "task.delete", "label": "Vazifani o'chirish",
      "description": "Vazifani soft-delete qiladi; 30 kun ichida tiklash mumkin.",
      "default_roles": ["admin"], "owner_only": false, "sensitive": false
    }]
  }]
}
```

`default_roles` **never** contains `owner`. `group.label` and every `label`/`description` are Uzbek UI strings; `key` and `code` are stable English identifiers and are never localized.

`default_roles` lists only the three assignable roles; `owner` is never in it (AD-3). `catalog_version`
is bumped whenever the catalog's shape changes and is the value the frontend caches against — it is
**5** today, and §1.7.1 is generated from the same source, so the two can never disagree.

### 18.2 `GET workspaces/{id}/role-permissions/` (endpoint 66)

Requires `workspace.manage_permissions` (owner-only by default).

```json
{
  "workspace_id": "…", "version": 7, "catalog_version": 5,
  "roles": {
    "owner":  { "locked": true,  "permissions": ["…all 49 codes…"] },
    "admin":  { "locked": false, "permissions": ["…"] },
    "member": { "locked": false, "permissions": ["…"] },
    "guest":  { "locked": false, "permissions": ["…"] }
  },
  "overrides": [
    { "role": "member", "permission": "space.create", "allowed": true,
      "updated_by_id": "…", "updated_at": "2026-08-10T11:00:00Z" }
  ]
}
```

`permissions` is alphabetically sorted. `overrides` lists only rows that differ from the catalog default (the UI's "changed" badge). Errors: `401`, `403`, `404`.

### 18.3 `PUT workspaces/{id}/role-permissions/` (endpoint 67)

```json
{ "expected_version": 7,
  "roles": { "member": { "space.create": true, "task.delete": false },
             "guest":  { "comment.create": false } } }
```

**200:** identical shape to `GET`, with `version` = 8. Side effects: `permissions_version += 1` and a `permission.updated` WebSocket frame on the workspace channel.

| HTTP | `code` | When | `details` |
|---|---|---|---|
| 400 | `validation_error` | `expected_version` missing | `{"expected_version": ["This field is required."]}` |
| 400 | `validation_error` | Unknown code | `{"roles.member.foo_bar": ["Noma'lum ruxsat kodi."]}` |
| 400 | `validation_error` | Writing the `owner` row | `{"roles.owner": ["Owner ruxsatlarini o'zgartirib bo'lmaydi."]}` |
| 400 | `validation_error` | Granting an `owner_only` code | `{"roles.admin.workspace.manage_permissions": ["Bu ruxsat faqat owner uchun."]}` |
| 400 | `validation_error` | Monotonicity broken | `{"monotonic": ["'space.create' member'da yoqilgan, admin'da o'chirilgan."]}` |
| 403 | `permission_denied` | Caller lacks `workspace.manage_permissions` | `{}` |
| 403 | `permission_denied` | Editing one's own role or above | `{"reason": "self_escalation", "role": "admin"}` |
| 409 | `conflict` | `expected_version` mismatch | `{"expected_version": 7, "current_version": 9}` |

`roles` is a strict whitelist over the catalog and over `{admin, member, guest}` — an unknown key is a `400`, never a silent ignore. Every rejection is side-effect free: `permissions_version` does not move.

### 18.4 `POST workspaces/{id}/role-permissions/reset/` (endpoint 68)

Body `{"role": "member"}` resets one role, `{"role": null}` (or `{}`) resets all three. **200** returns the `GET` shape with the bumped `version`. Same permission and rank guard as `PUT`.

### 18.5 `GET workspaces/{id}/my-permissions/` (endpoint 69)

Any member, guests included — membership only, no code. The frontend builds all UI gating from this single request.

```json
{ "workspace_id": "…", "role": "member", "version": 7,
  "permissions": ["comment.create", "list.create", "task.create", "…"],
  "spaces": [{ "space_id": "…", "access": "manager" }] }
```

For `owner`, `permissions` is the entire catalog. `spaces` lists the caller's `SpaceMember` rows in this workspace (`access` ∈ `viewer` | `contributor` | `manager`). Client-side `can()` is an affordance only — the server always re-checks.

### 18.6 New WebSocket events (see §15.3)

| `type` | Channel | `data` | Client action |
|---|---|---|---|
| `permission.updated` | workspace | `{"workspace_id", "version"}` | Invalidate `my-permissions/` and `role-permissions/` |
| `access.revoked` | `user.<id>` | `{"workspace_id", "space_id"\|null}` | Invalidate; if viewing the resource, navigate to `/w/{id}` |

*End of contract — version 1.1.0, 2026-08-10.*
