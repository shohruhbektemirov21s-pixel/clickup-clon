# Faza 06 — Dashboard ekrani

## Holat

**Ishlanmoqda, hali commit qilinmagan.** `git status` bo'yicha untracked:
`frontend/src/app/(app)/w/[workspaceId]/dashboard/` (route) va
`frontend/src/components/shell/dashboard-view.tsx` (375 qator). Kod
yozilgan, lekin hali birorta commit'ga kirmagan — ya'ni review halqasidan
o'tmagan, E2E qamrovi yo'q, va `docs/API_CONTRACT.md`da dashboard uchun
alohida endpoint hujjatlashtirilganmi tekshirilmagan. Keyingi sessiya buni
**noldan qurmasin** — avval nima yozilganini o'qib, tugatish/tuzatish
kerak.

## Prompt

```
Finish the dashboard view for UzWork — frontend/src/components/shell/
dashboard-view.tsx and its route at frontend/src/app/(app)/w/[workspaceId]/
dashboard/page.tsx already exist but are UNCOMMITTED work-in-progress
(confirm with `git status` before assuming anything about their state —
they may have changed since this was written).

Before writing new code:
1. Read dashboard-view.tsx fully and determine what data it actually
   queries (grep for useQuery/fetch calls to see which backend
   endpoints it depends on).
2. Cross-check every endpoint it calls against docs/API_CONTRACT.md. If
   dashboard-view.tsx calls something not in the contract, either the
   contract is missing an update (fix docs/API_CONTRACT.md in the same
   commit, per CLAUDE.md's binding-contract rule) or the frontend is
   calling a route that doesn't exist yet (check backend/apps for a
   matching view before assuming it needs to be built).
3. Confirm it follows the existing conventions this codebase already
   established: server state through TanStack Query
   (frontend/src/hooks/queries.ts), permission gating via
   GET workspaces/{id}/my-permissions/ (frontend/src/lib/permissions.ts),
   Uzbek UI copy.

Then: finish whatever is incomplete, add it to the nav (check
frontend/src/components/shell/nav-rail.tsx, also uncommitted — confirm
dashboard is actually linked from somewhere a user can reach), and write
at least a smoke-level Playwright test under frontend/e2e/ so this phase
gets the same CI coverage every other screen has.
```

## Qabul mezonlari

- [ ] `dashboard-view.tsx` chaqiradigan har bir endpoint
      `docs/API_CONTRACT.md`da hujjatlashtirilgan
- [ ] Server holat TanStack Query orqali, Zustand'da server ma'lumot yo'q
- [ ] Ruxsat tekshiruvi `my-permissions/` orqali
- [ ] `nav-rail.tsx`da dashboard'ga havola bor va u ishlaydi
- [ ] Kamida bitta Playwright smoke test qo'shilgan
      (`frontend/e2e/`)
- [ ] O'zgarishlar commit qilingan (hozir untracked)
