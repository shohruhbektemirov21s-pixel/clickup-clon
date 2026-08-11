# Faza 05 — Kanban / Board ko'rinishi

## Holat

**Bajarildi.** `frontend/src/components/board/` — `board-view.tsx`,
`board-column.tsx`, `board-card.tsx`, `board-states.tsx`,
`use-board-permissions.ts`. @dnd-kit orqali sudrab tashlash (loyihada
belgilangan yagona DnD kutubxonasi — boshqasi qo'shilmasin). List
ko'rinishi bilan bir xil ma'lumot manbasidan oziqlanadi
(`frontend/src/lib/task-buckets.ts`, `task-cache.ts`). Oxirgi branch
(`fix/list-view-readonly-affordances`) list-view'dagi faqat-o'qish
hisoblar uchun affordance regressiyasini tuzatgan — board ko'rinishida
xuddi shu sinf muammo bor-yo'qligini tekshirish kerak (E2E:
`e2c4f62`da faqat list-view qamrovda).

## Prompt

```
Verify and finish the Kanban/board view for UzWork
(frontend/src/components/board/). This phase is DONE — audit, do not
rebuild the drag-and-drop plumbing.

Hard constraint: drag & drop is @dnd-kit (core, sortable, modifiers,
utilities) only — do not add another DnD library, even for a feature
@dnd-kit handles awkwardly.

Recent regression class to check for HERE specifically: the branch this
repo is currently on (fix/list-view-readonly-affordances) fixed a bug
where read-only accounts (see docs/API_CONTRACT.md's guest role and the
demo-account feature, settings.py DEMO_MODE) saw drag handles / action
buttons they could not actually use in the list view. Confirm
board-view.tsx / board-card.tsx / use-board-permissions.ts gate the same
affordances correctly for a read-only viewer — a guest or demo account
should not see a draggable card handle or column-menu actions it cannot
execute. If you find the same class of gap, fix it and add a Playwright
regression test alongside the existing frontend/e2e/ suite (mirror the
list-view test's structure).

Check ordering behavior matches backend/apps/tasks position semantics
(docs/DATA_MODEL.md §8) — a drop should PATCH a single task's position/
status, never trigger a bulk reorder.

Status-model dependency: board columns are driven by Status objects today.
If docs/adr/0009-status-modeli.md's migration has landed (Task.status is
now a fixed enum), board-column.tsx must be updated to render the 4 fixed
codes as columns instead of querying StatusSet — check 02-hierarchy.md's
status first before assuming board-column.tsx is still correct.
```

## Qabul mezonlari

- [ ] Faqat @dnd-kit ishlatiladi, boshqa DnD kutubxona qo'shilmagan
- [ ] Faqat-o'qish (guest/demo) hisob board'da sudrab bo'lmaydigan
      elementlarni ko'rmaydi/bosolmaydi
- [ ] Kartani ustunlar orasida ko'chirish bitta `PATCH` bilan bitta
      `position`/`status` yozadi
- [ ] `docs/adr/0009` migratsiyasi tugagan bo'lsa, ustunlar fixed enum'dan
      o'qiladi, `StatusSet`dan emas
- [ ] Yangi/tuzatilgan affordance uchun Playwright regressiya testi
      qo'shilgan (`frontend/e2e/`)
