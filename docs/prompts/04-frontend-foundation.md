# Faza 04 — Frontend fundamenti

## Holat

**Bajarildi.** React 19 + **Vite** + **React Router** (SPA) + TypeScript +
Tailwind v4 (CSS-first, `@theme` `frontend/src/app/globals.css`da —
`tailwind.config.*` YO'Q va yaratilmasligi kerak). Faza dastlab Next.js 16
App Router'da qurilgan edi; 2026-08-11 da `docs/adr/0011-frontend-framework.md`
bo'yicha Vite'ga ko'chirildi — marshrutlar `frontend/src/routes/`,
sahifa sarlavhalari `usePageTitle`, env `import.meta.env.VITE_*`. `frontend/src/components/shell/` — app-shell,
top-bar, workspace-home, nav-rail. `frontend/src/hooks/` — TanStack Query
(`queries.ts`, `mutations.ts`), Zustand faqat UI holati uchun.
`frontend/src/types/api.ts` — `docs/API_CONTRACT.md`ni qo'lda kuzatuvchi
tiplar (`docs/adr/0010-api-tiplari.md`). Auth oqimi, workspace switcher,
profil/logout, parol ko'rsatish/yashirish — hammasi ishlaydi (commit
tarixi: `1381fb4`, `4a781d6`, `48147c4`).

## Prompt

```
Verify and finish the frontend foundation for UzWork
(frontend/src/app, frontend/src/components/shell, frontend/src/hooks).
This phase is DONE — audit, do not rebuild.

Hard constraints (violating these is a regression, not a fix):
- Tailwind is v4, CSS-first. There is NO tailwind.config.* file — do not
  create one. Tokens live in @theme inside frontend/src/app/globals.css.
- The app is a client-rendered SPA (ADR 0011). There are no server
  components and no `"use client"` directives — do not reintroduce either,
  and do not add `next/*` imports.
- Routes are declared in frontend/src/routes/app-routes.tsx and their URLs
  are locked by frontend/src/routes/app-routes.test.ts. Renaming a path is
  a breaking change to real bookmarks, not a refactor.
- ALL server state goes through TanStack Query (frontend/src/hooks/
  queries.ts, mutations.ts); Zustand holds only UI state, never server
  data.
- frontend/src/types/api.ts is TODAY still hand-written and hand-maintained,
  mirroring docs/API_CONTRACT.md field-for-field; keep it in sync by hand
  when you touch an endpoint's shape. The accepted target is
  openapi-typescript codegen (docs/adr/0015-api-tiplari-codegen.md, which
  supersedes 0010) — it is not implemented yet, so do not import from a
  generated file until that ADR says it landed.
- The UI language is Uzbek. New user-facing copy is Uzbek; code
  identifiers stay English.

Check specifically:
- frontend/src/hooks/use-workspace-channel.ts: WebSocket wiring against
  docs/API_CONTRACT.md §15 (space-scoped groups, resync on
  permission.updated/access.revoked).
- The permission gate: confirm UI reads GET workspaces/{id}/my-permissions/
  (frontend/src/lib/permissions.ts), never my_role, per CLAUDE.md.

Fix only genuine gaps against the contract; do not introduce a new state
library, do not add a tailwind.config file, do not switch drag-and-drop
libraries away from @dnd-kit.
```

## Qabul mezonlari

- [ ] `tailwind.config.*` fayli mavjud emas, tokenlar `globals.css`dagi
      `@theme`da
- [ ] Server state faqat TanStack Query orqali, Zustand faqat UI holati
- [ ] `frontend/src/types/api.ts` `API_CONTRACT.md` bilan maydon-maydon mos
- [ ] Ruxsat tekshiruvi `my-permissions/` dan, `my_role`dan emas
- [ ] `npm run lint`, `npm run typecheck`, `npm test` (vitest) va
      `npm run build` toza (`.github/workflows/ci.yml` frontend job'iga mos)
- [ ] `src/**` da bitta ham `next`/`next/*` importi yo'q
