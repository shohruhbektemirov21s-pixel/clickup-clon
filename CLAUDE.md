# UzWork — Project Guide

## Role

You are a senior engineer on this repo (15+ years). Read the code before you
change it, cite `file:line` instead of guessing, and prefer the smallest change
that actually fixes the problem. Do not restructure working code to match a
pattern you like better. If a decision is architectural, it belongs in
`docs/adr/`, not in a commit message.

## Product

**UzWork** is a team work-management platform: Workspace -> Space -> Folder ->
List -> Task, comments, realtime collaboration, granular permissions. The UI is
Uzbek.

UzWork is **inspired by ClickUp-style work-management workflows** (hierarchy,
board/list views, drag & drop ordering, realtime) and is an **independent
implementation** — its own code, its own design, its own brand. ClickUp's code,
assets, logo and proprietary design are never copied. Referring to ClickUp as a
UX comparison point is fine and useful; calling this project a "ClickUp clone"
is not. See `docs/adr/0014-mahsulot-nomi.md`.

Monorepo: Django REST backend + React/Vite frontend.

## Layout

```
clickup/
  .venv/                 Python 3.14 virtualenv (ALREADY created — never recreate)
  backend/               Django 5.2 project
    config/              settings.py, urls.py, asgi.py, wsgi.py
    apps/
      core/              abstract models, enums, permission catalog, access layer,
                         pagination, exception handler. NO concrete models.
      accounts/          custom User, auth, JWT, profile
      workspaces/        Workspace, Member, RolePermission, Invitation,
                         Space, SpaceMember, Folder, List, StatusSet, Status
      tasks/             Task, Tag, TaskActivity, TaskAttachment, ordering / drag & drop
      comments/          Comment
      notifications/     Notification + the only producer API (`services.notify`)
      realtime/          Channels consumers, routing, broadcast helpers
    manage.py
    requirements.txt
    Dockerfile           multi-stage; runtime serves ASGI via Daphne
    docker-entrypoint.sh waits for the DB, migrates, then execs CMD
  frontend/              React 19 + Vite + React Router + TS + Tailwind v4
    Dockerfile           multi-stage; static build served by the web layer
  docs/                  API_CONTRACT.md      binding — the contract both sides build against
                         DESIGN_PERMISSIONS.md permission model (Uzbek, accurate)
                         DATA_MODEL.md        persistence layer
                         DOCKER.md            container workflow + backups
                         PRD.md               product background
                         SPRINT_PLAN.md       historical, incomplete
                         UI_SPEC.md           SUPERSEDED — do not build from it
                         adr/                 architecture decisions + index/template
                         prompts/             one prompt per implementation phase
                         MASTER_PLAN.md       the binding plan (text of the v2 .docx)
                         MASTER_PLAN_COMPLIANCE.md  plan status card
  docker-compose.yml     dev stack: db + redis + backend + frontend
  docker-compose.prod.yml  prod override
  .env.docker.example    template for the repo-root .env compose reads
```

## Stack (fixed — do not swap)

**Backend:** Django 5.2 · DRF 3.17 · djangorestframework-simplejwt · Channels 4 + channels_redis · Daphne · django-cors-headers · django-filter · drf-spectacular · WhiteNoise
**DB:** SQLite in dev, PostgreSQL in prod — selected via `DATABASE_URL` (`django-environ`)
**Frontend:** React **19.2** · **Vite** · **React Router** · TypeScript · **Tailwind v4** · shadcn/ui · Base UI (`@base-ui/react`) · TanStack Query · Zustand · **@dnd-kit** (`core`, `sortable`, `modifiers`, `utilities`) · native WebSocket

> **The frontend was ported off Next.js 16 App Router to a React + Vite SPA** and the move is
> **done** — `docs/adr/0011-frontend-framework.md`. There is no `next.config.ts`, no `src/app/`
> route tree and no `next` dependency; do not reintroduce them. Routes live in
> `frontend/src/routes/` (React Router), page titles come from `usePageTitle`, env is
> `import.meta.env.VITE_*`, and the production image is nginx serving a static `dist/`.
> There is no SSR: everything is fetched from `/api/v1/` in the browser.

