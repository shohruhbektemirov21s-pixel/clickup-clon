# 3 — Soft delete

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

Ba'zi obyektlarni o'chirishdan keyin ham vaqtinchalik saqlab qolish (audit,
"undo", bog'liq yozuvlarni saqlash) foydali, lekin har bir modelga buni
qo'llash kod va so'rov murakkabligini oshiradi. Qaysi modellar soft-delete,
qaysilari qattiq o'chishi kerakligini aniq belgilash kerak.

## Qaror

`SoftDeleteModel` (`backend/apps/core/models.py:46-64`) — `deleted_at` maydoni +
`AliveManager` (standart, faqat tirik qatorlar) + `all_objects` (hammasi) —
faqat UCH modelga qo'llangan:

- `Task` — `backend/apps/tasks/models.py:43`
- `Comment` — `backend/apps/comments/models.py:7`
- `Message` (chat) — `backend/apps/chat/models.py:109`

Qolgan barcha modellar — `Workspace`, `WorkspaceMember`, `RolePermission`,
`Invitation`, `Space`, `SpaceMember`, `Folder`, `TaskList`, `StatusSet`, `Status`
(`backend/apps/workspaces/models.py`), shuningdek `Tag`, `TaskAssignee`,
`TaskWatcher`, `TaskActivity`, `TaskAttachment`, `TaskTag`
(`backend/apps/tasks/models.py`) — soft-delete emas: ular `models.CASCADE` orqali
qattiq o'chadi (yoki umuman o'chirish endpointiga ega emas).

## Sabab

Soft-delete foydali bo'lgan joy — foydalanuvchi tez-tez yaratadigan/o'chiradigan,
tarixiy qiymatga ega bo'lgan mazmun birliklari: vazifa, izoh, chat xabari. Ularni
qayta tiklash yoki keyinroq audit qilish real stsenariy.

Ierarxiya (`Workspace`→`Space`→`Folder`→`TaskList`) va a'zolik/ruxsat modellari
esa strukturaviy: ularni o'chirish kam sodir bo'ladi, odatda "chuqur" kaskad
bilan birga keladi (masalan, bo'shliqni o'chirish — ichidagi papka/ro'yxat/
vazifalarni ham olib tashlaydi) va soft-delete qilinsa har bir so'rov
(`visible_spaces_q()`, ruxsat tekshiruvi) "o'chirilgan lekin hali bazada"
holatini hisobga olishi kerak bo'lardi — bu ruxsat qatlamini murakkablashtiradi
va xato qilish xavfini oshiradi. `Status`/`StatusSet` esa hozirda 0009-ADR bo'yicha
butunlay bekor qilinmoqda, shuning uchun ularga soft-delete qo'shishning ma'nosi
yo'q.

## Oqibatlar

**Ijobiy:** uchta "tez-tez o'zgaradigan" model uchun tiklash/audit imkoniyati bor;
qolganlarida so'rov qatlami (`AliveManager` filtri, `.alive()`/`.dead()`) shart
emas — kod soddaroq.

**Salbiy:** vazifa/izoh/xabar o'chirilganda bog'liq `CASCADE` yozuvlar (masalan,
`TaskAttachment`, `TaskActivity`) `Task`ning o'zi soft-delete bo'lsa ham qattiq
saqlanib qoladi — chunki ular `Task`ga FK orqali bog'langan va `Task.delete()`
(`core/models.py:59-61`) faqat `deleted_at`ni yozadi, Django CASCADE ishga
tushmaydi. Bu ataylab shunday (bola yozuvlar ota bilan birga "yashaydi"), lekin
bola yozuvlarni tozalash uchun alohida tozalash joyi (masalan, davriy job) yo'q —
hozircha kerak emas, chunki `Task` qattiq o'chirilmaydi.

## Rejadan chetlashish

Yo'q.
