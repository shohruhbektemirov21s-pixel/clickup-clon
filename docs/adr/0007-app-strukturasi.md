# 7 — App strukturasi

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

`docs/DATA_MODEL.md` (va Master Plan'ning tavsiya qiladigan "Variant B"si)
ierarxiya modellarini (`Space`, `Folder`, `TaskList`/`List`, `StatusSet`,
`Status`) alohida `apps.projects` (yoki `apps.spaces`) ilovasida ko'radi.
Hozirgi kodda ular `apps.workspaces` ichida joylashgan
(`backend/apps/workspaces/models.py:201,282,314,386,411`) — `Workspace`,
`WorkspaceMember`, `RolePermission`, `Invitation` bilan bir qatorda, bitta
faylda.

## Qaror

Ierarxiya modellari `apps.workspaces` ichida qoladi. Yangi `apps.projects`
(yoki `apps.spaces`) ilovasi yaratilmaydi.

## Sabab

Bu qaror allaqachon rasman qabul qilingan va hujjatlashtirilgan —
`docs/API_CONTRACT.md`ning R1 qoidasi (§17, "Rulings" jadvali,
`API_CONTRACT.md:1403`):

> `R1 | DATA_MODEL puts Space/Folder/TaskList/StatusSet/Status in an
> apps.spaces app (+ apps.core); CLAUDE.md puts them in apps.workspaces |
> **CLAUDE.md wins** — all hierarchy models live in apps.workspaces.
> No API-visible impact.`

`CLAUDE.md`ning "Layout" bo'limi ham buni aniq belgilaydi:
`apps/workspaces/ — Workspace, Member, RolePermission, Invitation, Space,
SpaceMember, Folder, List, StatusSet, Status`. Ya'ni loyihaning o'zi (CLAUDE.md)
va kontrakt (`API_CONTRACT.md`) allaqachon `DATA_MODEL.md`dagi (va shu
sababli Master Plan'dagi Variant B) taklifdan farqli, ammo bir-biriga mos
qarorni qabul qilgan. Bu ADR shu mavjud qarorni rasmiylashtiradi, yangi
qaror qabul qilmaydi.

Amaliy sabab: `Space`/`Folder`/`TaskList` ierarxiyasi `Workspace`ning bir
qismi sifatida ko'riladi (ruxsat, a'zolik va ko'rinuvchanlik hammasi
`Workspace` konteksti ichida hisoblanadi — `apps/core/access.py`), shuning
uchun ularni bitta ilovada saqlash import doiralanishini (circular import)
oldini oladi va `WorkspaceMember`/`RolePermission` bilan bir xil faylda
ruxsat mantiqini kuzatishni osonlashtiradi.

## Oqibatlar

**Ijobiy:** `DATA_MODEL.md` va kod orasidagi nomuvofiqlik allaqachon
kontraktda hal qilingan (R1) — bu ADR shunchaki uni arxitektura jurnaliga
ko'chiradi. Yangi ilova qo'shish, import qayta tashkil qilish kabi qo'shimcha
migratsiya ishi kerak emas.

**Salbiy:** `apps/workspaces/models.py` katta fayl bo'lib qolmoqda (410+
qator, 10 ta model) — bitta ilovada juda ko'p mas'uliyat (a'zolik, ruxsat,
taklif, ierarxiya, status) jamlangan. Kelajakda fayl davom etib o'ssa,
ichki modul bo'linishi (masalan, `apps/workspaces/hierarchy.py`,
`apps/workspaces/membership.py`) ko'rib chiqilishi kerak bo'lishi mumkin —
bu Django ilova chegarasini o'zgartirmaydi, faqat fayl darajasida.

## Rejadan chetlashish

**Bor.** Master Plan (va uning asosidagi `DATA_MODEL.md`) `apps.projects`
(Variant B)ni tavsiya qiladi; loyiha haqiqatda `apps.workspaces`
(mono-ilova, "Variant A"ga yaqin) yo'lidan bormoqda. Sabab yuqorida: bu
tanlov `CLAUDE.md` va `API_CONTRACT.md` R1 orqali rejadan OLDIN rasmiylashtirilgan
va butun kod bazasi (import yo'llari, testlar, admin ro'yxatga olish) shunga
qurilgan. Reja bilan qayta muvofiqlashtirish endi katta qayta yozishni
talab qiladi va foyda keltirmaydi — API sirtiga ta'siri yo'q (R1: "No
API-visible impact").
