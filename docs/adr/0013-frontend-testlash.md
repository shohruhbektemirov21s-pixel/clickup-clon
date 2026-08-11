# 13 — Frontend testlash: vitest + Playwright

Holat: Qabul qilindi (vitest hali ishga tushirilmagan) | Sana: 2026-08-11

## Kontekst

Frontend'da bugun **birorta ham unit/komponent testi yo'q**. `frontend/src`
ostida bitta `*.test.ts(x)` fayl topilmaydi; yagona test to'plami — Playwright
E2E (`frontend/e2e/`, 7 ta spec: `auth`, `board-columns`, `dashboard`,
`member-profile`, `permissions`, `realtime`, `smoke`, ~26 test). CI'ning
`frontend` job'i (`.github/workflows/ci.yml:345-387`) faqat `npm ci`, lint,
`tsc --noEmit` va build'ni bajaradi — unit test qadami yo'q.

Reja (§3) frontend uchun **vitest** ni ko'rsatadi, va §17.5 optimistik
yangilanish rollback'ini test bilan qamrashni talab qiladi.

Playwright allaqachon jiddiy sozlangan va uni almashtirish niyati yo'q:
`frontend/playwright.config.ts:24-26` (`testDir: "./e2e"`, global setup/teardown),
`:30-31` `fullyParallel: false` + `workers: 1` (izoh `:27-29` — realtime
testlari ikkita brauzer konteksti ushlaydi, parallellik presence hisoblagichini
buzadi), `:55-60` bitta `chromium` proyekti. Eng muhimi `:3-22` dagi izoh:
`webServer` **ataylab yo'q**, chunki backend ko'tarilishi `migrate` →
`seed_demo` → Daphne zanjiri va Playwright o'ldiradigan jarayonlar loglarini
yo'qotadi.

Optimistik mutatsiyalar `frontend/src/hooks/mutations.ts` (1071 qator) da
to'plangan, lekin ularning **faqat to'rttasida** haqiqiy rollback yo'li bor:
`useUpdateTask` (`:171-230`, ikkita keshni qaytaradi), `useMoveTask`
(`:286-333`, `position_conflict` da jimgina refetch bilan tiklanadi),
`useDeleteTask` (`:232-251`) va `useMarkNotificationRead` (`:622-660`,
o'qilmaganlar badge'ini ham qaytaradi). Qolgan ~30 mutatsiya `onMutate` siz,
faqat `onError: toast.error` bilan ishlaydi. Ya'ni rollback testlarining
qamrovi aniq va tor.

## Qaror

Frontend ikki qatlamda testlanadi va chegara qat'iy:

**vitest** — unit, hook va komponent testlari. Jumladan:

- sof funksiyalar va yordamchilar (`src/lib/`), fraksional pozitsiya
  hisoblari, format/parse;
- TanStack Query hooklari, **ayniqsa optimistik yangilanish va rollback**
  (§17.5): `onMutate` keshni to'g'ri o'zgartirdimi, `onError` uni **aynan**
  oldingi holatga qaytardimi, `useMoveTask` dagi `position_conflict`
  toast emas refetch bilan tiklanadimi;
- WebSocket hodisalarining kesh reduksiyasi (`use-list-channel.ts`,
  `use-workspace-channel.ts`, `use-chat-channel.ts`) — soket **soxta**,
  haqiqiy server emas;
- ruxsat gating helperi (`can()`) — qaysi affordance ko'rinadi;
- xavfsizlik sarlavhalari pariteti (`security-headers.ts` ↔ nginx shabloni,
  ADR 0011).

Muhit `vite.config.ts:49-58` da: `environment: "jsdom"` (`:50`),
`globals: true` (`:51`), `setupFiles: ["./src/test/setup.ts"]` (`:52`),
`include: ["src/**/*.test.{ts,tsx}"]` (`:53`), `exclude` ichida `e2e/**`
(`:55`) — ya'ni Playwright specslari vitest'ga hech qachon tushmaydi.

