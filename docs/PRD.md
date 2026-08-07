# Product Requirements Document — Clickish (ClickUp clone) MVP

## Doc control

| Field | Value |
| --- | --- |
| Document | Product Requirements Document (PRD) |
| Product | Clickish |
| Version | 1.0 |
| Date | 2026-08-07 |
| Owner | Product |
| Status | Approved for build |
| Applies to | MVP release (feature areas F1–F9) |
| Binding source of truth | `DECISIONS.md` (decision sheet). Where this PRD and the decision sheet disagree, the decision sheet wins and this PRD is defective. |
| Downstream docs | `docs/DATA_MODEL.md`, `docs/API_CONTRACT.md`, `docs/SPRINT_PLAN.md`, `docs/UI_SPEC.md` |
| Audience | Engineering (backend + frontend), QA, Design |

### TL;DR

Clickish is a ClickUp-style work management app built for small product and ops teams who have outgrown a flat board but refuse to pay the configuration tax of an enterprise tracker. The MVP delivers exactly nine feature areas: authentication and profile, the Workspace → Space → Folder (optional) → List hierarchy, tasks with a fixed field set, per-Space/per-List custom status sets, two interchangeable views (List and Board) with drag-and-drop reordering, comments, realtime collaboration over WebSockets, search/filter/sort, and members/roles/invitations with four roles (`owner`, `admin`, `member`, `guest`). It is deliberately narrow: Docs, Goals, Dashboards, Gantt, automations, integrations, time tracking, file attachments, custom fields, and subtasks/checklists are all out of scope. Success is measured by activation, time-to-first-task, D7 retention, realtime broadcast latency p95 under 300 ms, and a task-move error rate under 0.5%. Everything in this document — field names, role names, priority values, status types, endpoint paths, error codes — is taken verbatim from the decision sheet; nothing here invents new surface area.

---

## 2. Vision & problem statement

### 2.1 The problem

Small cross-functional teams (5–40 people) live between two bad options.

1. **Flat tools (Trello, Notion boards, spreadsheets).** Easy to start, impossible to scale. There is one level of grouping, so "Marketing Q3 campaign backlog" and "Engineering bugs" end up as sibling boards with no shared home, no shared vocabulary, and no way to see across them. Status is whatever column the card sits in, so the same word means different things on different boards.
2. **Heavy trackers (Jira, enterprise Asana).** Powerful, but the unit of setup is a project with a workflow scheme, an issue-type scheme, a permission scheme, and a screen scheme. Changing "Done" to "Shipped" is a ticket to an admin. Teams pay a permanent configuration tax for flexibility they use once.

The concrete symptoms we heard repeatedly in discovery:

- Work is fragmented across 6–12 boards with no hierarchy, so nobody can answer "what is my team doing this week" without a manual roll-up.
- Every team wants slightly different states (`Backlog / In progress / In review / Done` for engineering, `Idea / Drafting / Scheduled / Published` for marketing) and current tools force either one global workflow or one board per team.
- Switching from a list to a board means re-creating the data or accepting a second source of truth.
- Multi-person editing is not live. Two people move the same card and one silently loses.
- Clients and contractors either get full access or get emailed screenshots. There is no safe read-mostly seat.

### 2.2 Why now

- Remote/hybrid teams changed the default from "walk over and ask" to "the tool is the meeting." Latency and staleness are now felt as friction, not as a nice-to-have.
- Realtime infrastructure is commodity: Django Channels + Redis gives us multi-tab, multi-user live updates without a bespoke sync engine.
- The market has bifurcated into "toy" and "enterprise." The middle — hierarchical, customizable, fast, and learnable in ten minutes — is where teams are actively switching.
- Our stack decisions are already locked (Django 5.2 / DRF / Channels / Next.js 15), so the MVP is a scope problem, not a technology problem.

### 2.3 Product vision (one sentence)

> Clickish gives a team one home for all of its work — organized in a hierarchy deep enough to be honest and flexible enough to be theirs — where every status set is customizable, every list is instantly viewable as a list or a board, and every change appears for everyone else in under a third of a second.

### 2.4 MVP success metrics

Measured over the first 8 weeks after GA. Each metric has an owner, an instrumentation point, and a target that gates "MVP successful."

| # | Metric | Definition | Instrumentation | Target |
| --- | --- | --- | --- | --- |
| M1 | **Activation rate** | % of newly registered users who, within 24h of `POST /api/v1/auth/register/`, belong to a workspace with ≥1 Space, ≥1 List, and ≥3 Tasks created | Backend analytics event on `POST /api/v1/lists/{id}/tasks/`, aggregated per `user_id` | ≥ 40% |
| M2 | **TTFT — time to first task** | Median wall-clock seconds from successful `POST /api/v1/auth/register/` (201) to the first successful `POST /api/v1/lists/{id}/tasks/` (201) by the same `user_id` | Server-side timestamps (`created_at`, UTC) | ≤ 180 s median, ≤ 420 s p90 |
| M3 | **D7 retention** | % of activated users who perform ≥1 write request (`POST`/`PATCH`/`DELETE` under `/api/v1/`) on day 7 (±1 day) after registration | Request log keyed by `user_id` | ≥ 30% |
| M4 | **Realtime latency p95** | Time from the DB commit of a mutation to the WebSocket frame being written to a subscribed client's socket, for `task.created`, `task.updated`, `task.moved`, `task.deleted`, `comment.created` | `ts` on the server frame vs. commit timestamp; sampled synthetic subscriber per environment | **p95 < 300 ms**, p99 < 800 ms |
| M5 | **Task-move error rate** | Failed `PATCH /api/v1/tasks/{id}/move/` calls ÷ total move calls, where "failed" = any 4xx/5xx **excluding** `permission_denied`; specifically counts `position_conflict`, `invalid_status_for_list`, `validation_error`, `server_error` | API metrics by endpoint + `error.code` | < 0.5% of all moves; `position_conflict` specifically < 0.1% |

Supporting (non-gating) health metrics: median tasks per active workspace, % of Lists that override their Space's status set, % of workspaces with ≥1 `guest`, WebSocket reconnect rate per session-hour.

---

## 3. Target personas

Four personas. Every MVP feature must serve at least one of them; anything serving none of them is out of scope by definition.

### 3.1 Maya — the team lead

| Attribute | Detail |
| --- | --- |
| Role in Clickish | Workspace role `admin` (occasionally `owner` for her own workspace) |
| Context | Leads a 9-person product squad. Runs a weekly planning session and a daily standup. |
| Goals | See the whole squad's work in one place; rebalance priorities in seconds during standup; keep the board honest without nagging people |
| Frustrations | Boards drift out of date between meetings; "Done" means five different things; she rebuilds the same status columns for every new project; she cannot reorganize work without breaking someone's saved filter |
| Jobs-to-be-done | "When we plan a sprint, I want to drag tasks between statuses and reorder them by importance, so the top of the column is genuinely what we do next." · "When a project starts, I want to spin up a List with the statuses my team already uses, so nobody has to learn a new vocabulary." · "When we standup, I want the board to update live as people talk, so I never present stale state." |
| MVP features touched | F2 (creates Spaces/Folders/Lists), F4 (defines Space-level and List-level status sets), F5 (Board view, drag & drop), F7 (realtime during standup), F8 (filter by `assignee`, `priority`, `due`), F9 (invites members, sets roles) |

### 3.2 Dev Dan — the IC engineer

| Attribute | Detail |
| --- | --- |
| Role in Clickish | Workspace role `member` |
| Context | Backend engineer. Lives in the editor; treats the tracker as a tax to be minimized. |
| Goals | Get in, update state, get out; never lose context; find "my stuff" in one keystroke |
| Frustrations | Slow page loads; mouse-only UIs; being forced to fill six mandatory fields to log a bug; losing a comment draft on refresh; his edits colliding with a PM's edits |
| Jobs-to-be-done | "When I finish work, I want to move a task to a `closed`-type status in under three seconds, so updating the tracker never interrupts flow." · "When I open the app, I want a filtered view of tasks where `assignee=me`, so I don't triage anyone else's work." · "When I write a comment, I want to know it reached my teammate immediately, so I don't repeat myself in chat." |
| MVP features touched | F1 (login, profile, `timezone`), F3 (edits `status_id`, `priority`, `due_date`, `assignee_ids`), F5 (List view, keyboard reorder), F6 (comments), F7 (realtime), F8 (`assignee=me`, `status_type=open`, `ordering=priority_order`) |

### 3.3 Priya — the ops admin / workspace owner

| Attribute | Detail |
| --- | --- |
| Role in Clickish | Workspace role `owner` |
| Context | Operations manager. Owns billing, access, and the shape of the workspace. Also the person who gets asked "can you add Carlos?" |
| Goals | Correct access for everyone, no orphaned data, a hierarchy that still makes sense in six months |
| Frustrations | No safe way to give a contractor limited access; ex-employees left in the member list; deleting something and not knowing what it cascaded to; role changes requiring support tickets |
| Jobs-to-be-done | "When someone joins, I want to invite them by email with an explicit role, so access is right on day one." · "When someone leaves, I want to remove them and know what happens to their assignments." · "When I restructure, I want to move a List between Folders without breaking its tasks." · "When I hand over the workspace, I want to transfer ownership without deleting anything." |
| MVP features touched | F1, F2 (workspace/space structure, `GET /api/v1/workspaces/{id}/tree/`), F4 (Space-level status sets as org standard), F9 (invitations, role changes, removal, ownership transfer), cross-cutting permissions |

### 3.4 Carlos — the external guest / client

| Attribute | Detail |
| --- | --- |
| Role in Clickish | Workspace role `guest` |
| Context | Agency client (or contractor) invited into one workspace to follow delivery and occasionally do assigned work. |
| Goals | See status without asking; leave feedback in context; do the tasks assigned to him — and nothing else |
| Frustrations | Being sent PDF status reports; being given a full seat and then accidentally deleting things; not knowing whether his comment was seen |
| Jobs-to-be-done | "When I want status, I want to open the List and read it, so I don't email for an update." · "When I have feedback, I want to comment on the exact task, so context isn't lost." · "When something is assigned to me, I want to update it, so the team sees my progress." · "When I try something I'm not allowed to do, I want a clear message, not a silent failure." |
| MVP features touched | F1, F2 (read-only navigation), F3 (edit **only** tasks where he is in `assignee_ids`), F5 (read views; drag limited to his own tasks), F6 (create comments; edit/delete his own), F7 (receives realtime events), F8 (search within what he can read). Explicitly **cannot** see the members page (F9). |

### 3.5 Persona → feature coverage matrix

| Feature area | Maya (admin) | Dan (member) | Priya (owner) | Carlos (guest) |
| --- | --- | --- | --- | --- |
| F1 Authentication & profile | ✓ | ✓ | ✓ | ✓ |
| F2 Hierarchy | ✓ create | ✓ create folders/lists | ✓ own structure | read only |
| F3 Tasks | ✓ | ✓ primary | ✓ | assigned only |
| F4 Custom status sets | ✓ primary | read | ✓ | read |
| F5 Views (List/Board + DnD) | ✓ primary | ✓ | ✓ | read / own tasks |
| F6 Comments | ✓ | ✓ | ✓ | ✓ primary |
| F7 Realtime | ✓ | ✓ | ✓ | ✓ |
| F8 Search, filter, sort | ✓ | ✓ primary | ✓ | scoped |
| F9 Members, roles, invitations | ✓ (not owners) | read list only | ✓ primary | ✗ no access |

---

## 4. Competitive note: what makes ClickUp's UX distinctive

ClickUp's reputation is "does everything," but the parts genuinely worth copying are structural, not featural. Four properties explain most of the perceived difference, and one deliberate omission explains our MVP.

**(a) A deep hierarchy where one level is optional.** ClickUp nests Workspace → Space → Folder → List → Task. Competitors are shallower: Jira gives Project → Issue (with boards as a query over issues), Trello gives Board → List → Card, Asana gives Team → Project → Task → Subtask, Linear gives Team → Project/Cycle → Issue. Depth alone is not the trick — the trick is that **Folder is optional**. A List can live directly under a Space, or inside a Folder under a Space. That single affordance means a team can start flat ("Space: Engineering → List: Bugs") and introduce grouping later ("Space: Engineering → Folder: Q3 Platform → List: Bugs") without migrating anything. Tools with a mandatory middle level force premature taxonomy on day one; tools with no middle level force a flat sprawl by month three. In Clickish this is encoded directly: `POST /api/v1/spaces/{id}/lists/` takes an **optional** `folder_id` in the body, and `PATCH /api/v1/lists/{id}/move/` re-parents a List between `(space_id, folder_id)` scopes. The hierarchy is honest about how teams actually grow.

**(b) Status sets that belong to the container, not to the tool.** In Jira, states live in a workflow scheme owned by an admin; changing them is a governance event. In Trello, status *is* the list — you cannot have both "grouping" and "state" because they are the same object, so a board that wants "by owner" and "by state" needs two boards. ClickUp separates the two: the container (Space or List) owns a reusable set of statuses, and the List's ordering/grouping is independent of it. Clickish adopts this exactly: a `StatusSet` belongs to **either** a Space **or** a TaskList (never both — a CHECK constraint enforces it), and a List's *effective* status set is its own if present, otherwise its Space's. A Space always has one, auto-created. Each `Status` carries `name`, `color`, `order`, and a `type` of `open`, `active`, or `closed` — so "Shipped," "Published," and "Won't fix" can all be different words that the system still understands as closed. That typed layer is what lets us build cross-list filters (`status_type=closed`) over teams that share no vocabulary. The cost of flexibility is handled, not avoided: replacing a List's status set via `PUT /api/v1/lists/{id}/status-set/` requires an explicit `status_mapping` of `{old_status_id: new_status_id}`, so no task is ever silently orphaned.

