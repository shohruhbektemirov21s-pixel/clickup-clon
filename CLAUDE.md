# ClickUp Clone — Project Guide

A clone of app.clickup.com. Monorepo: Django REST backend + Next.js frontend.

## Layout

```
clickup/
  .venv/                 Python 3.14 virtualenv (ALREADY created — never recreate)
  backend/               Django 5.2 project
    config/              settings.py, urls.py, asgi.py, wsgi.py
    apps/
      accounts/          custom User, auth, JWT, profile
      workspaces/        Workspace, Member, Invitation, Space, Folder, List, Status
      tasks/             Task, Tag, ordering / drag & drop
      comments/          Comment
      realtime/          Channels consumers, routing, broadcast helpers
    manage.py
    requirements.txt
    Dockerfile           multi-stage; runtime serves ASGI via Daphne
    docker-entrypoint.sh waits for the DB, migrates, then execs CMD
  frontend/              Next.js 15 App Router + TS + Tailwind
    Dockerfile           multi-stage; Next standalone output
  docs/                  PRD.md, DATA_MODEL.md, API_CONTRACT.md, SPRINT_PLAN.md, UI_SPEC.md, DOCKER.md
  docker-compose.yml     dev stack: db + redis + backend + frontend
  docker-compose.prod.yml  prod override
  .env.docker.example    template for the repo-root .env compose reads
```

## Stack (fixed — do not swap)

**Backend:** Django 5.2 · DRF 3.17 · djangorestframework-simplejwt · Channels 4 + channels_redis · Daphne · django-cors-headers · django-filter · drf-spectacular · WhiteNoise
**DB:** SQLite in dev, PostgreSQL in prod — selected via `DATABASE_URL` (`django-environ`)
**Frontend:** Next.js 15 (App Router) · TypeScript · Tailwind · shadcn/ui · TanStack Query · Zustand · native WebSocket
**Tests:** pytest + pytest-django (backend), Playwright (E2E)

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

# frontend (run from frontend/)
npm run dev
npm run build
npm run lint
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
- Frontend: server components by default, `"use client"` only where interactivity needs it. All server state through TanStack Query; only UI state in Zustand.
- TypeScript types for API payloads live in `frontend/src/types/api.ts` and mirror `docs/API_CONTRACT.md` field-for-field.
