# 4 — API versioning

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

REST API'ga kelajakda buzuvchi (breaking) o'zgarishlar kiritish ehtimoli bor —
maydon nomini o'zgartirish, endpoint xatti-harakatini o'zgartirish. Qaysi
versiyalash strategiyasi (URL prefiksi, sarlavha, hech qanday versiyalash)
tanlanishi kerakligini hal qilish kerak edi.

## Qaror

Bitta global URL prefiksi — `/api/v1/` (`backend/config/urls.py`,
`docs/API_CONTRACT.md` §1.1). Endpoint-darajasida yoki resurs-darajasida alohida
versiyalash yo'q — butun API bitta versiya raqami ostida harakat qiladi.
Kontraktning o'zi (`docs/API_CONTRACT.md`) semantik versiyalanadi (hozir
**1.3.4**, sarlavhada) va har bir o'zgarish "changelog" bo'limida (§ boshida)
qayd etiladi — lekin bu hujjat versiyasi, URL versiyasi emas.

## Sabab

Loyiha bitta frontend (`frontend/`) tomonidan iste'mol qilinadi — tashqi/uchinchi
tomon iste'molchilari yo'q. Backend va frontend bitta monorepo'da birga
joylashtiriladi (`docker-compose.yml`), shuning uchun ular doim birga
deploy qilinadi: eski frontend yangi backend bilan (yoki aksincha) parallel
ishlab turishi shart emas. Bu sharoitda ko'p-versiyali URL sxemasi (`/v1/`,
`/v2/` parallel) qo'shimcha murakkablik qo'shadi, lekin foyda bermaydi.

`/api/v1/` prefiksining o'zi kelajak uchun eshikni ochiq qoldiradi — agar
tashqi iste'molchilar paydo bo'lsa, `/api/v2/` alohida qo'shilishi mumkin,
mavjud yo'llarni buzmasdan.

## Oqibatlar

**Ijobiy:** oddiy marshrutlash, bitta manba haqiqat (`API_CONTRACT.md`),
frontend/backend versiyalarini muvofiqlashtirish shart emas.

**Salbiy:** kontraktga har qanday buzuvchi o'zgarish backend va frontendni
BIR VAQTDA yangilashni talab qiladi — eski frontend build yangi backend bilan
mos kelmasligi mumkin (va aksincha). Rolling/canary deploy strategiyasi bo'lsa
bu muammo bo'ladi; hozirgi Docker Compose joylashtiruvida (`docker compose up`,
bitta atomik yangilanish) amaliy xavf past.

## Rejadan chetlashish

Yo'q — Master Plan `/api/v1/`ni ham nazarda tutadi, kod aynan shunga mos.