**(c) Instant view switching over one dataset.** ClickUp's most under-appreciated move is that List and Board are renderings of the same records, not separate artifacts. Toggling is instant and lossless — no export, no sync, no "board version" drifting from "list version." Clickish implements this with one endpoint and one parameter: `GET /api/v1/lists/{id}/tasks/` returns a flat, paginated collection for List view, and the same call with `?group_by=status` returns a grouped payload for Board view. Critically, **view state is per-user-per-list**: which view Dan last used, his collapsed columns, his active filters, and his sort are his, not the List's. Shared global view state is the classic multiplayer bug — Maya switching to Board during standup must not yank Dan out of his filtered List. Per-user state also makes `assignee=me` a sane default rather than a destructive one.

**(d) Keyboard-first speed.** ClickUp's power users barely touch the mouse: a command palette, quick-create, and a task-detail slide-over that never loses the underlying context. Speed here is a product feature, not a performance detail — it is the reason Dan updates the tracker at all. Clickish commits to full keyboard navigation (see §7.3): every drag-and-drop reorder has a keyboard equivalent, and the task panel is a 720 px slide-over from the right that preserves the list behind it.

**(e) What we are deliberately NOT copying in MVP.** ClickUp's weakness is the same as its strength: an enormous surface (Docs, Goals, Dashboards, Gantt/Timeline, Automations, native integrations, time tracking, attachments, custom fields, subtasks and checklists, multiple assignee workflows, recurring tasks, ClickApps toggles). We are copying the *skeleton* — hierarchy, typed custom statuses, dual views, realtime, roles — and none of the *organs*. A ClickUp clone that ships all of ClickUp ships nothing on time and, worse, inherits ClickUp's genuine UX problem: settings sprawl and a first-run experience that overwhelms. Our differentiator in MVP is that the skeleton is fast and complete, not that the feature count is high.

| Dimension | ClickUp (reference) | Jira | Trello | Asana | Linear | **Clickish MVP** |
| --- | --- | --- | --- | --- | --- | --- |
| Hierarchy depth | Workspace → Space → Folder → List → Task | Project → Issue | Board → List → Card | Team → Project → Task | Team → Project/Cycle → Issue | Workspace → Space → Folder (optional) → List → Task |
| Optional middle level | Yes (Folder) | No | No | No | Partly (Project optional) | **Yes (Folder optional)** |
| Custom statuses | Per Space or per List | Per workflow scheme (admin-governed) | Status = the list itself | Fixed sections + custom fields | Fixed typed workflow states | **Per Space or per List, typed `open`/`active`/`closed`** |
| Status semantics for cross-project queries | Status categories | Status categories | None | None | Built-in state types | **`status_type` filter (`open`\|`active`\|`closed`)** |
| List ↔ Board switching | Instant, same data | Board is a separate query/config | Board only | Instant | Instant | **Instant, `?group_by=status`** |
| View state scope | Per-user + shared views | Shared (saved filters) | Shared | Both | Per-user | **Per-user-per-list only** |
| Realtime multiplayer | Yes | Partial (polling-ish) | Yes | Yes | Yes (strong) | **Yes, WebSocket, p95 < 300 ms** |
| External/guest seat | Yes (guest) | Limited | Board-level | Limited | Limited | **Yes, `guest` role** |
| Config burden to first task | Medium | High | Very low | Medium | Low | **Very low (defaults auto-created)** |
| MVP surface (Docs/Goals/Dashboards/Automations) | All present | Some | Power-Ups | Some | Some | **None — out of scope** |

---

## 5. Scope

### 5.1 In scope — 9 feature areas

| ID | Feature area | One-line definition | Primary endpoints / channels | Persona driver |
| --- | --- | --- | --- | --- |
| F1 | Authentication & user profile | Email+password registration, JWT login/refresh/logout, password change, profile read/update including `timezone`, avatar upload | `auth/register/`, `auth/login/`, `auth/refresh/`, `auth/logout/`, `auth/password/change/`, `me/` (GET, PATCH), `me/avatar/` | All |
| F2 | Hierarchy (Workspace/Space/Folder/List) | CRUD for Workspace, Space, Folder, and TaskList with optional `folder_id`, plus ordered re-parenting and a full tree fetch | `workspaces/`, `workspaces/{id}/tree/`, `spaces/`, `folders/`, `lists/`, `lists/{id}/move/` | Priya, Maya |
| F3 | Tasks | Task CRUD over the exact field set, soft delete, assignees, watchers, tags, priority, dates, archive | `lists/{id}/tasks/`, `tasks/{id}/`, `tasks/{id}/watch/` | Dan, Maya |
| F4 | Custom status sets | Per-Space and per-List `StatusSet` with typed `Status` rows, default status, mandatory closed status, mapped migration | `spaces/{id}/status-set/`, `lists/{id}/status-set/` | Maya, Priya |
| F5 | Views (List & Board with drag & drop) | One dataset rendered as List or Board; fractional-index reordering across and within status columns; per-user-per-list view state | `lists/{id}/tasks/?group_by=status`, `tasks/{id}/move/` | Maya, Dan |
| F6 | Comments | Flat comments on a task, own-edit/own-delete, moderator delete, denormalized `comment_count` | `tasks/{id}/comments/`, `comments/{id}/` | Carlos, all |
| F7 | Realtime collaboration | WebSocket fan-out of task/comment/presence events per List and per Space, with echo suppression | `ws/list/{list_id}/`, `ws/space/{space_id}/` | All |
| F8 | Search, filtering & sorting | Task filters, text search, ordering, pagination, plus cross-list workspace search over mixed entity types | `lists/{id}/tasks/`, `workspaces/{id}/tasks/`, `workspaces/{id}/search/` | Dan, Maya |
| F9 | Members, roles & invitations | Four-role membership, invitation lifecycle by email token, role changes, removal, leave, ownership transfer | `workspaces/{id}/members/`, `workspaces/{id}/invitations/`, `invitations/{id}/`, `invitations/accept/`, `invitations/lookup/` | Priya |

Supporting, non-user-facing but in scope: `GET /api/v1/health/`, the standard response envelope, the error-code vocabulary, pagination, and the `core` app (abstract bases, permissions, pagination, exception handler).

### 5.2 Explicitly OUT of scope for MVP

| Excluded capability | Reason for exclusion |
| --- | --- |
| **Docs** (collaborative rich-text documents) | A second editor surface with its own permissions, versioning and realtime model — larger than F1–F9 combined; no persona blocks on it in MVP. |
| **Goals** (OKR objects rolled up from tasks) | Requires a cross-workspace aggregation and progress model; meaningless until there is enough task history to roll up. |
| **Dashboards** (widget grids, charts, reporting) | Depends on stable aggregate queries and a widget framework; premature before F8 filters prove out in production. |
| **Gantt / Timeline view** | A third view renderer with dependency edges and date math; F5 already carries the drag-and-drop risk for MVP. |
| **Automations** (rule triggers/actions) | Needs a durable rule engine, run history and loop protection; high blast radius on a young permission model. |
| **Integrations** (Slack, GitHub, calendar, webhooks) | Each is a separate OAuth, rate-limit and failure-mode surface; no integration is on the activation path. |
| **Time tracking** (timers, logged time) | `time_estimate_minutes` is stored but not tracked against; billing-grade time data has a much higher correctness bar. |
| **File attachments on tasks/comments** | Requires object storage, virus scanning, quota and signed-URL delivery. (Note: `POST /api/v1/me/avatar/` is in scope as the single, narrow image-upload path.) |
| **Custom fields** | A schema-on-data system that changes serialization, filtering, sorting and the whole view layer; the fixed Task field set in §F3 is the MVP contract. |
| **Subtasks / checklists** | Introduces task recursion, roll-up completion, and hierarchical ordering into the `position` scheme; MVP tasks are flat by design. |

Also out of scope by omission (called out to prevent scope creep): task dependencies, recurring tasks, multiple workspaces per invitation, saved/shared views, email notifications beyond invitation emails, mobile apps, SSO/SAML, two-factor authentication, public sharing links, task templates, bulk edit, trash/restore UI beyond the `deleted_at` soft-delete flag, and any view other than List and Board.

### 5.3 Scope guardrails

- The Task field set in F3 is closed. Adding a field is a PRD change, not a ticket.
- The endpoint inventory is 64 endpoints under `/api/v1/`. Adding a 65th requires updating the decision sheet and `docs/API_CONTRACT.md` in the same commit.
- The WebSocket event vocabulary is closed: `connection.ack`, `task.created`, `task.updated`, `task.moved`, `task.deleted`, `comment.created`, `presence.join`, `presence.leave`, `presence.sync`, `error`.
- Every path ends with a trailing slash. Every timestamp is ISO-8601 UTC with `Z`. Every JSON key is snake_case. Every primary key is a UUID.

---

## 6. Feature areas

Conventions used in every feature area below:

- **Priority** on a user story is `P0` (MVP cannot ship without it) or `P1` (MVP should ship with it; cuttable only with Product sign-off in the sprint plan).
- Roles referenced are exactly `owner`, `admin`, `member`, `guest`.
- Error responses always use the envelope `{"error":{"code":...,"message":...,"details":{...},"request_id":...}}` with a code from: `validation_error`, `authentication_failed`, `token_not_valid`, `permission_denied`, `not_found`, `method_not_allowed`, `conflict`, `throttled`, `position_conflict`, `invalid_status_for_list`, `server_error`.
- Collections use the envelope `{"count","page","page_size","total_pages","next","previous","results"}`; single resources are bare JSON objects.

---

## F1 Authentication & user profile

### Why it matters

Nothing in Clickish is public. Every other feature area depends on a resolved `user_id`, a workspace membership, and a role, and the realtime layer depends on the same identity being provable over a WebSocket query parameter. F1 is also the first 60 seconds of the product: TTFT (M2) is measured from the moment `POST /api/v1/auth/register/` returns 201, so any friction here is charged directly against our headline activation metric. Finally, the user's `timezone` set here is what every rendered date in F3/F5/F8 is formatted against — dates are stored UTC and rendered local, and getting that wrong makes "due today" wrong for half the team.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F1-US-01 | prospective user | to register with email and password and immediately land in a usable workspace | I can create my first task without a setup wizard | P0 |
| F1-US-02 | registered user (any role) | to log in and receive an access token (30 min) and a refresh token (14 days) | I stay signed in across a workday without re-entering credentials | P0 |
| F1-US-03 | signed-in user (any role) | my session to refresh silently before the access token expires | a long editing session is never interrupted mid-typing | P0 |
| F1-US-04 | signed-in user (any role) | to log out and have my refresh token blacklisted | leaving a shared machine actually ends my session | P0 |
| F1-US-05 | signed-in user (any role) | to edit my profile — name, `timezone`, avatar — and change my password | dates render in my local time and my identity is recognizable in comments and presence | P1 |

### Acceptance criteria

```gherkin
Scenario F1-AC-01: Successful registration returns tokens and a bootstrapped workspace
  Given no User exists with email "maya@acme.io"
  When the client sends POST /api/v1/auth/register/
       with {"email":"maya@acme.io","password":"C0rrect-horse!","name":"Maya"}
  Then the response is HTTP 201 with a bare JSON object
   And the body contains "access", "refresh", and a "user" object with "id" (uuid), "email", "name", "timezone"
   And a Workspace is created with the registering user as WorkspaceMember.role = "owner"
   And that Workspace has one Space, and that Space has an auto-created StatusSet
   And that auto-created StatusSet contains at least one Status with type "closed"
   And exactly one Status in that set has is_default = true
   And the access token carries the custom claims "user_id" and "email"

Scenario F1-AC-02: Duplicate email registration is rejected
  Given a User already exists with email "maya@acme.io"
  When the client sends POST /api/v1/auth/register/ with the same email
  Then the response is HTTP 400
   And the body is {"error":{"code":"validation_error","message":...,"details":{"email":["..."]},"request_id":"req_..."}}
   And no second User row is created

Scenario F1-AC-03: Expired access token is rejected, refresh rotates
  Given a user holds an access token issued more than 30 minutes ago
  When the client sends GET /api/v1/me/ with Authorization: Bearer <expired access>
  Then the response is HTTP 401 with error.code = "token_not_valid"
  When the client then sends POST /api/v1/auth/refresh/ with the valid refresh token
  Then the response is HTTP 200 with a new "access" AND a new "refresh" in the JSON body
   And the previously used refresh token is blacklisted
  When the client replays the old refresh token to POST /api/v1/auth/refresh/
  Then the response is HTTP 401 with error.code = "token_not_valid"

Scenario F1-AC-04: Unauthenticated access to any resource is refused
  Given the client sends no Authorization header
  When the client sends GET /api/v1/workspaces/
  Then the response is HTTP 401
   And error.code = "authentication_failed"
   And the body contains no workspace data

Scenario F1-AC-05: Profile timezone drives rendering, not storage
  Given a signed-in user with timezone "UTC"
  When the client sends PATCH /api/v1/me/ with {"timezone":"Europe/Berlin"}
  Then the response is HTTP 200 and the returned "timezone" is "Europe/Berlin"
   And a Task whose due_date is stored as "2026-08-07T22:30:00Z"
       is rendered in the UI as "2026-08-08 00:30" for that user
   And the stored value returned by GET /api/v1/tasks/{id}/ is still "2026-08-07T22:30:00Z"

Scenario F1-AC-06: WebSocket rejects a bad token
  Given an invalid or expired access token
  When the client opens ws://<host>/ws/list/{list_id}/?token=<invalid>
  Then the server closes the socket without sending "connection.ack"
   And no task or comment payload is ever delivered on that socket
```

### Rules & edge cases

