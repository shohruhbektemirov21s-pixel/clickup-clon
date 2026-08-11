# Faza 10 — Xavfsizlik auditi

## Holat

**Davom etmoqda — asosiy oqimlar bir necha marta qattiq tekshirilgan,
yangi WIP ekranlar hali auditdan o'tmagan.** Commit tarixi jiddiy
xavfsizlik ishini ko'rsatadi: `89fb57c` ("close the WebSocket space leak
and finish the security follow-ups"), `0ce9c84` ("role-scoped authority,
team visibility and a hardened attack surface"), `API_CONTRACT.md`ning
v1.3.1–v1.3.4 changelog'lari (R18–R32) — email masklash, ruxsat
tekshiruvlari, `space.change_visibility` kodi, `access.revoked` kanali.
`.github/workflows/security.yml` alohida CI workflow sifatida mavjud.
`security-review` skill loyihada ishlatilgan.

Lekin `git status`dagi untracked fayllar — `apps.notifications`,
`ai-assistant.tsx`, `dashboard-view.tsx`, `planner-view.tsx`,
`notifications-page.tsx`, `workspace-realtime.tsx` — **hali birorta
xavfsizlik auditidan o'tmagan**. Bular yangi ma'lumot yo'llari (yangi
realtime event turlari, yangi frontend sahifalar) ochadi, ya'ni oldingi
audit natijalari ularni qamramaydi.

## Prompt

```
Run a security review for UzWork, scoped to what hasn't been audited yet.
Do NOT re-litigate the areas already hardened through 89fb57c and 0ce9c84
from scratch — read those commits and docs/API_CONTRACT.md's R18-R32
rulings first so you know what's already been fixed and why, then focus
new effort on what's actually new since:

- backend/apps/notifications/ (new app: models.py, events.py, services.py,
  views.py) — apply the same scrutiny that caught the WebSocket space
  leak: does every notification query/broadcast respect the same
  visible_spaces_q() / permission-code boundary as apps.tasks and
  apps.comments? A notification about a task in a space the recipient
  can no longer see is the same class of bug as the leak fixed in
  89fb57c.
- backend/apps/chat/ and backend/apps/emailcheck/ (added in 7365fb5) —
  apps/emailcheck in particular makes outbound SMTP probes
  (EMAILCHECK_HELO_HOSTNAME, settings.py:544-555) — confirm the throttle
  (emailcheck: 30/hour, settings.py:278) is actually applied and that it
  can't be used as an SSRF/probing oracle against arbitrary hosts.
- The uncommitted frontend work (ai-assistant.tsx, dashboard-view.tsx,
  planner-view.tsx, notifications-page.tsx, workspace-realtime.tsx) —
  confirm each one gates on GET workspaces/{id}/my-permissions/ and
  never renders data a read-only/guest/demo account shouldn't see. This
  is exactly the bug class the current branch
  (fix/list-view-readonly-affordances) was created to fix for the list
  view — check whether the newer screens repeat it.
- DEMO_MODE (settings.py:58-60): confirm it is still hard-disabled by
  default and that none of the new screens assume a demo account has
  write access.

Use the security-review skill/workflow this project already has
(.github/workflows/security.yml, and the security-review skill) rather
than inventing a new process.
```

## Qabul mezonlari

- [ ] `apps.notifications` xuddi `apps.tasks`dagi kabi
      `visible_spaces_q()`/ruxsat chegarasiga rioya qiladi
- [ ] `apps.emailcheck`ning SMTP probe funksiyasi tashqi SSRF vositasi
      sifatida suiiste'mol qilib bo'lmaydi (throttle + HELO/MAIL FROM
      tekshiruvi)
- [ ] Yangi (commit qilinmagan) frontend ekranlarning hech biri
      `my-permissions/`ni chetlab o'tmaydi
- [ ] `DEMO_MODE=False` bo'lganda hech bir yangi ekran demo hisobga
      yozish huquqi bor deb taxmin qilmaydi
- [ ] Topilgan har bir muammo uchun `docs/API_CONTRACT.md`da mos R-qoida
      yozilgan (mavjud R18–R32 uslubida)
