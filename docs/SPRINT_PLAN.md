# Clickish — MVP Sprint Plan (binding)

## Document control

| Field | Value |
|---|---|
| Document | `docs/SPRINT_PLAN.md` |
| Product | Clickish (ClickUp clone MVP) |
| Version | 1.0.0 |
| Status | Binding — supersedes any informal plan |
| Author | Delivery Lead / Engineering Manager |
| Date issued | 2026-08-07 |
| Authoritative inputs | `DECISIONS.md` (decision sheet), `docs/API_CONTRACT.md` (to be produced in Sprint 1), `CLAUDE.md` |
| Sprint 0 | 2026-08-07 (half day) |
| Delivery window | 2026-08-10 → 2026-09-11 (5 x 1-week sprints) |
| MVP demo / go-no-go | 2026-09-11, 15:00 |
| Change control | Any change to scope, ticket points or the API contract requires a PR touching this file and/or `docs/API_CONTRACT.md`, plus sign-off from the BE lead and the FE lead |

### Conventions used in this document

- All model names, endpoint paths, field names, role names, error codes, event types and design tokens are taken verbatim from the decision sheet. Where this document and the decision sheet disagree, the decision sheet wins and this document is a defect.
- The "List" entity is the Django model `TaskList` (`db_table = "lists"`); the API resource is always `list` (`/lists/`, `list_id`). Ticket text follows that rule.
- Base path is `/api/v1/` with a **required trailing slash** on every path.
- Ticket IDs are continuous across sprints and never reused: `BE-01..BE-46`, `FE-01..FE-35`, `QA-01..QA-17`, `INF-01..INF-16`, `DOC-01..DOC-12`.

## TL;DR

We ship a working Clickish MVP in five one-week sprints: 15 models, all 64 REST endpoints, both views (List and Board), drag & drop with fractional indexing, comments, realtime over Channels, workspace members/roles/invitations, and search/filtering — behind a versioned API contract that lets frontend and backend run fully in parallel from day two.

- **126 tickets, 397 story points**, committed against a nominal capacity of 84 points/sprint across 6 people.
- **Sprint 1** produces the OpenAPI schema and an MSW mock server, so the frontend never waits on the backend again.
- **Sprint 2** builds the hierarchy (Workspace → Space → Folder → TaskList) and the status-set system.
- **Sprint 3** delivers the Task model, the task endpoints and the List view.
- **Sprint 4** delivers the Board view, drag & drop and comments.
- **Sprint 5** delivers realtime, search/filters, members/roles/invitations and hardening.
- **Top risk:** no Docker on the build machine, so Channels runs on `InMemoryChannelLayer` in dev and a natively installed Redis (or Memurai) in the realtime and staging environments. This is decided, not open — see RISK-01.

### Repo reality check (verified on disk 2026-08-07)

These facts differ from the briefing that produced this plan and are reflected in the ticket set:

| Observation | Impact on plan |
|---|---|
| `frontend/` already exists and is scaffolded (Next.js 15, TypeScript, Tailwind, ESLint, `components.json` for shadcn/ui, `node_modules` installed) | FE-01/FE-02 are *configure and verify* tickets, not *create the project* tickets. Sprint 0 does not need `create-next-app`. |
| `backend/` has `manage.py`, `config/` (`settings.py`, `urls.py`, `asgi.py`, `wsgi.py`) and empty apps `accounts`, `comments`, `realtime`, `tasks`, `workspaces` | INF-01 converts the single `settings.py` into a settings package; INF-02 creates the two missing apps. |
| Apps `core` and `spaces` do **not** exist | INF-02 creates them. Per the decision sheet, `Space`, `Folder`, `TaskList`, `StatusSet`, `Status` live in `apps.spaces`, **not** in `apps.workspaces` as `CLAUDE.md` currently states. DOC-04 fixes `CLAUDE.md`. |
| `requirements.txt` contains `model-bakery`, **not** `factory_boy`; it has no `pytest-cov`, no `ruff`, no `locust` | QA-01 adds `factory_boy` + `pytest-cov`, INF-06 adds `ruff`, INF-16 adds the load-smoke tool. `model-bakery` stays installed but is not used, to avoid two competing fixture idioms. |
| `.venv` is Python 3.14 with all backend deps installed; there is no global activation | Every command in tickets uses `../.venv/Scripts/python.exe` explicitly. |
| No Docker | See RISK-01, INF-10, INF-13. |

---

## 2. Team and cadence

### Team