- Email is the username field (`AUTH_USER_MODEL = accounts.User`); email comparison for uniqueness is case-insensitive and emails are stored lowercased.
- Password rules use Django's default validators (min length, common-password, numeric-only, similarity). Failures return `validation_error` with per-field `details`.
- Access TTL is 30 minutes; refresh TTL is 14 days; `ROTATE_REFRESH_TOKENS=True` and `BLACKLIST_AFTER_ROTATION=True`. The refresh token is returned in the JSON body, not a cookie — see §8 open question OQ-1.
- The client should proactively refresh at ~T-2 minutes of access expiry; a 401 with `token_not_valid` triggers one refresh attempt, then a redirect to login.
- `POST /api/v1/auth/logout/` blacklists the presented refresh token and returns 204 with an empty body. Logging out does not invalidate other devices' refresh tokens.
- `POST /api/v1/auth/password/change/` requires the current password; on success all other refresh tokens for that user are blacklisted and the caller receives a fresh pair.
- `POST /api/v1/me/avatar/` accepts a single image; it is the only file upload in MVP and is not a general attachment mechanism.
- `timezone` must be a valid IANA name; invalid values return 400 `validation_error`. Default on registration is `UTC`.
- Deleting a user account is out of MVP scope; removal from a workspace (F9) is the supported path.
- Rate limiting: login and register are throttled; exceeding the limit returns HTTP 429 with `error.code = "throttled"`.
- There is no password reset by email in MVP (no email-recovery flow beyond invitation emails) — flagged as OQ-4.

---

## F2 Hierarchy (Workspace/Space/Folder/List)

### Why it matters

The hierarchy is the single most distinctive thing we are copying (§4a). It is also the container for every permission decision: role lives on `WorkspaceMember`, and everything below inherits from it. Getting the optional-Folder rule right is what lets Priya start flat and add structure later without a migration. `GET /api/v1/workspaces/{id}/tree/` is the sidebar's only data source, so its shape and speed determine the perceived speed of the whole app.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F2-US-01 | owner | to create a Workspace and have a Space with a working status set created for me | I can start adding work in seconds instead of configuring schemes | P0 |
| F2-US-02 | admin | to create, rename and delete Spaces inside my workspace | each department has its own top-level home with its own defaults | P0 |
| F2-US-03 | member | to create a List directly under a Space **without** creating a Folder first | I am not forced into a taxonomy before I know I need one | P0 |
| F2-US-04 | member | to create Folders and move Lists into them later | I can group related Lists once the project grows | P0 |
| F2-US-05 | owner | to fetch the whole workspace tree in one request | the sidebar renders instantly on load without N+1 requests | P0 |
| F2-US-06 | admin | to reorder Spaces, Folders and Lists by dragging them in the sidebar | the most-used containers sit at the top where my team looks first | P1 |

### Acceptance criteria

```gherkin
Scenario F2-AC-01: A List can be created with no Folder
  Given a member "dan" in workspace W with Space S
  When dan sends POST /api/v1/spaces/{S}/lists/ with {"name":"Bugs"}   # no folder_id
  Then the response is HTTP 201 with a bare JSON object
   And the body has "folder_id": null and "space_id": "{S}"
   And "position" is a non-empty string (first item in an empty scope is "n")
   And the List's effective status set is the Space's StatusSet

Scenario F2-AC-02: A member cannot create or delete a Space
  Given a user with WorkspaceMember.role = "member" in workspace W
  When the user sends POST /api/v1/workspaces/{W}/spaces/ with {"name":"Marketing"}
  Then the response is HTTP 403 with error.code = "permission_denied"
   And no Space row is created
  When the same user sends DELETE /api/v1/spaces/{S}/
  Then the response is HTTP 403 with error.code = "permission_denied"

Scenario F2-AC-03: Deleting a List cascades to its tasks
  Given a List L in Space S containing 12 Tasks and 30 Comments
  When an admin sends DELETE /api/v1/lists/{L}/
  Then the response is HTTP 204 with an empty body
   And the List row is hard-deleted
   And all 12 Tasks and their 30 Comments are removed by CASCADE (not soft-deleted)
   And a subsequent GET /api/v1/lists/{L}/tasks/ returns HTTP 404 with error.code = "not_found"

Scenario F2-AC-04: Moving a List between folders re-scopes its position
  Given List L is at position "n" in scope (space_id=S, folder_id=null)
   And Folder F in Space S already contains Lists at positions "n" and "u"
  When an admin sends PATCH /api/v1/lists/{L}/move/
       with {"folder_id":"{F}","after_id":"<list at n>","before_id":"<list at u>"}
  Then the response is HTTP 200 with the List's new "folder_id" = "{F}"
   And the returned "position" sorts strictly between "n" and "u" by plain string comparison
   And the ordering scope for uniqueness is (space_id, folder_id)

Scenario F2-AC-05: A guest cannot create hierarchy but can read it
  Given a user with WorkspaceMember.role = "guest" in workspace W
  When the guest sends GET /api/v1/workspaces/{W}/tree/
  Then the response is HTTP 200 and contains the Spaces, Folders and Lists the guest may read
  When the guest sends POST /api/v1/spaces/{S}/folders/ with {"name":"Client docs"}
  Then the response is HTTP 403 with error.code = "permission_denied"

Scenario F2-AC-06: Cross-workspace access is a 404, not a 403
  Given user "carlos" is a member of workspace W1 only
   And Space S2 belongs to workspace W2
  When carlos sends GET /api/v1/spaces/{S2}/
  Then the response is HTTP 404 with error.code = "not_found"
   And the body leaks no name, id or existence detail about workspace W2
```

### Rules & edge cases

- Hierarchy is exactly Workspace → Space → Folder (optional) → TaskList → Task. A Folder never contains a Folder; a List never contains a List.
- The Django model for a List is `TaskList` (`db_table` "lists", verbose_name "list"), but the **API resource name is always "list"**: paths are `/api/v1/lists/`, the foreign key field is `list_id`. No API payload ever says "task_list".
- Everything in the hierarchy **hard-deletes with CASCADE**. Only Task and Comment support soft delete (`deleted_at`). Deleting a Space removes its Folders, Lists, Tasks, Comments and its StatusSet.
- Deletion of a Space or Folder is destructive and irreversible in MVP; the UI must require typed confirmation of the container name.
- Ordering scopes: Space is ordered within `(workspace_id)`, Folder within `(space_id)`, TaskList within `(space_id, folder_id)`. All use the fractional `position` CharField (max 64, base-62 alphabet `0-9A-Za-z`), compared as plain strings.
- The first item created in an empty scope receives `position = "n"`.
- Moving a List to `folder_id: null` moves it back to living directly under its Space; that is a valid state, not an error.
- Moving a List across Spaces is **not** supported in MVP: `PATCH /api/v1/lists/{id}/move/` may change `folder_id` and ordering within the same `space_id` only. A cross-space `space_id` in the body returns 400 `validation_error` (see OQ-2).
- Renaming is a `PATCH` on the container; names are non-empty, trimmed, max 255 chars, and are **not** required to be unique among siblings (duplicate names are allowed; ids disambiguate).
- `GET /api/v1/workspaces/{id}/tree/` returns the nested Spaces → Folders → Lists structure (no tasks) ordered by `position ASC`; it is the sidebar contract and must stay under the §7.2 budget.
- A workspace always has at least one Space in practice, but deleting the last Space is permitted; the UI then shows an empty state with a create action.
- Only an `owner` may delete a Workspace (`DELETE /api/v1/workspaces/{id}/`); it cascades everything and is irreversible.

---

## F3 Tasks

### Why it matters

The Task is the atom the whole product exists to move. It is also where our scope discipline is most visible: the field set is closed, there are no custom fields, no subtasks and no attachments. Every persona touches tasks, and two of our five success metrics (M2 TTFT, M5 task-move error rate) are measured on task endpoints. Because Task is the only entity besides Comment with soft delete, it is also the only place where "delete" is recoverable — which changes what the UI can safely offer.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F3-US-01 | member | to create a task with just a title and have everything else defaulted | capturing work costs one keystroke and never blocks on required fields | P0 |
| F3-US-02 | member | to open a task in a slide-over panel and edit title, description, `status_id`, `priority`, `due_date` | I can update state without losing my place in the list | P0 |
| F3-US-03 | admin | to assign one or more people via `assignee_ids` | everyone knows who owns the work | P0 |
| F3-US-04 | member | to set `priority` to one of `urgent`, `high`, `normal`, `low`, `none` | the team can sort by real importance instead of guessing | P0 |
| F3-US-05 | member | to soft-delete a task and have it disappear from every view | mistakes are correctable and history is not destroyed | P0 |
| F3-US-06 | member | to watch a task I do not own | I get realtime updates on work that affects me | P1 |
| F3-US-07 | guest | to edit a task where I appear in `assignee_ids`, and only such tasks | I can report my own progress without being able to damage the workspace | P0 |

### Acceptance criteria

```gherkin
Scenario F3-AC-01: Minimal task creation applies all defaults
  Given a member in a List L whose effective status set has a Status D with is_default = true
  When the member sends POST /api/v1/lists/{L}/tasks/ with {"title":"Fix login redirect"}
  Then the response is HTTP 201 with a bare JSON object containing exactly the task field set:
       id, list_id, title, description_html, description_json, status_id, priority, position,
       due_date, start_date, time_estimate_minutes, assignee_ids, watcher_ids, tag_ids,
       comment_count, created_by_id, updated_by_id, created_at, updated_at, deleted_at, archived
   And "status_id" equals D
   And "priority" equals "none"
   And "archived" is false, "deleted_at" is null, "comment_count" is 0
   And "assignee_ids", "watcher_ids", "tag_ids" are empty arrays
   And "position" places the task last in the (list_id, status_id) scope
   And "created_by_id" and "updated_by_id" equal the caller's user_id
   And created_at/updated_at are ISO-8601 UTC ending in "Z"

Scenario F3-AC-02: A status from a different status set is rejected
  Given List L whose effective status set is SS1
   And a Status X belonging to a different status set SS2
  When a member sends PATCH /api/v1/tasks/{id}/ with {"status_id":"{X}"}
  Then the response is HTTP 400
   And error.code = "invalid_status_for_list"
   And the task's status_id is unchanged

Scenario F3-AC-03: Priority sets the sortable shadow column
  Given a task with priority "none"
  When a member sends PATCH /api/v1/tasks/{id}/ with {"priority":"urgent"}
  Then the response is HTTP 200 with "priority":"urgent"
   And the stored priority_order becomes 1
   And GET /api/v1/lists/{L}/tasks/?ordering=priority_order returns this task before
       any task with priority "high" (2), "normal" (3), "low" (4) or "none" (5)
  When the member sends PATCH /api/v1/tasks/{id}/ with {"priority":"critical"}
  Then the response is HTTP 400 with error.code = "validation_error"
   And details contains the key "priority"

Scenario F3-AC-04: Soft delete hides the task everywhere by default
  Given a live task T in List L
  When a member sends DELETE /api/v1/tasks/{T}/
  Then the response is HTTP 204 with an empty body
   And the Task row still exists with deleted_at set to the current UTC timestamp
   And is_deleted is derived as true
   And GET /api/v1/lists/{L}/tasks/ does not include T
   And GET /api/v1/tasks/{T}/ returns HTTP 404 with error.code = "not_found"
   And a "task.deleted" event is broadcast to group list.{L}
  When an admin sends GET /api/v1/lists/{L}/tasks/?include_deleted=true
  Then the response is HTTP 200 and includes T
  When a member sends GET /api/v1/lists/{L}/tasks/?include_deleted=true
  Then the response is HTTP 403 with error.code = "permission_denied"

Scenario F3-AC-05: Guest may edit only tasks where they are an assignee
  Given a user "carlos" with WorkspaceMember.role = "guest"
   And task T1 where carlos is present in assignee_ids
   And task T2 where carlos is not in assignee_ids
  When carlos sends PATCH /api/v1/tasks/{T1}/ with {"status_id":"<valid status in the list's set>"}
  Then the response is HTTP 200 and the change is persisted
  When carlos sends PATCH /api/v1/tasks/{T2}/ with {"title":"anything"}
  Then the response is HTTP 403 with error.code = "permission_denied"
  When carlos sends POST /api/v1/lists/{L}/tasks/ with {"title":"New"}
  Then the response is HTTP 403 with error.code = "permission_denied"
  When carlos sends DELETE /api/v1/tasks/{T1}/
  Then the response is HTTP 403 with error.code = "permission_denied"

Scenario F3-AC-06: Watching a task is self-service and idempotent
  Given a member who is not in watcher_ids of task T
  When the member sends POST /api/v1/tasks/{T}/watch/
  Then the response is HTTP 201 (or 200 on repeat) and the caller's user_id appears exactly once in watcher_ids
  When the member sends POST /api/v1/tasks/{T}/watch/ again
  Then watcher_ids still contains the caller's user_id exactly once
  When the member sends DELETE /api/v1/tasks/{T}/watch/
  Then the response is HTTP 204 and the caller's user_id is absent from watcher_ids

Scenario F3-AC-07: Client-generated id enables optimistic create
  Given the client generates uuid "3f2a...c91"
  When the client sends POST /api/v1/lists/{L}/tasks/ with {"id":"3f2a...c91","title":"Draft brief"}
  Then the response is HTTP 201 and the returned "id" equals "3f2a...c91"
  When the client retries the identical request (network retry)
  Then the response is HTTP 409 with error.code = "conflict"
   And no duplicate Task row is created
```

### Rules & edge cases

