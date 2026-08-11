# UzWork frontend — agent rules

Read `../CLAUDE.md` first; this file only adds what is specific to `frontend/`.

## What this app is

A **client-rendered React 19 SPA built with Vite**, routed by React Router,
styled with Tailwind v4, fetching everything from the Django REST API at
`/api/v1/` and the Channels WebSocket endpoints. There is no SSR, no server
components, no route handlers, no `metadata` export.

UzWork is an independent implementation inspired by ClickUp-style
work-management workflows — never describe it as a ClickUp clone, and never
copy ClickUp code, assets, logo or proprietary design
(`../docs/adr/0014-mahsulot-nomi.md`).

## Framework: React + Vite (ADR 0011)

The port off Next.js 16 App Router is **done**
(`../docs/adr/0011-frontend-framework.md`). What that means day to day:

- There is no `next.config.ts`, no `next-env.d.ts`, no `src/app/` route tree and
  no `next` dependency. Do not add any back. `src/app/` holds exactly two files:
  `globals.css` and `providers.tsx`.
- Routing is React Router. Routes are declared in `src/routes/app-routes.tsx`;
  `src/routes/app-routes.test.ts` locks the 20 public URLs, so a renamed path
  fails a test rather than a user's bookmark.
- Navigation: `useNavigate` / `useLocation` / `useParams` / `useSearchParams`
  from `react-router`. Links go through `@/components/ui/link`, which keeps the
  old `href` prop so call sites read the same.
- Page titles: `usePageTitle(...)`, not a `metadata` export.
- Env: `import.meta.env.VITE_*`. Anything named `NEXT_PUBLIC_*` is dead — Vite
  will not expose it and you get `undefined` with no warning.
- Security headers are the serving layer's job, not app code's:
  `security-headers.ts` (dev/preview) and `nginx/default.conf.template` (prod
  image). `src/test/security-headers.test.ts` keeps the two in parity — if you
  add a header to one, that test tells you about the other.
- Tests: `npm test` (vitest) for components/hooks/units, `npm run test:e2e`
  (Playwright) against a real stack. ADR 0013 draws the line.

## Hard rules

- **Tailwind v4, CSS-first.** No `tailwind.config.*` file — ever. Tokens live in
  `@theme` inside the single global stylesheet. `hsl(var(--x) / <alpha-value>)`
  is pre-v4 syntax and wrong.
- **@dnd-kit** is the only drag & drop library.
- **TanStack Query** owns all server state; **Zustand** owns UI state only.
  Never cache API responses in Zustand.
- **Uzbek UI copy.** Any string a user can read is Uzbek; identifiers stay
  English.
- **Permission gating is cosmetic here.** `can()` hides controls; the server
  re-checks every write. Never treat a hidden button as a security boundary,
  and never gate on `my_role` — gate on `my-permissions/`.
- `src/types/api.ts` mirrors `../docs/API_CONTRACT.md` field-for-field and is
  hand-maintained. Do not invent fields; if the contract lacks it, the contract
  changes first. Codegen is decided but not implemented
  (`../docs/adr/0015-api-tiplari-codegen.md`).
- `docs/UI_SPEC.md` is **superseded** — do not implement from it.

## Before you hand work over

```bash
npm run lint
npx tsc --noEmit
npm run test            # vitest
npm run build
npx playwright test     # when a user-visible flow changed; needs both servers
```

Optimistic mutations must have a rollback path and a vitest case proving the
rollback (`../docs/adr/0013-frontend-testlash.md`). Leave no `test-results/`,
`playwright-report/` or scratch files in the tree.