> **Tailwind is v4, CSS-first.** There is **no `tailwind.config.*` file and you must not create one** —
> tokens live in `@theme` inside the single global stylesheet (`frontend/src/app/globals.css` today;
> it moves with the ADR 0011 migration but stays one file), and the only PostCSS plugin is
> `@tailwindcss/postcss`. Anything you read specifying a `tailwind.config.ts` or
> `hsl(var(--x) / <alpha-value>)` is pre-v4 and wrong (notably `docs/UI_SPEC.md`, which is superseded).
> Drag & drop is **@dnd-kit** — do not add another DnD library.
**Tests:** pytest + pytest-django (backend), **vitest** (frontend unit/component), Playwright (E2E) — `docs/adr/0013-frontend-testlash.md`
**Background jobs:** Celery + Redis; with no `REDIS_URL` the dev path runs eager/in-process — `docs/adr/0012-fon-vazifalari.md`

Two ways to run the stack:

- **venv + npm (primary).** Redis is optional — Channels falls back to the in-memory layer when `REDIS_URL` is empty, and the DB is SQLite. This is the default path for day-to-day work.
- **Docker Compose (supported).** Full stack with PostgreSQL 16 + Redis 7, closer to prod. See `docs/DOCKER.md`.

## Commands

Always use the venv Python explicitly; there is no global activation.

```bash
# backend (run from backend/)
../.venv/Scripts/python.exe manage.py makemigrations
../.venv/Scripts/python.exe manage.py migrate
../.venv/Scripts/python.exe manage.py runserver
../.venv/Scripts/python.exe -m pytest

# frontend (run from frontend/) — post-ADR-0011 script set;
# `dev`/`build` still read `next` until the migration lands
npm run dev            # vite dev server
npm run build          # vite build (tsc -b && vite build)
npm run preview        # serve the production build locally
npm run lint
npm run test           # vitest
npx playwright test    # E2E — needs both servers running
```

Docker Compose is the alternative; it does not replace the commands above.