- The Task field set is exactly: `id`, `list_id`, `title`, `description_html`, `description_json`, `status_id`, `priority`, `position`, `due_date`, `start_date`, `time_estimate_minutes`, `assignee_ids`, `watcher_ids`, `tag_ids`, `comment_count`, `created_by_id`, `updated_by_id`, `created_at`, `updated_at`, `deleted_at`, `archived`. No other field may appear in a task payload.
- `priority` is a CharField with choices `"urgent" | "high" | "normal" | "low" | "none"`, default `"none"`. The database additionally stores `priority_order` (SmallInteger: urgent=1, high=2, normal=3, low=4, none=5) purely for sorting; clients never set `priority_order` directly.
- `title` is required, trimmed, non-empty, max 255 characters. Everything else is optional at creation.
- Description is dual-stored: `description_json` is the canonical editor document, `description_html` is the rendered form used for read-only display and search snippets. Both are updated together; sending only one returns 400 `validation_error`.
- `status_id` must reference a Status inside the List's **effective** status set (own StatusSet if present, else the Space's). Otherwise 400 `invalid_status_for_list`.
- `Task.status` is `PROTECT`: a Status that is still referenced by a live task cannot be deleted (see F4).
- Soft delete only: `DELETE /api/v1/tasks/{id}/` sets `deleted_at` and returns 204. A deleted task is excluded from every collection unless `?include_deleted=true`, which is **admin-only** (`owner` and `admin`); other roles receive 403 `permission_denied`.
- There is no restore endpoint in MVP; `deleted_at` preserves data for support recovery only (OQ-5).
- `archived` (bool) is separate from deletion. `?archived=` defaults to `false`, so archived tasks are hidden unless explicitly requested. Archiving does not change `position` or `status_id`.
- Moving a task between Lists is done via `PATCH /api/v1/tasks/{id}/move/` (F5), which must also supply a valid `status_id` for the destination list's status set — otherwise 400 `invalid_status_for_list`.
- `assignee_ids` may contain zero or more workspace members; a user id that is not a member of the task's workspace returns 400 `validation_error`. Removing a user from the workspace removes them from `assignee_ids` (F9).
- `watcher_ids` is self-service via `POST`/`DELETE /api/v1/tasks/{id}/watch/`; it is not settable through `PATCH /api/v1/tasks/{id}/`.
- `tag_ids` reference `Tag` rows scoped to the workspace; a tag from another workspace returns 400 `validation_error`.
- `comment_count` is denormalized and maintained by the server on comment create/delete; it is read-only for clients.
- `updated_by_id` is set from the authenticated caller on every successful write. `created_by_id` is immutable.
- `due_date` and `start_date` are nullable datetimes stored UTC. `start_date` after `due_date` is allowed (no validation) but the UI surfaces a warning. Dates render in the user's `timezone` (§7.4).
- `time_estimate_minutes` is stored and displayed but never tracked against — time tracking is out of scope.
- Every successful task mutation emits the matching realtime event (`task.created`, `task.updated`, `task.moved`, `task.deleted`) to group `list.<list_id>` from the service layer, never from the view.

---

## F4 Custom status sets

### Why it matters

Typed, container-owned statuses are the second distinctive property we are copying (§4b) and the one that makes Clickish usable by an engineering team and a marketing team in the same workspace without either learning the other's vocabulary. The `type` field (`open`, `active`, `closed`) is the machine-readable layer underneath the human names — it is what makes `?status_type=closed` work across Lists whose statuses share no words. It is also the riskiest data-integrity area in the MVP: `Task.status` is `PROTECT`, so status deletion and status-set replacement must be explicitly mapped rather than silently coerced.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F4-US-01 | admin | every new Space to come with a working default status set | a team can start working before anyone configures anything | P0 |
| F4-US-02 | admin | to edit my Space's statuses — name, `color`, `type`, `order`, `is_default` | the whole Space speaks my organization's language | P0 |
| F4-US-03 | admin | to override the status set on a single List | one team's odd workflow does not force a change on everyone else | P0 |
| F4-US-04 | admin | to be forced to map old statuses to new ones when I replace a List's status set | no task is ever left pointing at a status that no longer exists | P0 |
| F4-US-05 | member | to see status color and type on every task chip in both views | I can read board state at a glance without reading every label | P1 |

### Acceptance criteria

```gherkin
Scenario F4-AC-01: A Space always has a status set, auto-created
  Given an admin creates a Space via POST /api/v1/workspaces/{W}/spaces/ with {"name":"Engineering"}
  When the admin sends GET /api/v1/spaces/{S}/status-set/
  Then the response is HTTP 200 with a StatusSet whose space FK is {S} and whose list FK is null
   And it contains Status rows each having name, color (hex), type in {open, active, closed}, order (int)
   And exactly one Status has is_default = true
   And at least one Status has type = "closed"

Scenario F4-AC-02: A status set must keep exactly one default and at least one closed status
  Given a StatusSet with statuses Backlog(open, default), Doing(active), Done(closed)
  When an admin sends PUT /api/v1/spaces/{S}/status-set/ with a payload where no status has is_default = true
  Then the response is HTTP 400 with error.code = "validation_error"
   And details references "is_default"
  When the admin sends a payload where no status has type = "closed"
  Then the response is HTTP 400 with error.code = "validation_error"
   And details references "type"
  When the admin sends a payload with two statuses having is_default = true
  Then the response is HTTP 400 with error.code = "validation_error"

Scenario F4-AC-03: A List-level status set overrides the Space's
  Given List L in Space S, where L has no own StatusSet
   And GET /api/v1/lists/{L}/status-set/ currently returns the Space's set
  When an admin sends PUT /api/v1/lists/{L}/status-set/ with a new set
       {"statuses":[...], "status_mapping":{"<old_status_id>":"<new_status_id>", ...}}
  Then the response is HTTP 200
   And a StatusSet is created with list FK = {L} and space FK = null (CHECK constraint: exactly one is set)
   And every Task in L is re-pointed to its mapped new status
   And GET /api/v1/lists/{L}/status-set/ now returns the List's own set
   And other Lists in Space S are unaffected

Scenario F4-AC-04: Replacing a status set without a complete mapping is refused
  Given List L has its own StatusSet with statuses used by 7 tasks
  When an admin sends PUT /api/v1/lists/{L}/status-set/ with a status_mapping that omits one in-use old status
  Then the response is HTTP 400 with error.code = "validation_error"
   And details identifies the unmapped old status id
   And no Status rows are created, changed or deleted (the whole operation is one transaction)

Scenario F4-AC-05: A status still in use cannot be deleted
  Given Status X is referenced by at least one live Task (deleted_at IS NULL)
  When an admin sends PUT /api/v1/spaces/{S}/status-set/ with a payload that omits X and provides no mapping for X
  Then the response is HTTP 409 with error.code = "conflict"
   And the message explains that Task.status is PROTECT and X is still referenced
   And X still exists
  When the admin re-sends the same payload with status_mapping {"{X}":"{Y}"} where Y is in the new set
  Then the response is HTTP 200, all tasks previously on X now have status_id = Y
   And a "task.updated" event is emitted for each re-pointed task to its list group

Scenario F4-AC-06: A member cannot manage statuses
  Given a user with WorkspaceMember.role = "member"
  When the user sends PUT /api/v1/spaces/{S}/status-set/ with any valid payload
  Then the response is HTTP 403 with error.code = "permission_denied"
  When the user sends GET /api/v1/spaces/{S}/status-set/
  Then the response is HTTP 200 (reading statuses is allowed for every role including guest)
```

### Rules & edge cases

- A `StatusSet` belongs to **either** a Space (`space` FK set, `list` NULL) **or** a TaskList (`list` FK set, `space` NULL). A database CHECK constraint enforces that exactly one is set. There is no workspace-level or global status set in MVP.
- A List's **effective** status set = its own StatusSet if one exists, otherwise its Space's StatusSet. A Space always has one (auto-created on Space creation), so the effective set is never null.
- `Status` fields: `name`, `color` (hex), `type` ∈ {`open`, `active`, `closed`}, `order` (integer), `is_default` (bool), `status_set` FK. Statuses are ordered by the integer `order`, **not** by the fractional `position` scheme used for Tasks/Lists/Folders/Spaces.
- Invariants per status set, enforced on every write: exactly one `is_default = true`; at least one status of `type = "closed"`; at least one status total; `order` values unique within the set.
- `is_default` determines the status assigned to a task created without an explicit `status_id`.
- Default colors when unspecified follow the status-type defaults: `open` `#87909E`, `active` `#4194F6`, `closed` `#6BC950`.
- `PUT /api/v1/lists/{id}/status-set/` creates or replaces the List's own set and **requires** `status_mapping` `{old_status_id: new_status_id}` covering every old status currently referenced by any task in that List (including archived tasks; soft-deleted tasks are mapped too so restoration stays valid).
- `DELETE /api/v1/lists/{id}/status-set/` removes the List's override so the List falls back to its Space's set. It requires the same complete `status_mapping` semantics from the List's statuses to the Space's statuses; without it the request returns 400 `validation_error`.
- **What happens when the status a task uses is removed:** it cannot be removed while referenced (`PROTECT` → 409 `conflict`) unless the same request supplies a mapping, in which case tasks are re-pointed inside one transaction and a `task.updated` event is emitted per affected task.
- Changing a Space's status set affects every List in that Space that has **no** override; Lists with their own set are untouched.
- Re-pointing tasks preserves `position`. Because the position scope is `(list_id, status_id)`, tasks merged from two old statuses into one new status may end up with colliding-looking ordering; the server resolves ties with `ORDER BY position ASC, created_at ASC` and does not renumber.
- Status names are non-empty, max 60 characters, and must be unique (case-insensitive) within a set; duplicates return 400 `validation_error`.
- Managing status sets is `owner`/`admin` only. `member` and `guest` can read status sets but cannot write them.
- Deleting a Space cascades its StatusSet; deleting a List cascades its own StatusSet if it has one.

---

## F5 Views (List & Board with drag & drop)

### Why it matters

This is the third distinctive property (§4c): List and Board are two renderings of one dataset, switchable instantly, with view state that belongs to the user rather than to the List. It is also where the highest-risk engineering decision lives — the fractional `position` index — and where our M5 metric (task-move error rate < 0.5%) is measured. If drag-and-drop is janky or lossy under two concurrent users, the product feels broken regardless of how correct everything else is.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F5-US-01 | member | to switch a List between List view and Board view instantly | I choose the shape that fits the moment without duplicating data | P0 |
| F5-US-02 | admin | to drag a task between status columns on the Board | changing state is one gesture, not a form | P0 |
| F5-US-03 | member | to reorder tasks within a column or list by dragging | the top of the column is genuinely the next thing to do | P0 |
| F5-US-04 | member | my view choice, filters, sort and collapsed columns to be remembered for me on that List | my colleague switching to Board does not change my screen | P0 |
| F5-US-05 | member | a keyboard equivalent for every drag operation | I can reorder without a mouse and the app is accessible | P1 |
| F5-US-06 | member | the board to show a per-column task count and to load long columns incrementally | a column with 400 tasks does not freeze the page | P1 |

### Acceptance criteria

```gherkin
Scenario F5-AC-01: One dataset, two shapes
  Given List L with 20 tasks spread across statuses Backlog, Doing, Done
  When the client sends GET /api/v1/lists/{L}/tasks/
  Then the response is HTTP 200 with the collection envelope
       {"count","page","page_size","total_pages","next","previous","results"}
   And results are ordered by status.order ASC, position ASC   # ungrouped list view
  When the client sends GET /api/v1/lists/{L}/tasks/?group_by=status
  Then the response is HTTP 200 with a grouped payload keyed by status
   And each group lists its tasks ordered by position ASC, created_at ASC
   And the union of all groups equals the ungrouped result set for the same filters

Scenario F5-AC-02: Dragging a card to another column changes status and position atomically
  Given task T is in List L with status_id = Backlog at position "n"
   And column Doing contains tasks at positions "g" and "u"
  When the client sends PATCH /api/v1/tasks/{T}/move/
       with {"list_id":"{L}","status_id":"<Doing>","after_id":"<task at g>","before_id":"<task at u>"}
       and header X-Client-Id: <tab uuid>
  Then the response is HTTP 200 with the task's new "status_id" and a server-computed "position"
   And the new position sorts strictly between "g" and "u" under plain string comparison
   And a "task.moved" event is broadcast to group list.{L}
   And that event's actor.client_id equals the X-Client-Id sent, so the originating tab suppresses its own echo
   And the client never sends a raw position value

Scenario F5-AC-03: Moving to a status outside the list's effective set is refused
  Given task T in List L whose effective status set is SS1
  When the client sends PATCH /api/v1/tasks/{T}/move/ with {"status_id":"<a status in SS2>"}
  Then the response is HTTP 400 with error.code = "invalid_status_for_list"
   And the task's status_id and position are unchanged
   And no "task.moved" event is broadcast

Scenario F5-AC-04: Position key growth triggers a rebalance
  Given repeated insertions between two adjacent tasks have grown the generated key beyond 48 characters
  When a client sends PATCH /api/v1/tasks/{T}/move/ that would generate a key longer than 48 chars
  Then the server, inside a single transaction, re-numbers the whole (list_id, status_id) scope
       with evenly spaced 2-character keys
   And the response is HTTP 200 with the moved task's new "position"
   And the server emits a single "task.moved" event for the moved task with "rebalanced": true
   And every subscribed client, on seeing rebalanced = true, refetches the list rather than patching locally

Scenario F5-AC-05: Concurrent moves do not lose a task
  Given user A and user B both view List L over WebSocket
  When A moves task T1 above T2 and, within the same second, B moves T2 above T1
  Then both PATCH /api/v1/tasks/{id}/move/ calls return HTTP 200
   And both clients converge to the same order after applying both "task.moved" events
   And if the server cannot compute a strictly-between key for a stale before_id/after_id pair
       it returns HTTP 409 with error.code = "position_conflict"
   And the client retries the move once against refreshed neighbours

Scenario F5-AC-06: A guest cannot drag a task that is not theirs
  Given a user with WorkspaceMember.role = "guest" viewing List L in Board view
   And task T where the guest is NOT in assignee_ids
  When the guest sends PATCH /api/v1/tasks/{T}/move/ with any valid body
  Then the response is HTTP 403 with error.code = "permission_denied"
   And the card animates back to its original column and position
   And no "task.moved" event is broadcast

Scenario F5-AC-07: View state is per-user-per-list
  Given user A last used Board view on List L with filter assignee=me and column "Done" collapsed
   And user B last used List view on the same List L with no filters
  When A and B both open List L at the same time
  Then A sees Board view, filtered to assignee=me, with "Done" collapsed
   And B sees List view, unfiltered, with all statuses expanded
   And neither user's choice changes the other's screen
   And no request either user makes writes shared view configuration
```

