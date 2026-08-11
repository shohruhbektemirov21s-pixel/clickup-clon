# Faza promptlari

Bu papka "UzWork Master Plan v2" §17 dagi faza promptlarini saqlaydi — har bir
fayl bitta fazani boshlashda yangi agent sessiyasiga beriladigan to'liq prompt.

## Nega bu fayllar boshqacha

Master Plan promptlari **noldan boshlanadigan** loyiha uchun yozilgan. Bu loyiha
**allaqachon mavjud** va ko'p fazalar to'liq yoki qisman bajarilgan — ba'zilari
hatto bir necha marta qayta ko'rib chiqilgan (masalan, realtime xavfsizligi
uch marta tuzatilgan: `89fb57c`, `0ce9c84`, `e2c4f62`). Agar promptni o'zgarishsiz
bersangiz, yangi agent "noldan qur" deb tushunib, ishlab turgan kodni qayta
yozishga urinishi mumkin — bu eng qimmat va eng xavfli xato.

Shuning uchun har bir fayl **"Holat"** blokidan boshlanadi: bu faza hozir qay
darajada bajarilgan, qaysi fayllarga qarash kerak, va prompt matni "qur" emas
"tekshir, yakunla, kengaytir" ohangida yozilgan (agar faza allaqachon bajarilgan
bo'lsa).

## Qanday ishlatiladi

1. **Yangi sessiya oching** (yoki joriy sessiyada `/clear` bering) — faza
   promptlari mustaqil ishlashi uchun mo'ljallangan, oldingi suhbat konteksti
   kerak emas (aksincha, eski kontekst chalkashtirishi mumkin).
2. Tegishli `NN-fayl.md`ning **butun mazmunini** nusxalab, agentga bering.
   Fayl nomidagi raqam tavsiya etilgan tartib — lekin fazalar ko'p jihatdan
   mustaqil, kerak bo'lsa tartibni almashtirish mumkin (masalan, `06-dashboard`
   `05-kanban`dan oldin bajarilishi mumkin).
3. Agent ishini tugatgach, **"Qabul mezonlari"** checklist'ini qo'lda (yoki
   `code-review` skill orqali) tekshiring.
4. Agar faza holati o'zgargan bo'lsa (masalan, "bajarilmagan" dan "bajarildi"ga
   o'tdi), shu faylning **Holat** blokini yangilang — bu hujjat yashab turishi
   kerak, bir martalik artefakt emas.

## Review halqasi

Har bir faza uchun tavsiya etilgan oqim:

```
faza prompti → agent ishlaydi → code-review skill (yoki qo'lda ko'rib chiqish)
   → topilgan muammolar tuzatiladi → Qabul mezonlari tekshiriladi
   → shu faylning Holat bloki yangilanadi → keyingi faza
```

Katta yoki xavfli fazalar uchun (masalan, `09-status-modeli` bilan bog'liq
migratsiya, yoki `10-security-audit`) — natijani darhol `main`ga
birlashtirmasdan, alohida branch/PR orqali ko'rib chiqing.

## Indeks

| Fayl | Faza | Hozirgi holat (qisqacha) |
|---|---|---|
| [00-architect.md](00-architect.md) | Arxitektura hujjatlari (ADR + promptlar) | Bajarilmoqda — shu ish |
| [01-backend-foundation.md](01-backend-foundation.md) | Django loyiha skeleti, auth, core | Bajarildi |
| [02-hierarchy.md](02-hierarchy.md) | Workspace/Space/Folder/List/ruxsat | Bajarildi (Status modeli 0009-ADR bo'yicha o'zgaradi) |
| [03-task.md](03-task.md) | Task, tag, comment, attachment, activity | Bajarildi |
| [04-frontend-foundation.md](04-frontend-foundation.md) | React/Vite SPA shell, auth, TanStack Query | Bajarildi |
| [05-kanban.md](05-kanban.md) | Board/Kanban, @dnd-kit | Bajarildi |
| [06-dashboard.md](06-dashboard.md) | Dashboard ekrani | Ishlanmoqda — commit qilinmagan |
| [07-realtime.md](07-realtime.md) | Channels/WebSocket | Bajarildi, xavfsizlik bo'yicha qayta ko'rib chiqilgan |
| [08-devops.md](08-devops.md) | Docker, CI/CD | Bajarildi |
| [09-ai.md](09-ai.md) | AI yordamchi | Qisman — faqat frontend evristikasi, backend AI yo'q |
| [10-security-audit.md](10-security-audit.md) | Xavfsizlik auditi | Davom etmoqda — yangi WIP ekranlar hali auditdan o'tmagan |
| [11-qa.md](11-qa.md) | QA / E2E | Qisman — asosiy oqimlar qamrovda, yangi ekranlar yo'q |
| [12-final-release.md](12-final-release.md) | Yakuniy chiqarish | Boshlanmagan |