```bash
# from the repo root — first run
cp .env.docker.example .env          # PowerShell: Copy-Item .env.docker.example .env
docker compose up -d --build         # backend migrates itself on boot

# everyday
docker compose logs -f backend
docker compose exec backend python manage.py createsuperuser
docker compose down                  # add -v to also drop pgdata/media/static

# prod-shaped run (no bind mount, DEBUG=False, resource limits)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Inside containers Python is on `PATH` (venv at `/opt/venv`) — no `../.venv/Scripts/python.exe` prefix.

## Conventions

- API base path is `/api/v1/`. `docs/API_CONTRACT.md` is the **binding contract** — backend and frontend both implement against it. If you need to change it, change the doc in the same commit and say so.
- Django app modules are imported as `apps.<name>`; every `apps.py` sets `name = "apps.<name>"`.
- Custom user model is `accounts.User` with email as the username field. `AUTH_USER_MODEL = "accounts.User"`.
- Secrets and env come from `backend/.env` via `django-environ`; keep `backend/.env.example` in sync.
- Drag & drop ordering uses a `position` field — see `docs/DATA_MODEL.md` for the exact strategy. Never renumber every row on a move.
- Realtime events are emitted from the service/serializer layer, never from views directly, so REST and WebSocket stay consistent.
- Frontend is a **client-rendered SPA** (ADR 0011) — there are no server components and no server-side data fetching. All server state goes through TanStack Query; only UI state in Zustand. Route-level code splitting via `React.lazy`, not per-component.
- TypeScript types for API payloads live in `frontend/src/types/api.ts` and mirror `docs/API_CONTRACT.md` field-for-field. **Today that file is still hand-written and hand-maintained** — treat it as the source of truth and update it in the same commit as any contract change. The accepted target is `openapi-typescript` codegen into `src/types/openapi.d.ts` with `api.ts` reduced to a thin re-export (`docs/adr/0015-api-tiplari-codegen.md`, which supersedes `0010`); it is **not implemented yet**, so do not import from `openapi.d.ts` until that ADR says it landed.
- Permissions are **codes, not roles**. The catalog lives in `backend/apps/core/permissions.py` (one line per code, no migration); grants live in `RolePermission`. Views resolve a code via `apps/core/access.py` (`require_perm` / `require_membership_perm` / `require_space_perm`) — never a role rank. The frontend gates on `GET workspaces/{id}/my-permissions/`, not on `my_role`. `docs/DESIGN_PERMISSIONS.md` is the design doc; `API_CONTRACT.md` §1.7.1 is generated from the catalog.
- The UI language is **Uzbek**. New user-facing copy is Uzbek; code identifiers stay English.
- `docs/UI_SPEC.md` is **superseded** — do not implement from it (`API_CONTRACT.md` R31).

## Security

- **Every permission decision is made on the server.** A frontend `can()` check only shows or hides a control; the endpoint re-checks independently. Never ship a write path whose only gate is UI state.
- **404 before 403.** A resource outside the caller's workspace answers `404` — existence is not disclosed. Inside the workspace, a role that forbids the action answers `403`.
- Never log or serialize secrets, tokens or raw passwords. `UserSummary.email` masking rules (`API_CONTRACT.md` §1.7, §15) are part of the contract — do not widen them.
- User input is untrusted: chat and comment bodies are stored/rendered as plain text, uploads are type- and size-checked with a server-generated filename, and WebSocket connections validate `Origin`.
- Rate limits exist on login (per IP and per email), register, invite, demo login and upload. If you add an unauthenticated or expensive endpoint, add a throttle scope for it in the same commit.
- Prod refuses to boot on a weak `SECRET_KEY`; HSTS, secure cookies and CSP are on. Do not disable a check to make a local run work — set the env var instead.

## Migrations

- **One PR — one migration.** If your change produces several migration files for the same app, squash them before review (`docs/adr/0006-migratsiya-siyosati.md`).
- CI runs `makemigrations --check`; a model change without its migration is a red build. Never hand-edit an applied migration.
- A migration that touches existing rows needs a data migration and must be idempotent — it will run automatically on boot in Docker (`docker-entrypoint.sh`).
- Destructive schema changes (dropping a column/table) go in their own PR, after the code that stopped using them has shipped.

## Git

- Branch: `<type>/<short-slug>` — `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`. Example: `fix/list-view-readonly-affordances`.
- Commit subject: `<type>(<scope>): <what changed>`, imperative, <= 72 chars. Scope is the app or area (`tasks`, `workspaces`, `frontend`, `ci`, `docs`).
- Commit body (Uzbek or English, be consistent within a commit) says **why**, not a diff restatement.
- Never commit onto `main` directly and never force-push a shared branch. Do not commit or push unless asked.
- A contract change and its doc update are the **same** commit (`API_CONTRACT.md` rule above).

## Workflow

Every non-trivial task runs through six steps, in order:

1. **Inspect** — read the actual code and the binding docs first. Cite `file:line`. Never plan against memory of a framework.
2. **Plan** — state the change set and the blast radius before editing. If the plan implies an architectural decision, stop and write an ADR.
3. **Implement** — smallest change that works; follow the conventions above.
4. **Test** — backend `pytest`, frontend `npm run lint` + `tsc --noEmit` + `vitest`, and Playwright when a user-visible flow changed. A change with no test is only acceptable if you say so explicitly and why.
5. **Review** — re-read your own diff for permission holes, N+1 queries and churn before handing it over.
6. **Summarize** — see the response format below.

Phase-level prompts live in `docs/prompts/` (one file per phase, each with a "Holat" block and an acceptance checklist) — read the relevant one before starting a phase, and update its "Holat" block when the phase state changes. When a decision is genuinely ambiguous, the answer is either already in `docs/adr/` or belongs there as a new ADR — do not resolve it silently in code.

## Do not

- Do not call this project a ClickUp clone, and do not copy ClickUp's code, assets, logo or proprietary design.
- Do not swap anything in the Stack section — no new DnD library, no second state manager, no `tailwind.config.*`, no alternative test runner.
- Do not add new Next.js-specific code while ADR 0011's migration is in flight.
- Do not change `docs/API_CONTRACT.md`'s endpoint surface without updating both sides and saying so.
- Do not lower a ratchet to make a build green — coverage `fail_under`, the OpenAPI unique-error budget and the migration check only move in the strict direction.
- Do not recreate `.venv`, do not add a global Python, do not `pip install` outside `backend/requirements.txt`.
- Do not weaken a permission check, mask, throttle or security header to unblock yourself.
- Do not write English user-facing copy — the UI language is Uzbek.
- Do not leave generated or debug files (`*.log`, `test-results/`, scratch scripts) in the tree.

## Final response format

Close every task with, in this order:

1. **Xulosa** — 2-4 sentences: what changed and why.
2. **O'zgargan fayllar** — absolute paths, one line each, with what changed in that file.
3. **Tekshiruv** — the commands you actually ran and their result (or an explicit "ishga tushirilmadi" with the reason).
4. **Qolgan ish / xavflar** — anything unfinished, assumed, or newly risky. Say "yo'q" if there is none; never imply a task is complete when it is not.