### Rules & edge cases

- `position` is `CharField(max_length=64, db_index=True)` holding a lexicographic fractional index over the base-62 alphabet `0-9A-Za-z` (ASCII-order preserving), compared with plain string `<`. `midstring(prev, next)` produces a key strictly between two neighbours; `midstring(None, first)` and `midstring(last, None)` handle the ends. The first item in an empty scope is `"n"`.
- The client **never** sends a raw `position`. It sends `before_id` and/or `after_id` to `PATCH /api/v1/tasks/{id}/move/`; the server computes and returns the new `position`.
- Ordering scope for a Task is `(list_id, status_id)`. Changing either scope key is a move, not an update.
- Sort inside a status column: `ORDER BY position ASC, created_at ASC`. Ungrouped List view: `ORDER BY status__order ASC, position ASC`.
- **Rebalance rule:** if the generated key would exceed 48 characters for the target scope, the server re-numbers the entire scope with evenly spaced 2-character keys inside a transaction, then emits a single `task.moved` for the moved task with `rebalanced: true`. Clients treat `rebalanced: true` as "your local ordering is stale — refetch this list." There is no separate `list.rebalanced` event (see §8, D-7).
- Dropping into an empty column: the client sends neither `before_id` nor `after_id`; the server assigns `"n"`.
- Dropping at the top or bottom: exactly one of `before_id`/`after_id` is sent.
- A stale neighbour id (the neighbour was moved or deleted between render and drop) returns 409 `position_conflict`; the client refetches neighbours and retries once, then surfaces a non-blocking toast.
- Optimistic UI: the client applies the move locally, then reconciles with the server response. On 4xx the card animates back to its pre-drag position and an error toast names the reason.
- Cross-list drag (moving a task from List A to List B) is supported through `PATCH /api/v1/tasks/{id}/move/` with a new `list_id`; the body must also carry a `status_id` valid for the destination list's effective status set, otherwise 400 `invalid_status_for_list`.
- Board columns are the statuses of the List's effective status set, ordered by `Status.order` ASC. A status with no tasks still renders as an empty column (it is a valid drop target).
- Board columns paginate independently at `page_size` 50 (max 200) with "load more"; a column header shows the total `count` for that status from the grouped payload.
- Archived and soft-deleted tasks never render in either view (`?archived=false` and `deleted_at IS NULL` are the defaults).
- **View state (view type, filters, sort, collapsed columns) is stored client-side per user per list** — there is no server model for it in the 15-model MVP data model. It is keyed by `(user_id, list_id)` in browser storage and mirrored into Zustand for the session. It is therefore not portable across devices in MVP (see OQ-3).
- Row height in List view is 36 px; Board card min-height is 68 px; the task slide-over panel is 720 px wide from the right. Switching views must not unmount the task panel if one is open.
- Keyboard equivalent (F5-US-05): with a row/card focused, `Space` picks up, arrow keys move within and across columns, `Space` drops, `Escape` cancels — issuing the identical `PATCH /api/v1/tasks/{id}/move/` call with computed `before_id`/`after_id`.

---

## F6 Comments

### Why it matters

Comments are the only conversation surface in the MVP, which makes them the entire collaboration story for Carlos (the guest) and the main reason a task is a task rather than a row in a spreadsheet. They are also the second soft-deleted entity, and the source of the denormalized `comment_count` on Task — so the write path has to keep two things consistent. Because `comment.created` is one of only two content events broadcast over WebSocket, comments are also the most visible proof that the app is live.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F6-US-01 | guest | to add a comment to any task I can read | I can give feedback in context instead of by email | P0 |
| F6-US-02 | member | to see new comments appear live while the task panel is open | I do not have to refresh to know I was answered | P0 |
| F6-US-03 | member | to edit and delete my own comment | I can fix a typo or retract a mistake without asking an admin | P0 |
| F6-US-04 | admin | to delete anyone's comment | I can remove content that should not be in the workspace | P0 |
| F6-US-05 | member | to see an accurate comment count on the task in both views | I can tell which tasks have discussion without opening them | P1 |

### Acceptance criteria

```gherkin
Scenario F6-AC-01: Creating a comment increments the denormalized count and broadcasts
  Given task T in List L with comment_count = 2
  When a member sends POST /api/v1/tasks/{T}/comments/ with {"body_html":"...","body_json":{...}}
       and header X-Client-Id: <tab uuid>
  Then the response is HTTP 201 with a bare JSON object containing id, task_id, author_id,
       created_at, updated_at, deleted_at
   And GET /api/v1/tasks/{T}/ now returns comment_count = 3
   And a "comment.created" event is broadcast to group list.{L}
   And the event frame contains type, event_id, ts, list_id, actor and data
   And actor.client_id equals the X-Client-Id header so the author's own tab suppresses the echo

Scenario F6-AC-02: A guest may comment but not manage other people's comments
  Given a user with WorkspaceMember.role = "guest" who can read task T
  When the guest sends POST /api/v1/tasks/{T}/comments/ with a valid body
  Then the response is HTTP 201
  When the guest sends PATCH /api/v1/comments/{own_comment_id}/ with {"body_html":"edited"}
  Then the response is HTTP 200
  When the guest sends DELETE /api/v1/comments/{someone_elses_comment_id}/
  Then the response is HTTP 403 with error.code = "permission_denied"

Scenario F6-AC-03: Own-comment rule applies to every role; admins override on delete only
  Given a comment C authored by member "dan"
  When another member "sam" sends PATCH /api/v1/comments/{C}/
  Then the response is HTTP 403 with error.code = "permission_denied"
  When an admin sends PATCH /api/v1/comments/{C}/
  Then the response is HTTP 403 with error.code = "permission_denied"   # editing is author-only, always
  When an admin sends DELETE /api/v1/comments/{C}/
  Then the response is HTTP 204 and C is soft-deleted (deleted_at set)
   And the task's comment_count is decremented by 1

Scenario F6-AC-04: Deleting a comment is a soft delete
  Given comment C with deleted_at = null on task T with comment_count = 5
  When the author sends DELETE /api/v1/comments/{C}/
  Then the response is HTTP 204 with an empty body
   And the Comment row still exists with deleted_at set to a UTC timestamp
   And GET /api/v1/tasks/{T}/comments/ no longer includes C
   And GET /api/v1/tasks/{T}/ returns comment_count = 4

Scenario F6-AC-05: Empty and oversized comments are rejected
  Given a signed-in member on task T
  When the member sends POST /api/v1/tasks/{T}/comments/ with {"body_html":"","body_json":null}
  Then the response is HTTP 400 with error.code = "validation_error"
   And details contains "body_html" or "body_json"
   And comment_count is unchanged
  When the member sends a body exceeding the maximum length
  Then the response is HTTP 400 with error.code = "validation_error"

Scenario F6-AC-06: Comments on a task the caller cannot read are not enumerable
  Given user "carlos" is not a member of the workspace owning task T
  When carlos sends GET /api/v1/tasks/{T}/comments/
  Then the response is HTTP 404 with error.code = "not_found"
   And the body reveals nothing about T's existence
```

### Rules & edge cases

- Comments are **flat** in MVP: no threads, no replies-to, no reactions, no @mentions, no attachments. A comment belongs to exactly one Task.
- Body is dual-stored like task descriptions: `body_json` is canonical, `body_html` is rendered. Both are required on create; both are replaced together on edit.
- Comment and Task are the **only** soft-deleted entities (`deleted_at`, `is_deleted` derived). Deleting a Task cascades to its Comments; deleting a List/Folder/Space hard-deletes Comments through CASCADE.
- `comment_count` on Task is denormalized: incremented on create, decremented on soft delete, never editable by clients. It is recomputed by a management command if it drifts.
- Permission rules: **anyone who can read the task may comment**, including `guest`. **Everyone may edit and delete their OWN comment.** `admin` and `owner` may delete **any** comment. Nobody may edit someone else's comment — not even an owner.
- Editing sets `updated_at`; the UI shows an "edited" marker when `updated_at > created_at`.
- There is no `comment.updated` or `comment.deleted` WebSocket event in the MVP event vocabulary. Only `comment.created` is broadcast; edits and deletes are reconciled on the next fetch or on task panel re-open (see §8, D-9 and OQ-5).
- Comment list is paginated with the standard envelope, default `page_size` 50, ordered `created_at ASC` (oldest first, chat-like).
- A comment on a soft-deleted task is not readable (the task returns 404), but the rows are preserved.
- Comment bodies are sanitized server-side; only an allow-list of formatting tags survives, and any script/style/event-handler content is stripped before storage.
- Rapid repeat submissions are throttled; exceeding the limit returns HTTP 429 with `error.code = "throttled"`.

---

## F7 Realtime collaboration

### Why it matters

Realtime is the difference between a tracker and a shared workspace. Maya's standup only works if the board is live; Dan only trusts the tracker if his change is visible to others without a "did you refresh?" exchange; Carlos only feels included if his comment lands immediately. It is also one of our five gating metrics: M4 requires p95 broadcast latency under 300 ms. The two hardest requirements here are *echo suppression* (your own optimistic update must not be applied twice) and *consistency between REST and WebSocket* — events are emitted from the service layer, never from views, so every mutation path produces the same event exactly once.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F7-US-01 | member | task creates, updates, moves and deletes made by others to appear in my open List within a third of a second | I never act on stale state during a standup | P0 |
| F7-US-02 | member | my own optimistic change not to flicker or apply twice when the server echoes it back | the UI feels local even though it is multiplayer | P0 |
| F7-US-03 | admin | to see who else is currently viewing this List | I know whether to talk in the tool or in a call | P1 |
| F7-US-04 | member | the connection to recover automatically after sleep, a tunnel, or a deploy | I do not have to reload the page to become live again | P0 |
| F7-US-05 | guest | to receive live updates only for the lists I am permitted to read | I never see work I have no access to | P0 |

### Acceptance criteria

```gherkin
Scenario F7-AC-01: Connection handshake and group membership
  Given a valid access token
  When the client opens ws://<host>/ws/list/{list_id}/?token=<access>
  Then the server authenticates from the token query param and joins group "list.<list_id>"
   And the first server->client frame has type "connection.ack"
   And the client is also joined to its personal group "user.<user_id>"
  When the same client opens ws://<host>/ws/space/{space_id}/?token=<access>
  Then the server joins group "space.<space_id>" and sends "connection.ack"

Scenario F7-AC-02: Task mutation fans out to every subscriber with the standard frame
  Given users A and B are both subscribed to group list.{L}
  When A creates a task via POST /api/v1/lists/{L}/tasks/
  Then B receives a frame
       {"type":"task.created","event_id":"evt_...","ts":"2026-08-07T09:15:00Z",
        "list_id":"{L}","actor":{...},"data":{...the full task object...}}
   And the elapsed time from DB commit to the frame being written to B's socket is under 300 ms at p95
   And the same fan-out holds for task.updated, task.moved, task.deleted and comment.created

Scenario F7-AC-03: Echo suppression via X-Client-Id
  Given tab-1 of user A has client_id "c1" and tab-2 of user A has client_id "c2"
  When tab-1 sends PATCH /api/v1/tasks/{T}/ with header X-Client-Id: c1 and applies the change optimistically
  Then the broadcast frame contains actor.client_id = "c1"
   And tab-1 ignores the frame because actor.client_id equals its own client_id
   And tab-2 applies the frame because "c1" != "c2"
   And the task is never rendered in a doubled or flickering state in tab-1

Scenario F7-AC-04: Permission is enforced at subscribe time, not just at fetch time
  Given user "carlos" (role "guest") has no read access to List L2 in another Space
  When carlos opens ws://<host>/ws/list/{L2}/?token=<valid access>
  Then the server does not join group "list.{L2}"
   And the server emits a frame of type "error" and closes the socket
   And carlos never receives any task.* or comment.created event for L2

Scenario F7-AC-05: Presence join, sync and leave
  Given user A is subscribed to group list.{L}
  When user B subscribes to the same list
  Then A receives a "presence.join" frame identifying B
   And B receives a "presence.sync" frame enumerating everyone currently present, including A
  When B's socket closes (tab closed, network drop, or missed presence.ping window)
  Then A receives a "presence.leave" frame identifying B
   And B's avatar disappears from the presence stack in A's UI

Scenario F7-AC-06: Reconnect and resync after a disconnect
  Given a client was subscribed to list.{L} and the socket drops
  When the client reconnects with exponential backoff (1s, 2s, 4s, 8s, capped at 30s, with jitter)
  Then on "connection.ack" the client refetches GET /api/v1/lists/{L}/tasks/ to close the gap
   And any events missed while disconnected are recovered by that refetch, not replayed by the server
   And the UI shows a "reconnecting" indicator while disconnected and clears it on ack

Scenario F7-AC-07: A rebalance tells clients to refetch rather than patch
  Given a move triggers a scope-wide position rebalance (F5-AC-04)
  When subscribers receive the "task.moved" frame with "rebalanced": true
  Then each client discards its local ordering for that (list_id, status_id) scope
   And refetches GET /api/v1/lists/{L}/tasks/ before rendering
   And no client attempts to interpolate positions from the event payload
```

### Rules & edge cases