| Role | Headcount | Name/handle (placeholder) | Primary ownership |
|---|---|---|---|
| Backend engineer | 2 | BE-1 (lead), BE-2 | `backend/apps/*`, `config/`, migrations, API contract implementation |
| Frontend engineer | 2 | FE-1 (lead), FE-2 | `frontend/src/*`, mocks, types, both views |
| QA engineer | 1 | QA-1 | pytest suites, Playwright E2E, a11y, load smoke, release sign-off |
| PM / Design | 1 | PM-1 | backlog, `docs/*`, UI spec, design tokens, demo script, stakeholder comms |

BE-1 and FE-1 are the two **contract leads**. They are the only two people who approve a PR that modifies `docs/API_CONTRACT.md`.

### Cadence

| Ceremony | When | Duration | Attendees |
|---|---|---|---|
| Sprint planning | Monday 09:30 | 45 min | All |
| Daily stand-up | Daily 09:45 | 10 min | All |
| Contract sync | Tuesday + Thursday 14:00 | 15 min | BE-1, FE-1, PM-1 |
| Mid-sprint scope check | Wednesday 16:00 | 15 min | EM, PM-1 |
| Code freeze for the sprint | Friday 12:00 | — | All |
| Demo | Friday 14:00 | 30 min | All + stakeholders |
| Retro | Friday 15:00 | 30 min | All |

Sprint 1 starts Monday **2026-08-10**. Each sprint is Monday 09:30 → Friday 15:30. Friday afternoon after retro is reserved for flaky-test triage and is deliberately not planned.

### Capacity

One point ≈ 0.4 ideal engineer-days. A five-day sprint yields ~13 ideal points per engineer before ceremonies, review and interrupt load; we plan at 13 and expect 11–13 delivered.

| Discipline | People | Nominal points/sprint | Notes |
|---|---|---|---|
| BE | 2 | 26 | Backend feature work only |
| FE | 2 | 26 | Frontend feature work only |
| QA | 1 | 14 | 2 points/sprint held back for exploratory testing and bug verification (unticketed) in S1–S4; released in S5 |
| INF | shared (BE-1 + PM-1) | 10 | Infra work is drawn from BE-1 slack + PM-1; tracked as its own stream so it cannot be silently squeezed |
| DOC | PM-1 | 8 | Contract, data model, UI spec, runbook |
| **Total** | **6** | **84** | Committed range per sprint: **77–82** |

Committed load by sprint: S1 82, S2 78, S3 77, S4 78, S5 82. Total **397 points / 126 tickets**.

### Story point scale

| Points | Meaning | Rule of thumb | Example |
|---|---|---|---|
| 1 | Trivial, no design decisions | < 2 hours, one file | `GET /api/v1/health/` |
| 2 | Small, well understood | Half a day | A single model + migration + admin registration |
| 3 | Standard unit of work | ~1 day | A 5-endpoint CRUD resource on an existing model |
| 5 | Large; has real design choices or many moving parts | ~2 days | Task model with all fields; status-set system; List view |
| 8 | Very large; **must** be justified at planning and is the maximum allowed | ~3 days, high uncertainty | Drag & drop with optimistic position and rollback |

Anything estimated above 8 must be split before it enters a sprint. There is exactly one 8-point ticket in the whole plan (FE-24).

### Definition of Ready (a ticket may not enter a sprint without all of these)

1. Title states a user-visible or system-visible outcome, not an activity.
2. Owner role assigned and the named individual has capacity in that sprint.
3. Points agreed by the whole team at planning (planning poker, no averaging).
4. Dependencies listed by ticket ID and all of them are either done or scheduled earlier in the same sprint.
5. For any ticket touching the API: the relevant section of `docs/API_CONTRACT.md` exists and is at a known version.
6. Definition of Done is written, concrete and independently verifiable by someone who did not do the work — it names endpoints, models, files, error codes or UI behaviour.
7. Test approach named (which pytest suite, which Playwright spec, or "no automated test, reviewer verifies manually" with a reason).
8. No open question that would change the approach is outstanding.

### Global Definition of Done (applies to every ticket, in addition to its own DoD)

A ticket is Done when **all** of the following are true:

