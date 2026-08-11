# Faza 07 — Realtime (Channels/WebSocket)

## Holat

**Bajarildi, va bir necha marta xavfsizlik bo'yicha qayta ko'rib chiqilgan.**
`apps.realtime` — consumers, routing, broadcast helpers
(`backend/apps/realtime/events.py`, `middleware.py`). `docs/API_CONTRACT.md`
§15–§16 to'liq tasvirlaydi: space-scoped guruhlar (`space.<id>`),
`workspace.<id>` faqat `permission.updated` uchun, `user.<id>` shaxsiy
kanal `access.revoked` uchun. Commit tarixi realtime xavfsizligining necha
marta chuqurlashtirilganini ko'rsatadi: `89fb57c` ("close the WebSocket
space leak"), undan oldin R25–R32 qoidalari (`API_CONTRACT.md` v1.3.4
changelog). `apps.notifications` (yangi ilova, `backend/apps/notifications/`)
ham shu infratuzilmaga ulanadi.

`frontend/src/components/shell/workspace-realtime.tsx` va
`frontend/src/components/shell/notification-bell.tsx` **hali commit
qilinmagan** (untracked) — bular yangi ekranlarni (dashboard, ai, planner,
notifications) realtime kanalga ulaydi va hali audit qilinmagan.

## Prompt

```
Verify and finish realtime for UzWork. The core WebSocket/Channels layer
(backend/apps/realtime/) is DONE and has already been hardened through
several security passes — do not restructure events.py's group scoping
without re-reading docs/API_CONTRACT.md §15 first (space.<id> vs
workspace.<id> vs user.<id> each carry a specific, narrow authorization
meaning; conflating them re-opens the leak fixed in 89fb57c).

What genuinely needs review here: frontend/src/components/shell/
workspace-realtime.tsx and notification-bell.tsx are UNCOMMITTED — they
wire the newer screens (dashboard, ai, planner, notifications — see
06-dashboard.md and 09-ai.md) to the realtime channel. Audit them against
the same rules the rest of the frontend already follows
(frontend/src/hooks/use-workspace-channel.ts is the reference
implementation):
- Does the client resubscribe/refetch on permission.updated and
  access.revoked, per API_CONTRACT §15.3?
- Does it suppress echoing the actor's own events (X-Client-Id header,
  see settings.py:333-337 and CORS_ALLOW_HEADERS)?
- Does apps.notifications' events.py follow the same "never broadcast
  from a view, only from services" convention as apps.tasks?

Check apps/notifications specifically since it is the newest app in this
layer (backend/apps/notifications/events.py, services.py) — confirm it
was built against the same space-scoping rules as apps/tasks and
apps/comments, not against an older/looser understanding of the group
model.
```

## Qabul mezonlari

- [ ] Broadcast'lar `apps/realtime/events.py`dagi guruh chegaralariga rioya
      qiladi (`space.<id>`, `workspace.<id>`, `user.<id>` aralashmagan)
- [ ] `apps.notifications` eventlari servis qatlamidan chiqadi, view'dan
      emas
- [ ] Frontend `permission.updated`/`access.revoked`da qayta ulanadi/
      so'raydi
- [ ] `X-Client-Id` orqali o'z eventini o'zi ko'rmaydi
- [ ] `workspace-realtime.tsx`/`notification-bell.tsx` commit qilingan va
      review'dan o'tgan
