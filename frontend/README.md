# UzWork — frontend

Client-rendered SPA for UzWork: **React 19 + Vite + React Router + TypeScript +
Tailwind v4**. It talks to the Django REST backend at `/api/v1/` and to the
Channels WebSocket endpoints; there is no server-side rendering and no
server-side data fetching.

UzWork is an independent implementation inspired by ClickUp-style
work-management workflows — not a clone, and no ClickUp code, assets, logo or
proprietary design is used. See `../docs/adr/0014-mahsulot-nomi.md`.

> **Ported off Next.js** (`../docs/adr/0011-frontend-framework.md`). There is no
> `next.config.ts`, no `src/app/` route tree, no `"use client"` directive and no
> `next` dependency left. Routing is a React Router table in `src/routes/`, page
> titles come from `src/hooks/use-page-title.ts`, and the security headers that
> `next.config.ts` used to send now live in `security-headers.ts` (dev/preview,
> via `vite.config.ts`) and `nginx/default.conf.template` (prod image), kept in
> sync by `src/test/security-headers.test.ts`.

## Getting started

```bash
npm install
npm run dev        # Vite dev server
```

The backend must be running separately (see the repo root `README.md`). API and
WebSocket base URLs come from Vite env vars (`import.meta.env.VITE_*`) — copy
`.env.example` if present, otherwise the defaults point at
`http://127.0.0.1:8000`.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Type-check then produce the static production build |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | ESLint (flat config, `eslint.config.mjs`) |
| `npm run test` | vitest — unit, hook and component tests |
| `npx playwright test` | E2E against a real running stack (`e2e/`) |

Testing split is fixed by `../docs/adr/0013-frontend-testlash.md`: vitest owns
units, hooks and components (including optimistic-update rollback); Playwright
owns flows over the real stack.

## Layout

```
index.html      SPA shell (the only HTML document)
src/
  main.tsx      entry point: createRoot + RouterProvider + providers
  routes/       React Router table, route layouts and page shells
  app/          globals.css (Tailwind v4 @theme) + providers.tsx
  components/   UI, shell, board, list, task, settings, auth
  hooks/        TanStack Query hooks, WebSocket channels
  lib/          api client, helpers
  stores/       Zustand — UI state only
  types/        api.ts — hand-maintained API payload types
  i18n/         Uzbek UI strings
  test/         vitest setup + cross-cutting tests
nginx/          prod container config (static SPA + security headers)
e2e/            Playwright specs
```

## Conventions

- **Server state only through TanStack Query**; Zustand holds UI state only.
- **Tailwind v4 is CSS-first** — there is no `tailwind.config.*` and you must
  not create one. Tokens live in `@theme` inside the single global stylesheet.
- Drag & drop is **@dnd-kit** — do not add another DnD library.
- **All user-facing copy is Uzbek.** Code identifiers stay English.
- Permissions are gated on `GET workspaces/{id}/my-permissions/`, never on
  `my_role` — and the UI gate is cosmetic; the server re-checks every write.
- `src/types/api.ts` mirrors `../docs/API_CONTRACT.md` field-for-field and is
  hand-maintained today (`../docs/adr/0015-api-tiplari-codegen.md` describes the
  codegen target, which has not landed).

Full project guide: `../CLAUDE.md`. Binding API contract:
`../docs/API_CONTRACT.md`.
