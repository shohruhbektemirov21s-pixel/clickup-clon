# Faza 02 — Workspace ierarxiyasi va ruxsatlar

## Holat

**Bajarildi**, bitta rejalashtirilgan o'zgarish bilan. `apps.workspaces`
(`backend/apps/workspaces/models.py`) — `Workspace`, `WorkspaceMember`,
`RolePermission`, `Invitation`, `Space`, `SpaceMember`, `Folder`, `TaskList`,
`StatusSet`, `Status` — hammasi mavjud, `docs/adr/0007-app-strukturasi.md`da
qayd etilganidek bitta ilovada (`docs/API_CONTRACT.md` R1 qarori). Ruxsat
matritsasi granular (permission-code, rol emas) va `DESIGN_PERMISSIONS.md`
§A–D.5 ga mos. Taklif (invitation) oqimi token-asosida ishlaydi
(`docs/adr/0005-email-backend.md`) — email yuborilmaydi.

**Kutilayotgan o'zgarish:** `docs/adr/0009-status-modeli.md` — `StatusSet`/
`Status` bekor qilinadi, `Task.status` fixed 4-kodli enumga o'tadi. Bu ADR
hali amalga oshirilmagan (faqat qaror qilingan) — status bilan bog'liq
kod hozircha shu faylda tasvirlangan holatda ishlaydi.

## Prompt

```
Verify and finish the workspace hierarchy for UzWork (backend/apps/workspaces).
This phase is DONE for Workspace/Member/RolePermission/Invitation/Space/
SpaceMember/Folder/TaskList — audit against docs/API_CONTRACT.md (member,
space, folder, list endpoints) and docs/DESIGN_PERMISSIONS.md, do not
rebuild working CRUD.

One piece is explicitly PENDING, not done: docs/adr/0009-status-modeli.md
records the accepted decision to delete StatusSet/Status entirely and
replace Task.status with a fixed 4-value enum. If you are asked to execute
that migration:
- Follow the three-migration sequence in the ADR's "Migratsiya strategiyasi"
  section (add column -> backfill via mapping table -> drop old FK and the
  StatusSet/Status models), one migration per PR per docs/adr/0006.
- Update docs/API_CONTRACT.md in the same PR as the code change that makes
  it true (remove status CRUD endpoints, redocument Task.status shape).
- Update frontend/src/types/api.ts and any status-picker UI as a
  coordinated follow-up (see 05-kanban.md, 06-dashboard.md).
- This is a breaking, irreversible data migration — get it reviewed before
  merging, and confirm the mapping table handles every existing status
  `type`/`name` combination in seed/demo data (see backend/apps/*/management
  seed_demo command) before running the backfill.

Otherwise, treat this phase as an audit: confirm apps/core/access.py's
visible_spaces_q() and require_space_perm() are what every workspaces/
view actually calls, and that R20's staged visibility rule still holds.
```

## Qabul mezonlari

- [ ] `Workspace`/`Space`/`Folder`/`TaskList`/`SpaceMember`/`Invitation`
      CRUD'i `docs/API_CONTRACT.md` bilan bir xil
- [ ] Har bir view ruxsat kodini `require_*_perm` orqali tekshiradi, rol
      nomiga qarab shoxlanmagan
- [ ] `Status`ni fixed enumga o'tkazish boshlangan bo'lsa, uch bosqichli
      migratsiya alohida PR'larda va `docs/API_CONTRACT.md` shu PR'da
      yangilangan
- [ ] `frontend/src/types/api.ts` backend o'zgarishi bilan sinxron
- [ ] Taklif oqimi token orqali ishlaydi, email yuborishga urinish yo'q
      (`docs/adr/0005`)