1. **Code** merged to `main` via a reviewed PR from a `feat/`, `fix/`, `chore/` or `docs/` branch; no direct pushes to `main`.
2. **Tests** written and passing: backend changes ship pytest tests; frontend changes ship at least a component/integration test or a Playwright step; CI is green on the merge commit.
3. **Coverage** does not regress; backend app coverage stays ≥ 85% from Sprint 3 onward (enforced by INF-09).
4. **Docs** updated in the same PR: `docs/API_CONTRACT.md` for any request/response change, `docs/DATA_MODEL.md` for any model change, `CLAUDE.md` for any convention change, `backend/.env.example` for any new setting.
5. **Reviewed** by one other engineer of the same discipline (contract changes additionally by both contract leads).
6. **Migrations** are checked in, apply cleanly on an empty SQLite database, and `makemigrations --check --dry-run` reports no drift.
7. **Error envelope** respected: every non-2xx response matches `{"error":{"code","message","details","request_id"}}` with a code from the allowed set.
8. **Demoable**: the change can be shown in the Friday demo from a clean checkout using `seed_demo` data, without a developer narrating workarounds.
9. No new lint, type or console errors (`ruff`, `eslint`, `tsc --noEmit`).
10. Ticket moved to Done in the tracker with a link to the merged PR.

---

## 3. Parallelisation strategy

### The core idea

The frontend is never allowed to be blocked by the backend, and the backend is never allowed to be blocked by the frontend. The only shared artefact is `docs/API_CONTRACT.md`, which is written **before** either side implements. Both sides implement *against the document*, not against each other.

Mechanically:

1. **Sprint 1, day 1–2:** PM-1 and BE-1 write `docs/API_CONTRACT.md` v1.0.0 (DOC-01) covering all 64 endpoints — path, method, auth, permitted roles, request body, success envelope, every error code, and one worked example per endpoint.
2. **Sprint 1, day 2–3:** BE-1 stands up `drf-spectacular` (INF-03). `GET /api/schema/` emits OpenAPI 3.1. Even for endpoints that are not implemented yet, serializers and view stubs are declared so the schema is complete-by-shape. The schema is exported to `docs/openapi.json` by CI on every merge to `main`.
3. **Sprint 1, day 3:** FE-1 wires `openapi-typescript` (FE-03). `npm run gen:api` reads `docs/openapi.json` and writes `frontend/src/types/api.ts`. This file is generated and never hand-edited.
4. **Sprint 1, day 3–4:** FE-2 builds the MSW mock server (FE-04) in `frontend/src/mocks/`, with handlers typed by `src/types/api.ts`. Handlers return contract-accurate payloads including the collection envelope and the error envelope.
5. **From then on:** `npm run dev:mock` runs the whole frontend against MSW with zero backend. `npm run dev` runs against `http://localhost:8000`. A single env var `NEXT_PUBLIC_API_MODE=mock|live` selects which. Every FE ticket's DoD says the feature works in **mock** mode; the FE ticket is not blocked on the matching BE ticket.
6. **Integration** happens continuously, not at the end. From Sprint 2 the Playwright E2E suite runs in `live` mode against a real Django server seeded with `seed_demo`. Any divergence between MSW and the real server is a bug in one of them, and QA-04 (contract-lint) catches the structural half of it automatically.

### What each discipline does in a sprint, in parallel

| Day | Backend | Frontend | QA | PM/Design |
|---|---|---|---|---|
| Mon | Plan; start models/migrations | Plan; extend MSW handlers for this sprint's endpoints | Write the failing API test suite first | Freeze contract delta for the sprint |
| Tue–Wed | Implement endpoints against the contract | Build UI against MSW | Test suites go green as endpoints land | Draft next sprint's contract section |
| Thu | Wire realtime/permissions; fix contract-lint failures | Switch feature flag to `live`, fix integration deltas | Playwright specs in `live` mode | Review UI against `docs/UI_SPEC.md` |
| Fri am | Freeze, fix, review | Freeze, fix, review | Full suite + a11y run | Demo script |
| Fri pm | Demo, retro | Demo, retro | Sign-off | Demo, retro |

### Contract-change protocol (binding)

`docs/API_CONTRACT.md` carries a semantic version in its header: `1.0.0` at the end of Sprint 1, incremented every sprint (`1.1.0` S2, `1.2.0` S3, `1.3.0` S4, `1.4.0` S5).