- WebSocket URLs: `ws://<host>/ws/list/{list_id}/?token=<access>` and `ws://<host>/ws/space/{space_id}/?token=<access>`. Authentication is by access token in the query parameter; there is no cookie-based socket auth.
- Group names: `list.<list_id>`, `space.<space_id>`, `user.<user_id>`.
- Server → client frame shape is fixed: `{"type", "event_id", "ts", "list_id", "actor", "data"}`. `ts` is ISO-8601 UTC with `Z`.
- Event types (closed set): `connection.ack`, `task.created`, `task.updated`, `task.moved`, `task.deleted`, `comment.created`, `presence.join`, `presence.leave`, `presence.sync`, `error`.
- Client → server messages (closed set): `presence.ping`, `presence.typing`, `subscribe`, `unsubscribe`.
- Echo suppression: every browser tab generates a `client_id` (uuid) and sends it on mutations via the `X-Client-Id` header. The server echoes it as `actor.client_id`. A client ignores any frame whose `actor.client_id` equals its own.
- `event_id` is unique per emitted event and is used by clients for idempotent application — receiving the same `event_id` twice (e.g. after a reconnect race) must be a no-op.
- Events are emitted from the service/serializer layer, never from views, so REST and WebSocket can never diverge. A mutation that fails validation or permission emits nothing.
- There is **no server-side event replay or backfill**. Recovery after disconnect is "reconnect, then refetch." The client must therefore treat a refetch as authoritative over any buffered events.
- Presence liveness is driven by `presence.typing`/`presence.ping` from the client; a client that misses its ping window is considered gone and a `presence.leave` is emitted. Typing indicators are ephemeral and never persisted.
- There is no server→client `presence.typing` event in the closed event set; typing is delivered as part of the presence mechanism only (see §8, D-10 / OQ-5).
- Comment edits and deletions do not broadcast (only `comment.created` exists). The task panel refetches comments on open and on window refocus.
- In development, Channels may fall back to the in-memory layer (no Redis). Multi-process fan-out is only guaranteed with `channels_redis`; the in-memory layer is single-process and must never be used in production.
- Backpressure: a socket that cannot keep up is closed rather than buffered indefinitely; the client's reconnect+refetch loop restores correctness.
- Every realtime payload is re-serialized through the same serializer as the REST response, so a `data` object is always shape-identical to what `GET` would return for that resource.

---

## F8 Search, filtering & sorting

### Why it matters

Hierarchy solves *where things live*; search and filters solve *where things are right now*. Dan's core loop is "show me my open tasks, most important first," which is a single filtered query. Maya's standup loop is "show me what is overdue in this Space." And because our status names are per-container, the typed `status_type` filter is the only way to ask a cross-List question like "what is still open." Filters also feed F5: the Board and List views are both just this query with different presentation.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F8-US-01 | member | to filter a List by `assignee=me` and `status_type=open` | I see only my live work with two clicks | P0 |
| F8-US-02 | admin | to filter by `priority`, `tag`, `due` and combine several filters at once | I can run planning and triage without exporting anything | P0 |
| F8-US-03 | member | to sort by `due_date`, `priority_order`, `created_at`, `updated_at` or `title`, ascending or descending | I can reshape the same data for the question I am asking | P0 |
| F8-US-04 | owner | to search across the entire workspace and get tasks, lists, folders and spaces back | I can find anything without remembering where it lives | P1 |
| F8-US-05 | member | results to be paginated with a stable envelope | large workspaces stay responsive and the UI can page predictably | P0 |

### Acceptance criteria

```gherkin
Scenario F8-AC-01: Combined filters are ANDed, repeated params are ORed
  Given List L contains tasks with mixed assignees, priorities and statuses
  When the client sends
       GET /api/v1/lists/{L}/tasks/?assignee=me&priority=urgent&priority=high&status_type=open
  Then the response is HTTP 200 with the collection envelope
   And every returned task has the caller in assignee_ids
   And every returned task has priority in {"urgent","high"}
   And every returned task's status has type "open"
   And archived tasks are excluded because ?archived defaults to false
   And soft-deleted tasks are excluded because deleted_at IS NULL is the default

Scenario F8-AC-02: Unassigned and overdue filters
  Given tasks with and without assignees and with due_date values in the past and future
  When the client sends GET /api/v1/lists/{L}/tasks/?assignee=none
  Then every returned task has an empty assignee_ids array
  When the client sends GET /api/v1/lists/{L}/tasks/?due=overdue
  Then every returned task has a non-null due_date strictly earlier than now (UTC)
   And "today" and "this_week" are evaluated against the caller's timezone, not the server's
  When the client sends GET /api/v1/lists/{L}/tasks/?due=none
  Then every returned task has due_date = null

Scenario F8-AC-03: Ordering allow-list is enforced
  Given List L with tasks
  When the client sends GET /api/v1/lists/{L}/tasks/?ordering=-due_date
  Then the response is HTTP 200 ordered by due_date descending
  When the client sends GET /api/v1/lists/{L}/tasks/?ordering=priority_order
  Then tasks are ordered urgent(1), high(2), normal(3), low(4), none(5)
  When the client sends GET /api/v1/lists/{L}/tasks/?ordering=secret_field
  Then the response is HTTP 400 with error.code = "validation_error"
   And details references "ordering"
  When no ordering param is sent
  Then the default ordering is "position"

Scenario F8-AC-04: Pagination envelope and limits
  Given a List with 130 live tasks
  When the client sends GET /api/v1/lists/{L}/tasks/?page=2&page_size=50
  Then the response is HTTP 200 with
       {"count":130,"page":2,"page_size":50,"total_pages":3,"next":"<url>","previous":"<url>","results":[...]}
   And results contains 50 items
  When the client sends ?page_size=500
  Then the response is HTTP 400 with error.code = "validation_error"    # max page_size is 200
  When the client sends ?page=99
  Then the response is HTTP 200 with an empty results array and count 130

Scenario F8-AC-05: Cross-list and mixed-entity search respect permissions
  Given user "carlos" (role "guest") can read Space S1 but not Space S2
  When carlos sends GET /api/v1/workspaces/{W}/tasks/?q=invoice
  Then the response is HTTP 200 and contains only tasks in lists carlos may read
   And no task from Space S2 appears
  When carlos sends GET /api/v1/workspaces/{W}/search/?q=invoice
  Then the response is HTTP 200 with a mixed payload of tasks, lists, folders and spaces
   And every item in it is readable by carlos
  When carlos sends GET /api/v1/workspaces/{W2}/search/?q=invoice for a workspace he does not belong to
  Then the response is HTTP 404 with error.code = "not_found"

Scenario F8-AC-06: include_deleted is admin-only
  Given a member and an admin in workspace W
  When the admin sends GET /api/v1/workspaces/{W}/tasks/?include_deleted=true
  Then the response is HTTP 200 and includes tasks whose deleted_at is not null
  When the member sends the same request
  Then the response is HTTP 403 with error.code = "permission_denied"
```

### Rules & edge cases

- Task filter vocabulary (exact): `status` (status id, repeatable), `status_type` (`open`|`active`|`closed`), `assignee` (user id, repeatable, or `me`, or `none`), `priority` (repeatable), `tag` (tag id, repeatable), `due_before`, `due_after`, `due` (`overdue`|`today`|`this_week`|`none`), `created_by`, `watcher`, `q` (text), `archived` (`true`|`false`, default `false`), `include_deleted` (admin only).
- Semantics: different filter keys are combined with AND; repeated values of the same key are combined with OR.
- `ordering` allow-list (exact): `position`, `-position`, `due_date`, `-due_date`, `priority_order`, `-priority_order`, `created_at`, `-created_at`, `updated_at`, `-updated_at`, `title`, `-title`. Default is `position`. Anything else is 400 `validation_error`.
- Pagination: `?page=1&page_size=50`, default 50, maximum 200. Over-max returns 400 `validation_error`. Every collection uses the same envelope.
- `q` searches task `title` and the text extracted from `description_html`; matching is case-insensitive substring/full-text depending on backend (SQLite dev vs PostgreSQL prod) — results must be equivalent for the acceptance tests, ranking may differ.
- `due=today` and `due=this_week` are computed in the **caller's** `timezone` (F1), then converted to a UTC range for the query. `due=overdue` compares against `now()` UTC and excludes tasks whose status type is `closed`.
- `assignee=me` resolves to the authenticated `user_id` from the token claims. `assignee=none` matches tasks with an empty `assignee_ids`.
- `?group_by=status` on the list-tasks endpoint returns the grouped payload for Board view; filters and ordering apply identically within each group.
- Permission scoping is applied before pagination, so `count` never reveals the existence of records the caller cannot read.
- `GET /api/v1/workspaces/{id}/tasks/` is the cross-list task query (same filter/ordering vocabulary, workspace-wide). `GET /api/v1/workspaces/{id}/search/` is the mixed-entity search returning tasks, lists, folders and spaces.
- Search never returns soft-deleted tasks or comments, and never returns archived tasks unless `?archived=true`.
- An empty `q` on the search endpoint returns 400 `validation_error`; `q` shorter than 2 characters returns an empty result set rather than an error.
- Search results are not realtime — a `task.created` event does not retroactively insert a row into an open search result page; the client refetches on demand.
- Filter state is part of per-user-per-list view state (F5) and is never shared or persisted server-side in MVP.

---

## F9 Members, roles & invitations

### Why it matters

F9 is where Priya's whole job lives, and it is the enforcement point for every other feature area: the `WorkspaceMember.role` value read here decides every 200 vs 403 in the product. It is also the only place where the MVP has a genuine irreversibility risk — removing the last `owner` would strand a workspace — so the invariants below are non-negotiable. Getting the `guest` seat right is what makes Clickish safe to open to clients, which is a real differentiator against tools where the cheapest external option is a screenshot.

### User stories

| ID | As a &lt;role&gt; | I want &lt;x&gt; | So that &lt;y&gt; | Priority |
| --- | --- | --- | --- | --- |
| F9-US-01 | owner | to invite people by email with an explicit role | access is correct on day one instead of being fixed later | P0 |
| F9-US-02 | invited person | to accept an invitation with a token, registering if I am new | joining takes one click from my inbox | P0 |
| F9-US-03 | admin | to see the member list with roles and change a member's role | I can promote and demote without asking the owner | P0 |
| F9-US-04 | owner | to remove a member and to transfer ownership | offboarding and handover are self-service | P0 |
| F9-US-05 | member | to leave a workspace I no longer work in | I control my own membership | P1 |
| F9-US-06 | owner | to invite an external collaborator as `guest` with read-mostly access | clients can follow progress without risking the workspace | P0 |

### Acceptance criteria

```gherkin
Scenario F9-AC-01: Creating an invitation with an explicit role
  Given an admin in workspace W
  When the admin sends POST /api/v1/workspaces/{W}/invitations/
       with {"email":"carlos@client.com","role":"guest"}
  Then the response is HTTP 201 with a bare JSON object containing id, email, role, created_at
   And the response does NOT expose the raw invitation token to the inviter's response body
   And an invitation email is sent to carlos@client.com containing the token link
   And GET /api/v1/workspaces/{W}/invitations/ lists the pending invitation

Scenario F9-AC-02: Duplicate email invite does not create a second invitation
  Given a pending invitation already exists for "carlos@client.com" in workspace W
  When an admin sends POST /api/v1/workspaces/{W}/invitations/ with the same email
  Then the response is HTTP 409 with error.code = "conflict"
   And exactly one pending Invitation row exists for that email and workspace
   And the admin is offered POST /api/v1/invitations/{id}/resend/ instead
  Given carlos is ALREADY a WorkspaceMember of W
  When an admin invites carlos@client.com again
  Then the response is HTTP 409 with error.code = "conflict"
   And no Invitation row is created

Scenario F9-AC-03: Accepting an invitation creates the membership with the invited role
  Given a pending invitation for "carlos@client.com" with role "guest" and token TK
  When an anonymous visitor sends GET /api/v1/invitations/lookup/?token=TK
  Then the response is HTTP 200 with the workspace name, the invited email and the role,
       and no other workspace data
  When carlos sends POST /api/v1/invitations/accept/ with {"token":"TK"} while authenticated
  Then the response is HTTP 200
   And a WorkspaceMember row exists with role = "guest"
   And the Invitation is marked accepted and can no longer be accepted
  When carlos replays POST /api/v1/invitations/accept/ with the same token
  Then the response is HTTP 409 with error.code = "conflict"
  When anyone sends POST /api/v1/invitations/accept/ with an unknown or expired token
  Then the response is HTTP 404 with error.code = "not_found"

Scenario F9-AC-04: Role change rules — admins cannot touch owners
  Given user P has role "owner" and user A has role "admin" in workspace W
  When A sends PATCH /api/v1/workspaces/{W}/members/{P}/ with {"role":"member"}
  Then the response is HTTP 403 with error.code = "permission_denied"
  When A sends PATCH /api/v1/workspaces/{W}/members/{someone}/ with {"role":"owner"}
  Then the response is HTTP 403 with error.code = "permission_denied"    # only an owner grants owner
  When A sends PATCH /api/v1/workspaces/{W}/members/{a member}/ with {"role":"guest"}
  Then the response is HTTP 200 and the member's role becomes "guest"
  When P (owner) sends PATCH /api/v1/workspaces/{W}/members/{A}/ with {"role":"owner"}
  Then the response is HTTP 200 and A becomes an owner

Scenario F9-AC-05: The last owner cannot leave or be demoted
  Given workspace W has exactly one member with role "owner", user P
  When P sends POST /api/v1/workspaces/{W}/members/leave/
  Then the response is HTTP 409 with error.code = "conflict"
   And the message states that the last owner must transfer ownership or delete the workspace
   And P is still a member with role "owner"
  When P sends PATCH /api/v1/workspaces/{W}/members/{P}/ with {"role":"admin"}
  Then the response is HTTP 409 with error.code = "conflict"
  When P first promotes user A to "owner" and then leaves
  Then the response is HTTP 204 and W still has at least one owner

Scenario F9-AC-06: Removing a member detaches their work without destroying it
  Given member "dan" is assigned to 14 tasks, watches 6 tasks and authored 30 comments in workspace W
  When an admin sends DELETE /api/v1/workspaces/{W}/members/{dan}/
  Then the response is HTTP 204 with an empty body
   And dan's user_id is removed from assignee_ids on all 14 tasks
   And dan's user_id is removed from watcher_ids on all 6 tasks
   And dan's 30 comments remain, still attributed to his user_id
   And created_by_id / updated_by_id references on tasks are preserved
   And dan's open WebSocket connections to that workspace's groups are closed
   And a subsequent request from dan to any resource in W returns HTTP 404 with error.code = "not_found"

Scenario F9-AC-07: A guest cannot see or manage the members page
  Given a user with WorkspaceMember.role = "guest" in workspace W
  When the guest sends GET /api/v1/workspaces/{W}/members/
  Then the response is HTTP 403 with error.code = "permission_denied"
  When the guest sends POST /api/v1/workspaces/{W}/invitations/ with any body
  Then the response is HTTP 403 with error.code = "permission_denied"
  When a "member" sends GET /api/v1/workspaces/{W}/members/
  Then the response is HTTP 200 (members may read the roster but may not manage it)
  When that "member" sends PATCH /api/v1/workspaces/{W}/members/{other}/ with {"role":"admin"}
  Then the response is HTTP 403 with error.code = "permission_denied"
```

