# 9 — Status modeli

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

Hozirgi kodda status moslashuvchan: `StatusSet`
(`backend/apps/workspaces/models.py:386-408`) har bir `Space`ga YOKI har bir
`TaskList`ga tegishli bo'lishi mumkin (`statusset_exactly_one_owner`
check-constraint), va `Status` (`models.py:411-429`) shu to'plam ichida
erkin sondagi qatorlar — har biri `name`, `color`, `type`
(`StatusType`: `open`/`closed`, `apps/core/enums.py:80-83`), `order`,
`is_default`. `TaskList.effective_status_set` (`models.py:381-383`) list'ning
o'z to'plami bo'lmasa space'nikini meros qiladi. `Task.status`
(`apps/tasks/models.py:47-48`) shu `Status`ga `PROTECT` FK — vazifa
statusi to'plamdan tashqarida bo'lsa `clean()` xato beradi
(`tasks/models.py:142-146`).

Master Plan fixed status kodlarini talab qiladi, va foydalanuvchi TO'LIQ
o'tishni tanladi: `StatusSet`/`Status` modellari o'chadi, `Task.status`
to'g'ridan-to'g'ri 4 ta fixed kodli enum bo'ladi (masalan,
`open` / `in_progress` / `review` / `done` — aniq nomlar keyingi
implementatsiya PR'ida `API_CONTRACT.md`ga yoziladi).

## Qaror

`StatusSet` va `Status` modellari (va ular bilan bog'liq barcha API —
status CRUD endpointlari, `effective_status_set`, per-space/per-list
moslashtirish) olib tashlanadi. `Task.status` `ForeignKey("workspaces.Status")`
o'rniga fixed 4 qiymatli `TextChoices` enum (`CharField(choices=...)`)
bo'ladi, butun tizim bo'ylab bitta global kod to'plami.

## Sabab

Foydalanuvchi tanlovi: per-space moslashtiriladigan statuslar mahsulot
murakkabligini (UI'da status boshqaruv ekrani, backend'da status CRUD +
qayta tartiblash + "statusni o'chirsam ichidagi vazifalar nima bo'ladi"
degan holat mashinasi) MVP doirasi uchun oqlamaydi. Fixed kod to'plami
Kanban ustuni, filtrlash, hisobot mantig'ini soddalashtiradi — har joyda
"qaysi status to'plami ishlatilmoqda" so'rovi kerak emas.

## Nima yo'qotiladi

- **Per-space moslashtiriladigan statuslar** — har bir jamoa o'z ish
  oqimiga mos status nomlari/ranglari/soni bo'la olmaydi; hamma bitta
  global to'plamni ishlatadi.
- **Per-list status override** — `TaskList.effective_status_set` mexanizmi
  (list o'z to'plamini belgilashi mumkinligi) butunlay yo'qoladi.
- Status **rangi** va erkin **tartib** (`order`) — fixed enum bilan bular
  yo'qoladi, agar enum darajasida qattiq kodlangan rang/tartib
  qo'shilmasa.

## Migratsiya strategiyasi

1. **Xaritalash jadvali qurish** — mavjud har bir `Status` qatorini
   (`type` maydoni: `open`/`closed`) yangi 4 ta fixed kodning biriga
   moslashtirish (masalan, `type=open, is_default=True` → `open`;
   `type=closed` → `done`; oraliq nomlar — "In Progress", "Review" kabi —
   nom bo'yicha heuristika + qo'lda ko'rib chiqish ro'yxati).
2. **Ma'lumot migratsiyasi** (`RunPython`) — har bir `Task.status_id`ni
   xaritalash jadvali orqali yangi enum qiymatiga o'tkazish, ESKI
   `status` FK ustuni yonida VAQTINCHA yangi `status_code` ustuni sifatida
   (ikki bosqichli: ustun qo'shish → ma'lumot ko'chirish → eski ustun va
   `StatusSet`/`Status` jadvallarini o'chirish — uchta alohida migratsiya,
   0006-ADR'dagi "bitta PR — bitta migratsiya" qoidasiga muvofiq har biri
   alohida PR).
3. **`API_CONTRACT.md`ni yangilash** — status CRUD endpointlarini olib
   tashlash, `Task.status`ning yangi shaklini (`enum`, endi obyekt emas)
   hujjatlashtirish, buzuvchi o'zgarish sifatida changelog yozish.
4. **Frontend** — status tanlagich UI'sini moslashuvchan ro'yxatdan fixed
   4 variantli komponentga soddalashtirish; `frontend/src/types/api.ts`dagi
   `Status`/`StatusSet` tiplarini olib tashlash.

## Oqibatlar

**Ijobiy:** butun status bilan bog'liq kod yuzasi (backend CRUD, frontend
boshqaruv UI, validatsiya) sezilarli qisqaradi; Kanban/filtr mantiq
soddalashadi.

**Salbiy:** mahsulot moslashuvchanligi yo'qoladi — kelajakda "jamoa o'z
statusini xohlaydi" degan haqiqiy talab paydo bo'lsa, bu qaror teskarisiga
qaytariladi (yangi ADR + StatusSet/Status'ni qayta qurish). Migratsiya
qaytarilmas ma'lumot yo'qotishga olib keladi (status rangi/erkin nomi) —
agar kimdir keyinroq "aslida rang kerak ekan" desa, eski qiymatlar
qaytarib bo'lmaydi (agar migratsiya arxiv jadvaliga zaxira qoldirmasa).

## Rejadan chetlashish

Yo'q — bu reja bilan mos, ammo rejadan HAM kattaroq qadam: reja "fixed
kodlarni talab qiladi" deydi, foydalanuvchi esa qisman emas, TO'LIQ
o'tishni tanladi (StatusSet/Status modellarini butunlay olib tashlash,
faqat yangi loyihalar uchun emas).