1. **The contract is versioned and the version is in the file header.** Every change bumps it: PATCH for typos/clarifications, MINOR for additive changes (new optional field, new endpoint), MAJOR for breaking changes (renamed/removed field, changed status code, changed error code).
2. **A change requires a PR that touches `docs/API_CONTRACT.md`.** A PR that changes a serializer, a URL, a status code or an error code without touching the contract is rejected at review. CI enforces the mechanical part: QA-04 fails the build if the generated OpenAPI schema drifts from the committed `docs/openapi.json` without a contract version bump in the same commit.
3. **Both leads are notified and must approve.** The PR must request review from BE-1 **and** FE-1. GitHub `CODEOWNERS` maps `docs/API_CONTRACT.md` and `docs/openapi.json` to both. No self-merge.
4. **Breaking changes are forbidden after Sprint 3** unless the EM signs off in writing in the PR. After Sprint 3 the frontend has too much surface built on the contract for a rename to be cheap.
5. **The MSW handlers must be updated in the same PR** as any contract change, so mock mode never lags the contract.
6. **Announcement:** the PR author posts the diff summary in the team channel and it is the first item at the next contract sync.

### Anti-blocking rules

- If the frontend needs an endpoint shape that does not exist yet, FE-1 proposes it as a contract PR. It is **never** invented locally in a mock handler and reconciled later.
- If the backend discovers the contract is unimplementable as written, the backend does **not** silently deviate. It raises a contract PR the same day and keeps the endpoint unimplemented until the PR merges.
- A BE ticket blocked > 4 hours on an FE question, or vice versa, is escalated at stand-up and swapped for the next unblocked ticket in the sprint.

---

## 4. Sprint 0 checklist — pre-work (half day, Friday 2026-08-07 afternoon)

Not point-estimated; this is setup, done by BE-1, FE-1 and PM-1 together in a half day. Nothing in Sprint 1 may start until every box is ticked.

| # | Item | Owner | Done when |
|---|---|---|---|
| S0-1 | Confirm git repo at project root is initialised, `main` exists and is pushed to the remote | BE-1 | `git remote -v` shows the origin; `git log` has at least the scaffold commit on `main` |
| S0-2 | Branch strategy documented in `CONTRIBUTING.md`: trunk-based, short-lived branches `feat/<ticket-id>-<slug>`, `fix/…`, `chore/…`, `docs/…`; squash-merge only; branch deleted on merge | PM-1 | `CONTRIBUTING.md` on `main` names the four prefixes and the squash rule |
| S0-3 | Branch protection on `main`: no direct push, 1 approving review, CI required, linear history | BE-1 | A push to `main` is rejected by the server |
| S0-4 | `CODEOWNERS` maps `docs/API_CONTRACT.md`, `docs/openapi.json` → BE-1 + FE-1; `backend/**` → BE team; `frontend/**` → FE team | BE-1 | Opening a test PR on the contract auto-requests both leads |
| S0-5 | Commit convention: Conventional Commits with the ticket ID, e.g. `feat(tasks): BE-23 add Task model` | PM-1 | Documented in `CONTRIBUTING.md`; commitlint config in repo |
| S0-6 | `backend/.env.example` created with every key the app will read: `DJANGO_SETTINGS_MODULE`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `CHANNEL_LAYER`, `CORS_ALLOWED_ORIGINS`, `ACCESS_TOKEN_LIFETIME_MINUTES`, `REFRESH_TOKEN_LIFETIME_DAYS`, `MEDIA_ROOT` | BE-1 | File exists; no real secret is in it; `backend/.env` is git-ignored |
| S0-7 | `frontend/.env.example` with `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_BASE_URL`, `NEXT_PUBLIC_API_MODE` | FE-1 | File exists and is git-ignored in its `.env.local` form |
| S0-8 | `.gitignore` verified to exclude `.venv/`, `backend/.env`, `db.sqlite3`, `frontend/node_modules/`, `frontend/.next/`, `media/`, `.pytest_cache/`, `htmlcov/`, `playwright-report/` | BE-1 | `git status` is clean after a full backend + frontend run |
| S0-9 | CI skeleton at `.github/workflows/ci.yml`: triggers on PR and push to `main`, two jobs (`backend`, `frontend`), both currently no-ops that exit 0 | BE-1 | A test PR shows two green checks |
| S0-10 | Tracker (project board) created with columns Backlog / Ready / In Progress / In Review / QA / Done; all 126 tickets imported with IDs, points, owner role and dependencies | PM-1 | Board shows 126 cards; the Sprint 1 filter shows 32 |
| S0-11 | Verify toolchain: `../.venv/Scripts/python.exe manage.py check` passes; `npm run build` in `frontend/` passes | BE-1, FE-1 | Both commands exit 0 from a clean checkout |
| S0-12 | Decide and record the dev channel-layer position (InMemory) and the realtime-test position (native Redis on Windows) in `docs/adr/0001-channel-layer.md` | BE-1 | ADR merged; referenced by INF-10 and RISK-01 |

---

## 5. Sprints

<!-- CONT -->
