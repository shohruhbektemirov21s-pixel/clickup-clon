# Faza 03 — Task, izoh, biriktirma, faollik

## Holat

**Bajarildi.** `apps.tasks` (`backend/apps/tasks/models.py`) — `Task`
(soft-delete, `PositionedModel`, `docs/adr/0003`), `Tag`, `TaskAssignee`,
`TaskWatcher`, `TaskActivity`, `TaskAttachment`, `TaskTag`. Drag & drop
tartiblash fraksional-indeks (`position`, `docs/DATA_MODEL.md` §8) orqali —
qatorlarni qayta raqamlamaydi. `apps.comments` — `Comment` (soft-delete).
Biriktirma yuklash mahalliy diskka (`docs/adr/0001-fayl-saqlash.md`),
`MAX_ATTACHMENT_MB=10` chegara bilan. `API_CONTRACT.md` R24: tugallangan
vazifa ham fayl qabul qiladi.

## Prompt

```
Verify and finish the task domain for UzWork (backend/apps/tasks,
backend/apps/comments). This phase is DONE — audit against
docs/API_CONTRACT.md's task/comment/attachment/activity endpoints and
docs/DATA_MODEL.md §8 (position/fractional-index ordering), do not
rewrite working code.

Check specifically:
- Task.position ordering: confirm moves write a single fractional position
  (backend/apps/tasks/services.py), never renumber every row.
- Task.status FK: this couples to docs/adr/0009-status-modeli.md — if that
  migration is in flight, Task's status handling is the primary blast
  radius (backend/apps/tasks/models.py:47-48, :142-146's clean() check).
- TaskAttachment size/type validation matches MAX_ATTACHMENT_MB
  (settings.py) and docs/adr/0001's local-disk assumption — do not assume
  cloud storage exists.
- SoftDeleteModel usage: Task and Comment use it (docs/adr/0003); child
  rows (TaskAttachment, TaskActivity, TaskAssignee, TaskWatcher, TaskTag)
  do not and are never expected to survive a hard-delete of their parent
  outside of Task's own soft-delete path.
- Realtime events (task.*) are emitted from services.py, never from views
  directly (CLAUDE.md convention) — confirm this still holds for any new
  mutation path you touch.

If a gap is found, fix it narrowly and update docs/API_CONTRACT.md in the
same commit if the fix changes observable behavior.
```

## Qabul mezonlari

- [ ] Vazifa ko'chirilganda faqat bitta `position` yoziladi, qatorlar
      qayta raqamlanmaydi
- [ ] Biriktirma hajmi/soni chegaralari `settings.py` bilan mos
      (`MAX_ATTACHMENT_MB`, `DATA_UPLOAD_MAX_NUMBER_FILES`)
- [ ] Har bir task/comment/attachment mutatsiyasi tegishli realtime event
      chiqaradi (`apps/realtime/events.py` orqali, view'dan emas)
- [ ] Tugallangan vazifa ham fayl biriktirishni qabul qiladi (R24)
- [ ] Soft-delete faqat `Task`/`Comment`da, boshqa yerda yo'q
      (`docs/adr/0003`)