### Rules & edge cases

- Roles are exactly four, strictly ordered: `owner` > `admin` > `member` > `guest`. Role is stored on `WorkspaceMember.role` and is per-workspace; the same user may hold different roles in different workspaces.
- `owner`: everything, including deleting the workspace, transferring ownership, and changing any role.
- `admin`: manage members (**except owners**), invitations, spaces, folders, lists, statuses and tags; all task operations.
- `member`: CRUD folders, lists, tasks, comments and tags; **read** spaces; **cannot** create or delete spaces; **cannot** manage members or invitations.
- `guest`: read-only on spaces, folders, lists and tasks; may create comments; may **edit tasks where they are an assignee**; cannot create lists, spaces or folders; cannot see the members page.
- Across all roles: everyone may edit and delete their **own** comment; `admin` and `owner` may delete **any** comment; nobody may edit someone else's comment.
- A workspace must always have at least one `owner`. The last owner cannot leave (`POST /api/v1/workspaces/{id}/members/leave/` → 409 `conflict`) and cannot self-demote (409 `conflict`). Ownership transfer is "promote someone to `owner`, then optionally demote or leave."
- Only an `owner` may grant the `owner` role. An `admin` may not modify or remove an `owner`.
- Self-removal by an admin/member/guest goes through `leave/`; removing someone else goes through `DELETE /api/v1/workspaces/{id}/members/{user_id}/`.
- **Duplicate email invite:** a second pending invitation for the same `(workspace, email)` returns 409 `conflict`. Inviting an email that already belongs to a member of the workspace also returns 409 `conflict`. The remedy is `POST /api/v1/invitations/{id}/resend/`, which re-sends the existing token and refreshes its expiry.
- Invitation tokens expire (default 14 days). `GET /api/v1/invitations/lookup/?token=` is the only unauthenticated read in F9 and returns the minimum needed to render the accept screen: workspace name, invited email, role. Expired or unknown tokens return 404 `not_found`.
- `DELETE /api/v1/invitations/{id}/` revokes a pending invitation; the token immediately stops working (subsequent accept → 404 `not_found`). Revoking an already-accepted invitation returns 409 `conflict`.
- An invitation binds to an email address. If the accepting user's authenticated email differs from the invited email, the request returns 403 `permission_denied`.
- Removing a member strips them from `assignee_ids` and `watcher_ids` everywhere in that workspace, preserves their comments and `created_by_id`/`updated_by_id` attributions, and closes their live WebSocket subscriptions for that workspace's groups.
- After removal, any request from that user for resources in the workspace returns 404 `not_found` (existence is not disclosed), not 403.
- Role changes take effect on the next request; already-open WebSocket subscriptions are re-evaluated on the next event fan-out, and a downgraded user is dropped from groups they may no longer read.
- Members may read the roster (`GET /api/v1/workspaces/{id}/members/`); guests may not (403 `permission_denied`).
- There is no per-Space or per-List permission override in MVP: role is workspace-wide. Restricting a guest to a subset of Spaces is post-MVP (OQ-2).

---

## 7. Cross-cutting requirements

### 7.1 Permissions matrix

Role is `WorkspaceMember.role`, per workspace, one of `owner`, `admin`, `member`, `guest`, strictly ordered `owner` > `admin` > `member` > `guest`.

