# Arxitektura qarorlari (ADR)

Bu papka loyihaning bog'lovchi arxitektura qarorlarini qayd etadi — "UzWork Master
Plan v2" §8 talabiga ko'ra. Har bir ADR bitta qarorni tasvirlaydi: muammo nima edi,
nima qilindi, nega, va nimaga arzon bo'lmadi.

## Indeks

| # | Fayl | Qaror |
|---|---|---|
| 0001 | [fayl-saqlash.md](0001-fayl-saqlash.md) | Biriktirmalar mahalliy disk (`FileSystemStorage`) da saqlanadi, bulut obyekt-do'koni yo'q |
| 0002 | [timezone.md](0002-timezone.md) | `TIME_ZONE = "Asia/Tashkent"`, `USE_TZ = True` — DB'da UTC, ko'rsatishda mahalliy |
| 0003 | [soft-delete.md](0003-soft-delete.md) | Soft delete faqat `Task`, `Comment`, `Message` uchun; ierarxiya va a'zolik qattiq o'chadi |
| 0004 | [api-versioning.md](0004-api-versioning.md) | Bitta global prefiks — `/api/v1/`, versiya raqami emas endpoint-darajasida |
| 0005 | [email-backend.md](0005-email-backend.md) | Email backend sozlanmagan; taklif token/havola orqali, email yubormasdan ishlaydi |
| 0006 | [migratsiya-siyosati.md](0006-migratsiya-siyosati.md) | CI'da `makemigrations --check` darvozasi + "bitta PR — bitta migratsiya" qoidasi |
| 0007 | [app-strukturasi.md](0007-app-strukturasi.md) | Ierarxiya modellari (`Space`/`Folder`/`TaskList`/`Status*`) `apps.workspaces` ichida, reja tavsiya qilgan `apps.projects` (Variant B) emas |
| 0008 | [pagination-rate-limit.md](0008-pagination-rate-limit.md) | Sahifalash 25/100 (standart/maksimal), throttle stavkalari endpoint-sinf bo'yicha alohida |
| 0009 | [status-modeli.md](0009-status-modeli.md) | `StatusSet`/`Status` bekor qilinadi, `Task.status` 4 ta fixed kodli enum bo'ladi |
| 0010 | [api-tiplari.md](0010-api-tiplari.md) | ~~Codegen yo'q; `api/openapi.json` artefakt + CI drift-check qo'shiladi~~ — **bekor qilindi (0015)** |
| 0011 | [frontend-framework.md](0011-frontend-framework.md) | Frontend Next.js 16 App Router'dan React + Vite + React Router SPA'ga ko'chadi; SSR yo'q |
| 0012 | [fon-vazifalari.md](0012-fon-vazifalari.md) | Fon vazifalari — Celery + Redis; broker `REDIS_URL`, brokersiz dev'da `TASK_ALWAYS_EAGER` |
| 0013 | [frontend-testlash.md](0013-frontend-testlash.md) | vitest — unit/hook/komponent (rollback ham); Playwright — haqiqiy stack ustidagi oqimlar |
| 0014 | [mahsulot-nomi.md](0014-mahsulot-nomi.md) | Mahsulot nomi **UzWork**; ClickUp kodi/assetlari/logotipi ko'chirilmaydi, UX naqshlari ilhom sifatida ochiq |
| 0015 | [api-tiplari-codegen.md](0015-api-tiplari-codegen.md) | `openapi-typescript` codegen → `openapi.d.ts`, `api.ts` yupqa qayta-eksport (hali amalga oshirilmagan) |

## Yangi ADR qo'shish

1. Keyingi raqamni ol (4 xonali, nol bilan to'ldirilgan: `0016`).
2. `docs/adr/000N-qisqa-nom.md` fayl yarat, quyidagi formatda:

   ```markdown
   # N — Qaror sarlavhasi

   Holat: Qabul qilindi | Sana: YYYY-MM-DD

   ## Kontekst
   ## Qaror
   ## Sabab
   ## Oqibatlar
   ## Rejadan chetlashish   (agar bo'lsa)
   ```

3. Qarorni kod bilan bog'la — taxmin emas, `fayl:qator` keltir.
4. Shu jadvalga bitta qator qo'sh.
5. Eski ADR endi noto'g'ri bo'lsa — o'chirma, `Holat: Bekor qilindi (N# bilan almashtirildi)`
   deb yangila va yangisiga havola qo'y.