**Playwright** — haqiqiy stack ustidagi oqimlar. Real brauzer, real Daphne,
real Postgres, real Redis, `seed_demo` ma'lumoti. Bu qatlam faqat
**foydalanuvchi oqimini** tekshiradi: kirish, navigatsiya, ruxsat matritsasi,
real vaqtli tarqalish, faqat-o'qish hisob uchun affordance gating'i.

Chegara qoidasi: **agar test uchun haqiqiy backend kerak bo'lmasa, u
vitest'da yoziladi.** Playwright'ga faqat "butun zanjir birga ishlaydimi"
savoli qoladi.

## Sabab

Bugungi holat piramidani teskari qo'ygan: yagona qatlam eng qimmat, eng sekin
va eng mo'rt qatlam. Optimistik rollback kabi mantiq E2E'da deyarli
tekshirib bo'lmaydi — server xatosini ishonchli chaqirish uchun tarmoqni
sun'iy buzish kerak, holbuki vitest'da bu bitta rad etilgan promise.

vitest tanlanishining ikkinchi sababi — ADR 0011. Vite konfiguratsiyasi
allaqachon bor, vitest o'sha konfiguratsiyani (alias, plugin, env) qayta
ishlatadi; Jest qo'shilsa, ikkinchi transform zanjiri va ikkinchi modul
qarori paydo bo'lardi.

Playwright saqlanadi, chunki u allaqachon regressiyalarni ushlab kelmoqda —
masalan `e2c4f62` ("readonly hisob uchun list-view affordance regressiyasi")
aynan shu to'plam bilan qamralgan (`e2e/permissions.spec.ts:218,236`).

## Oqibatlar

**Ijobiy:** rollback, kesh reduksiyasi va gating mantiqi soniyalarda,
deterministik tekshiriladi; E2E to'plami o'smaydi (u 7 spec / ~26 test
darajasida qolib, sekinlashmaydi); `vite.config.ts` bitta konfiguratsiya
bo'lib qoladi.

**Salbiy:** ikkita test harness'ni bilish kerak, va "bu test qayerga?"
savoli har safar tug'iladi — shuning uchun yuqoridagi chegara qoidasi qat'iy
yozildi. jsdom haqiqiy brauzer emas: layout, `IntersectionObserver`, drag &
drop pointer hodisalari kabi narsalar u yerda ishonchli emas — bunday
narsalar Playwright'da qoladi.

**Salbiy — hozircha nol amalga oshirilgan.** `vitest`, `jsdom`,
`@testing-library/*` `frontend/package.json:44-46,55,60` da **bor**, lekin:
`package.json:5-13` da `test` skripti yo'q, `vite.config.ts:52` ko'rsatgan
`src/test/setup.ts` fayli yo'q, birorta test fayli yo'q, va `ci.yml` da
`vitest` so'zi umuman uchramaydi. Ya'ni bu ADR hozircha **niyat**, darvoza
emas.

## Rejadan chetlashish

Yo'q. Reja §3 vitest'ni ko'rsatadi; Playwright rejaga qo'shimcha emas —
u allaqachon mavjud va CI'da majburiy (`ci.yml:392-561`), shuning uchun uni
olib tashlash regressiya bo'lardi.

## Ochiq ish

1. `frontend/src/test/setup.ts` (testing-library matcher'lari, `restoreMocks`).
2. `package.json` ga `"test": "vitest run"` va `"test:watch": "vitest"`.
3. Birinchi to'plam: `mutations.ts` dagi to'rtta rollback yo'li
   (`:171-230`, `:232-251`, `:286-333`, `:622-660`).
4. `ci.yml` ning `frontend` job'iga (`:345-387`) `npm run test` qadami —
   lint va typecheck orasiga.
5. Coverage darvozasi: birinchi o'lchovdan keyin, backend'dagi kabi
   ratchet sifatida (`backend/.coveragerc:47` uslubida) — avval o'lchash,
   keyin qulflash.