Legend: ✓ allowed · ✗ denied (HTTP 403 `permission_denied`, or 404 `not_found` when the resource is outside the caller's workspace) · **Own** = only rows the caller authored · **Assignee** = only tasks where the caller's `user_id` is in `assignee_ids`.

| Capability | Endpoint(s) | owner | admin | member | guest |
| --- | --- | --- | --- | --- | --- |
| Read workspace | `GET /workspaces/{id}/`, `GET /workspaces/{id}/tree/` | ✓ | ✓ | ✓ | ✓ |
| Create workspace | `POST /workspaces/` | ✓ (becomes owner) | ✓ (becomes owner) | ✓ (becomes owner) | ✓ (becomes owner) |
| Update workspace settings | `PATCH /workspaces/{id}/` | ✓ | ✗ * | ✗ | ✗ |
| Delete workspace | `DELETE /workspaces/{id}/` | ✓ | ✗ | ✗ | ✗ |
| Read spaces | `GET /workspaces/{id}/spaces/`, `GET /spaces/{id}/` | ✓ | ✓ | ✓ | ✓ |
| Create / update / delete Space | `POST /workspaces/{id}/spaces/`, `PATCH`/`DELETE /spaces/{id}/` | ✓ | ✓ | ✗ | ✗ |
| Read folders | `GET /spaces/{id}/folders/`, `GET /folders/{id}/` | ✓ | ✓ | ✓ | ✓ |
| Create / update / delete Folder | `POST /spaces/{id}/folders/`, `PATCH`/`DELETE /folders/{id}/` | ✓ | ✓ | ✓ | ✗ |
| Read lists | `GET /spaces/{id}/lists/`, `GET /lists/{id}/` | ✓ | ✓ | ✓ | ✓ |
| Create / update / delete List | `POST /spaces/{id}/lists/`, `PATCH`/`DELETE /lists/{id}/` | ✓ | ✓ | ✓ | ✗ |
| Move / reorder List | `PATCH /lists/{id}/move/` | ✓ | ✓ | ✓ | ✗ |
| Read status sets | `GET /spaces/{id}/status-set/`, `GET /lists/{id}/status-set/` | ✓ | ✓ | ✓ | ✓ |
| Manage status sets | `PUT /spaces/{id}/status-set/`, `PUT`/`DELETE /lists/{id}/status-set/` | ✓ | ✓ | ✗ | ✗ |
| Read tasks | `GET /lists/{id}/tasks/`, `GET /tasks/{id}/` | ✓ | ✓ | ✓ | ✓ |
| Create task | `POST /lists/{id}/tasks/` | ✓ | ✓ | ✓ | ✗ |
| Update task | `PATCH /tasks/{id}/` | ✓ | ✓ | ✓ | **Assignee** |
| Move task (DnD) | `PATCH /tasks/{id}/move/` | ✓ | ✓ | ✓ | **Assignee** |
| Delete (soft) task | `DELETE /tasks/{id}/` | ✓ | ✓ | ✓ | ✗ |
| See soft-deleted tasks | `?include_deleted=true` | ✓ | ✓ | ✗ | ✗ |
| Watch / unwatch task | `POST`/`DELETE /tasks/{id}/watch/` | ✓ | ✓ | ✓ | ✓ |
| Read comments | `GET /tasks/{id}/comments/` | ✓ | ✓ | ✓ | ✓ |
| Create comment | `POST /tasks/{id}/comments/` | ✓ | ✓ | ✓ | ✓ |
| Edit comment | `PATCH /comments/{id}/` | **Own** | **Own** | **Own** | **Own** |
| Delete comment | `DELETE /comments/{id}/` | ✓ any | ✓ any | **Own** | **Own** |
| Read tags | `GET /workspaces/{id}/tags/` | ✓ | ✓ | ✓ | ✓ |
| Create / update / delete Tag | `POST /workspaces/{id}/tags/`, `PATCH`/`DELETE /tags/{id}/` | ✓ | ✓ | ✓ | ✗ |
| Read member roster | `GET /workspaces/{id}/members/` | ✓ | ✓ | ✓ | ✗ |
| Change member role (non-owner) | `PATCH /workspaces/{id}/members/{user_id}/` | ✓ | ✓ | ✗ | ✗ |
| Change/remove an `owner` | `PATCH`/`DELETE /workspaces/{id}/members/{user_id}/` | ✓ | ✗ | ✗ | ✗ |
| Grant the `owner` role | `PATCH /workspaces/{id}/members/{user_id}/` | ✓ | ✗ | ✗ | ✗ |
| Remove member | `DELETE /workspaces/{id}/members/{user_id}/` | ✓ | ✓ (not owners) | ✗ | ✗ |
| Leave workspace | `POST /workspaces/{id}/members/leave/` | ✓ (not last owner) | ✓ | ✓ | ✓ |
| List / create / revoke / resend invitations | `GET`/`POST /workspaces/{id}/invitations/`, `DELETE /invitations/{id}/`, `POST /invitations/{id}/resend/` | ✓ | ✓ | ✗ | ✗ |
| Accept invitation / lookup token | `POST /invitations/accept/`, `GET /invitations/lookup/` | n/a — available to the invited email | | | |
| Search workspace | `GET /workspaces/{id}/tasks/`, `GET /workspaces/{id}/search/` | ✓ | ✓ | ✓ | ✓ scoped to readable items |
| Subscribe to `ws/list/{id}/`, `ws/space/{id}/` | WebSocket | ✓ | ✓ | ✓ | ✓ read-scoped |

\* The decision sheet assigns workspace-level administration (delete, transfer, role changes) to `owner` and enumerates the `admin` scope as members/invites/spaces/folders/lists/statuses/tags. Workspace **rename/settings** is not enumerated, so this PRD assigns it to `owner` only. See OQ-1.

Enforcement rules that apply to the whole matrix:

- Permission is checked before validation, so a caller never learns whether a payload was valid for a resource they cannot touch.
- Resources outside the caller's workspace return **404 `not_found`**, never 403, so existence is not disclosed.
- Resources inside the caller's workspace that the role may not act on return **403 `permission_denied`**.
- WebSocket subscription is authorized with the same read rules as the corresponding REST read; failure closes the socket after an `error` frame.

### 7.2 Performance budgets

| Surface | Metric | Budget |
| --- | --- | --- |
| `GET /api/v1/workspaces/{id}/tree/` | Server p95, workspace with 10 Spaces / 40 Folders / 200 Lists | < 200 ms |
| `GET /api/v1/lists/{id}/tasks/` (page_size 50) | Server p95 | < 250 ms |
| `GET /api/v1/lists/{id}/tasks/?group_by=status` | Server p95, 8 statuses × 50 tasks | < 350 ms |
| `PATCH /api/v1/tasks/{id}/move/` | Server p95 (excluding rebalance) | < 150 ms |
| `PATCH /api/v1/tasks/{id}/move/` with rebalance | Server p95 | < 800 ms |
| Any write endpoint | Server p95 | < 300 ms |
| WebSocket fan-out | DB commit → frame written to a subscribed socket, p95 / p99 | **< 300 ms** / < 800 ms (metric M4) |
| First contentful paint, authenticated app shell | p75, broadband | < 1.5 s |
| Time to interactive on a List with 200 tasks | p75 | < 2.5 s |
| Drag-and-drop optimistic feedback | Local render after drop | < 16 ms (one frame) |
| Board column incremental load | 50 more cards | < 400 ms p95 |
| N+1 budget | Queries per list-tasks request | ≤ 6 SQL queries regardless of page size |

Additional constraints: `position` is indexed (`db_index=True`); every list query is covered by an index on `(list_id, status_id, position)`; pagination is mandatory on every collection (no unbounded endpoint exists); `page_size` is capped at 200.

### 7.3 Accessibility

- Target: **WCAG 2.1 Level AA** for all MVP surfaces.
- **Full keyboard navigation**: every interactive element is reachable and operable by keyboard alone. No mouse-only affordance ships. This explicitly includes drag-and-drop (F5-US-05): `Space` to lift, arrows to move within/between columns, `Space` to drop, `Escape` to cancel, with a live region announcing "Moved *Fix login redirect* to *In progress*, position 2 of 9."
- Focus is always visible (never `outline: none` without a replacement), focus order follows visual order, and focus is trapped inside the task slide-over and modals with `Escape` restoring focus to the invoking element.
- Contrast: all text meets 4.5:1 (3:1 for large text and UI boundaries) against both the light (`bg #FFFFFF`, `text #1F2937`, `muted #6B7280`) and dark (`bg #16161A`, `text #E7E9EE`, `muted #9096A2`) neutral palettes. Status and priority colors are never the sole carrier of meaning — every status chip shows its `name`, every priority shows a label or icon plus its color.
- Semantics: Board columns are labelled regions with the status `name` and task count; the List view is a table with row/column headers; presence avatars have accessible names; realtime arrivals are announced politely (`aria-live="polite"`), never assertively, so incoming events never interrupt a screen-reader user mid-sentence.
- Forms: every input has a programmatic label; validation errors are associated with `aria-describedby` and mirror the server's `error.details` keys.
- Motion: all animation respects `prefers-reduced-motion`; card movement degrades to an instant position change.
- Zoom/reflow: usable at 200% zoom and at a 320 px viewport width without horizontal scrolling of the whole page (the Board may scroll horizontally as a component).

### 7.4 Internationalization & timezone handling

- **Store UTC, render local.** Every datetime (`created_at`, `updated_at`, `due_date`, `start_date`, `deleted_at`, event `ts`) is stored and transmitted as ISO-8601 UTC with a trailing `Z`, e.g. `"2026-08-07T09:15:00Z"`. The API never returns a local time and never returns an offset other than `Z`.
- The client renders every timestamp in the authenticated user's `timezone` (IANA name, from `GET /api/v1/me/`), falling back to the browser timezone only when the profile value is missing.
- Relative-date filters (`due=today`, `due=this_week`) are evaluated against the **caller's** timezone and translated to a UTC range server-side, so "today" means the user's today, not the server's.
- Date-only inputs (a due date picked without a time) are interpreted as end-of-day in the user's timezone and stored as the corresponding UTC instant.
- Week start for `this_week` follows the user's locale; the default is Monday.
- The UI is English-only in MVP, but all user-facing strings are externalized into a message catalog from day one, no string concatenation for sentences, and no text baked into images or icons. Numbers, dates and lists use `Intl` formatting.
- The layout must not assume string length (German/Finnish expansion) and must not assume LTR-only styling in CSS (use logical properties) even though no RTL locale ships in MVP.
- All identifiers, JSON keys and enum values (`priority`, status `type`, roles) stay in English snake_case/lowercase and are never localized; only their display labels are.
- Text fields accept full Unicode including emoji in `title`, status `name`, tag names and comment bodies; search is accent- and case-insensitive where the database backend supports it.

### 7.5 Audit & undo expectations

- **Attribution is mandatory, a full audit log is not.** Every task carries `created_by_id`, `updated_by_id`, `created_at`, `updated_at`; every comment carries its author and timestamps; every realtime frame carries `actor`. That is the MVP's audit surface. A dedicated immutable audit-log table is out of scope.
- **Soft delete is the recovery mechanism, not a user-facing undo.** Only Task and Comment support `deleted_at`; there is no restore endpoint in MVP. Recovery is a support operation. Everything else (Workspace, Space, Folder, TaskList, StatusSet, Status, Tag, membership) hard-deletes with CASCADE and is unrecoverable.
- Because hierarchy deletion is irreversible and cascading, destructive actions require an explicit confirmation dialog that names the object and states the cascade ("Deleting *Engineering* will permanently delete 4 folders, 17 lists and 312 tasks").
- **Client-side undo** is offered for low-risk, reversible actions only, as a 5-second toast that issues the compensating API call: task move (re-move to the previous `before_id`/`after_id`), status change, priority change, assignment change, archive, and task soft-delete. No undo is offered for anything that hard-deletes.
- Undo after a rebalance (`rebalanced: true`) is disabled for that scope, because the previous neighbour ids no longer describe the same ordering.
- `request_id` (`req_01J...`) is present on every error envelope and is logged server-side, so a user-reported failure can be traced to a single request without an audit log.
- Structured server logs record `user_id`, `client_id`, method, path, status code, `error.code` and duration for every request; these are retained per the infrastructure policy and are the substitute for per-object history in MVP.

---

## 8. Key product decisions & open questions

### 8.1 Decisions made (binding)

| ID | Decision | Rationale | Consequence / cost |
| --- | --- | --- | --- |
| D-1 | Folder is **optional** between Space and List | Lets teams start flat and add structure later without migration; this is the single most distinctive hierarchy property (§4a) | Every List query must handle `folder_id = null`; ordering scope is the compound `(space_id, folder_id)` |
| D-2 | Status sets belong to **either** a Space **or** a List, never both, with a CHECK constraint; effective set = own else Space's | Gives per-team vocabulary without a global admin bottleneck, while guaranteeing a set always exists | Requires a mandatory `status_mapping` on every set replacement; `Task.status` is `PROTECT` |
| D-3 | Statuses are **typed** `open` / `active` / `closed` | Machine-readable semantics under human names; enables cross-List queries like `?status_type=closed` | Every set must contain ≥1 `closed` status and exactly one `is_default` |
| D-4 | List and Board are one dataset, switched with `?group_by=status` | Eliminates dual sources of truth; makes view switching instant (§4c) | Grouped and flat payloads must always agree for identical filters |
| D-5 | **View state is per-user-per-list and client-side** | A colleague switching views must never change your screen; there is no view model in the 15-model data model | Not portable across devices in MVP (OQ-3) |
| D-6 | Ordering uses a lexicographic fractional index (`position`, base-62, compared as plain strings), never integer renumbering | O(1) moves, no write amplification, safe under concurrency | Keys grow on repeated mid-insertion; needs the rebalance rule (D-7) |
| D-7 | On rebalance the server emits a **single `task.moved` with `rebalanced: true`** and clients refetch | The decision sheet explored `list.reordered` and `list.rebalanced` and settled on this; it keeps the WebSocket event vocabulary closed at 10 types | Clients must implement a refetch branch; a rebalance costs one extra list fetch per subscriber |
| D-8 | Clients send `before_id`/`after_id`, never a raw `position` | The server is the only authority on ordering keys; prevents client-invented keys and makes conflicts detectable (`position_conflict`) | One extra server computation per move |
| D-9 | Only `comment.created` broadcasts; comment edits/deletes do not | Keeps the event set minimal for MVP; edits are low-frequency and low-stakes compared to creation | Edited/deleted comments can be briefly stale in an open panel until refetch (OQ-5) |
| D-10 | Realtime events are emitted from the **service/serializer layer**, never from views | Guarantees REST and WebSocket payloads can never diverge in shape or timing | Service layer becomes mandatory; no "quick fix in the view" is allowed |
| D-11 | Echo suppression via a per-tab `client_id` sent as `X-Client-Id` and echoed as `actor.client_id` | Optimistic UI without double-apply or flicker, and correct behaviour across multiple tabs of the same user | Every mutating request must carry the header; missing header degrades to a visible echo |
| D-12 | Soft delete for **Task and Comment only**; everything else hard-deletes with CASCADE | Recovers the two mistakes users actually make, without paying tombstone complexity across the whole schema | Deleting a List destroys its tasks irreversibly — requires a strong confirmation UX |
| D-13 | Four workspace-wide roles, no per-Space overrides | A permission model a non-admin can hold in their head; unblocks the `guest` seat without an ACL system | Cannot restrict a guest to one Space in MVP (OQ-2) |
| D-14 | Guests may **edit tasks where they are an assignee** but may not create or delete tasks | Makes the guest seat genuinely useful for contractors while keeping the blast radius near zero | Task-level permission checks must consider `assignee_ids`, not just role |
| D-15 | Out-of-workspace access returns **404**, in-workspace denial returns **403** | Prevents existence disclosure across tenants while still giving actionable errors inside a workspace | Two distinct code paths in the permission layer |
| D-16 | The Task field set and the 64-endpoint inventory are **closed** for MVP | Scope discipline is the only reason a ClickUp clone can ship; every added field multiplies view, filter and serializer work | Any addition requires updating the decision sheet, this PRD and `API_CONTRACT.md` in one commit |
| D-17 | `priority` is a CharField with a shadow `priority_order` SmallInteger | Human-readable API values with correct sort order and no client-side sort table | Two columns must be kept in sync server-side; clients never write `priority_order` |
| D-18 | `POST /api/v1/me/avatar/` is the only file upload in MVP | Identity in comments and presence needs a face; general attachments do not | Must not become a general-purpose upload endpoint |

### 8.2 Open questions for the tech lead

| ID | Question | Why it matters | Needed by |
| --- | --- | --- | --- |
| OQ-1 | The decision sheet marks "refresh token returned in the JSON body (not a cookie)" as a **REVIEW ITEM**. Do we ship body-delivered refresh tokens, or move to an `HttpOnly`, `Secure`, `SameSite=Lax` cookie? Related: the sheet does not say whether `admin` may `PATCH /api/v1/workspaces/{id}/` (rename/settings) — this PRD assumes `owner` only. Confirm both. | Body delivery means the refresh token is reachable from JS (XSS blast radius); a cookie changes CSRF handling and the WebSocket auth story. The workspace-settings gap is a live 403-vs-200 ambiguity in the permission layer. | Before F1 implementation starts (sprint 1) |
| OQ-2 | `PATCH /api/v1/lists/{id}/move/` — is changing `space_id` (moving a List to a different Space) in or out? This PRD assumes **out** (400 `validation_error`), because the List's effective status set would change and tasks would need a `status_mapping`. Confirm. | Determines whether the move endpoint needs the same mapping machinery as `PUT /lists/{id}/status-set/`, which is a significant scope difference. | Before F2/F4 implementation (sprint 2) |
| OQ-3 | Per-user-per-list view state has no model in the 15-model data model, so this PRD specifies browser-local storage. Do we accept "view state does not follow me to another device" for MVP, or do we add a 16th model / a `me/preferences` blob? | Adding a model breaks the "15 models" constraint; not adding it is a visible (if minor) UX gap that testers will report as a bug. | Before F5 frontend work (sprint 3) |
| OQ-4 | There is no password-reset flow in the 64-endpoint inventory (only `auth/password/change/`, which requires the current password). Is "forgot password" genuinely out of MVP, or does it need 2 more endpoints? | A user who forgets their password has no self-service recovery, which will generate support load from day one; adding it changes the endpoint count and needs the same email infrastructure as invitations. | Before GA scope freeze |
| OQ-5 | The event vocabulary has no `comment.updated`, `comment.deleted`, `task.restored`, or server→client `presence.typing`, and there is no restore endpoint for soft-deleted tasks. Are stale edited/deleted comments and support-only restore acceptable for MVP, or do we extend the vocabulary and add a restore endpoint? | Extending the closed event set has a ripple cost on both clients and the consumer layer; not extending it means documented, deliberate staleness that QA must be told to accept. | Before F6/F7 implementation (sprint 4) |

---

## 9. Future (post-MVP)

The out-of-scope list from §5.2, re-framed as a rough roadmap. Horizons are sequenced by dependency and by how much of the MVP's foundations they reuse — not by customer volume. Nothing here is committed.

### Horizon 1 — Depth on what already exists (next 1–2 quarters after GA)

Everything here extends models and endpoints the MVP already ships, and none of it requires a new architectural primitive.

| Item | Why it comes first | Depends on |
| --- | --- | --- |
| **Subtasks / checklists** | The single most-requested missing primitive; extends Task with a parent reference and roll-up completion | F3 field set, the `position` scheme extended to a hierarchical scope |
| **File attachments** on tasks and comments | Reuses the narrow upload path already proven by `me/avatar/`; needs object storage, quotas and signed URLs | F3, F6, storage infrastructure |
| **Custom fields** | Unblocks the teams that bounce off the closed Task field set; the largest serializer/filter/view change in this horizon | F3, F5, F8 (filtering must become schema-aware) |
| **Task restore / trash UI** | The data is already retained via `deleted_at`; this only exposes it (closes OQ-5) | F3 soft delete |
| **Password reset by email** | Closes OQ-4; reuses the invitation email pipeline | F1, F9 email infra |
| **Saved & shared views** | Promotes per-user-per-list view state into a first-class object (closes OQ-3) | F5, F8 |
| **Bulk edit and multi-select** | Pure leverage on existing task endpoints | F3, F5, F8 |
| **Comment threads, @mentions, reactions** | Turns comments into a real conversation surface; adds `comment.updated`/`comment.deleted` events | F6, F7 event vocabulary |

### Horizon 2 — New surfaces (2–4 quarters out)

Each item here introduces a genuinely new object type or renderer and should be scoped as its own mini-PRD.

| Item | Why it comes second | Depends on |
| --- | --- | --- |
| **Time tracking** | `time_estimate_minutes` already exists; tracking adds timers, entries and a reporting bar with a high correctness requirement | Horizon 1 custom fields (for billable flags), F3 |
| **Gantt / Timeline view** | A third renderer over the same dataset, plus dependency edges and date math | F5 view infrastructure, `start_date`/`due_date` |
| **Task dependencies** | Prerequisite for a useful Gantt; introduces graph validation and cycle detection | F3 |
| **Dashboards** | Widget grid over aggregate queries; only worth building once F8 filters have proven out at scale | F8, stable aggregates |
| **Goals / OKRs** | Roll-up objects over tasks and lists; meaningless before there is task history and dashboards to display them | Dashboards, F2 hierarchy |
| **Docs** | A full collaborative rich-text surface with its own permissions, versioning and realtime model — effectively a second product | F7 realtime foundations, a CRDT/OT decision |
| **Per-Space and per-List permission overrides** | Closes OQ-2/D-13; lets a guest be scoped to a single Space | F9 role model, a real ACL layer |

### Horizon 3 — Platform & ecosystem (4+ quarters out)

| Item | Why it comes last | Depends on |
| --- | --- | --- |
| **Automations** (trigger → condition → action rules) | Highest blast radius: needs a durable rule engine, run history, loop protection and a permission story for "who ran as whom" | Stable events (F7), stable permissions (F9), Horizon 1 field model |
| **Integrations** (Slack, GitHub, calendar) | Each is a separate OAuth, rate-limit, retry and failure surface; only worth it once the core object model has stopped moving | Public API stability, webhooks |
| **Public API, webhooks & API tokens** | Turns Clickish from an app into a platform; requires versioning guarantees we should not make during MVP iteration | Frozen `/api/v1/` contract |
| **Recurring tasks & templates** | Straightforward once automations exist; awkward and duplicative if built before them | Automations |
| **SSO / SAML, SCIM provisioning, audit log** | Enterprise-gated; the audit log deliberately deferred from §7.5 lands here | F1, F9 |
| **Mobile apps** | Only sensible once the web feature set and the API have stabilized | Frozen API, offline strategy |
| **Notifications** (email digests, in-app inbox, push) | Depends on a mature event stream and on watchers/mentions being widely used | F7 events, Horizon 1 mentions |

### Sequencing principle

Ship the skeleton completely and quickly (MVP), harden it with the primitives users hit first (Horizon 1), then add surfaces (Horizon 2), then open the platform (Horizon 3). Any request to pull a Horizon 2 or 3 item into MVP must name which of F1–F9 it replaces.

---

*End of document. Version 1.0 — Approved for build — 2026-08-07.*
