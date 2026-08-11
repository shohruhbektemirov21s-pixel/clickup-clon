# 11 — Frontend framework: Next.js → React + Vite

Holat: Qabul qilindi va **bajarildi** | Sana: 2026-08-11

## Kontekst

Frontend Next.js 16 App Router'da qurilgan: `frontend/next.config.ts` (91 qator),
`frontend/src/app/` ostida 26 ta `page.tsx`/`layout.tsx`, va 29 ta fayl
`next/*` dan import qiladi (20 tasi `next/link`, 16 tasi `next/navigation`).
Butun daraxtda atigi bitta `"use client"` bor —
`frontend/src/app/providers.tsx:1` — ya'ni deyarli hamma sahifa server
komponenti.

Reja (§3) frontend uchun **React + Vite** ni talab qiladi, va foydalanuvchi
ko'chishni tanladi. Bu ADR shu tanlovni va uning narxini qayd etadi.

Hozirgi holat (2026-08-11, ishchi daraxt): ko'chish **boshlangan, tugamagan**.
`frontend/vite.config.ts`, `frontend/index.html`,
`frontend/security-headers.ts` va `frontend/src/routes/{layouts,pages}.tsx`
paydo bo'ldi; `next` esa `frontend/package.json` ning dependency'laridan
(`:14-39`) butunlay olib tashlangan. Ayni paytda `package.json:6-8` hali
`"dev": "next dev"`, `"build": "next build"`, `"start": "next start"` deydi,
`frontend/index.html:24` mavjud bo'lmagan `/src/main.tsx` ga ishora qiladi, va
`createBrowserRouter`/`<RouterProvider>` hali hech qayerda chaqirilmagan. Ya'ni
repo hozir **ikkala stack orasida osilib turibdi** va `npm ci` dan keyin
lint/typecheck/build joblari qizil.

## Qaror

Frontend **React 19 + Vite + React Router** asosidagi **client-rendered SPA**
ga o'tadi. SSR yo'q: barcha ma'lumot brauzerdan `/api/v1/` orqali olinadi.

- Marshrutlash: `src/app/` fayl-marshrutlari o'rniga React Router route
  jadvali (`frontend/src/routes/`).
- Sahifa sarlavhasi: `metadata` eksportlari o'rniga
  `frontend/src/hooks/use-page-title.ts`; statik `<title>` —
  `frontend/index.html:20`.
- Xavfsizlik sarlavhalari: `next.config.ts` dan chiqib, **serving qatlamiga**
  ko'chadi — `frontend/security-headers.ts` bitta manba sifatida
  `vite.config.ts` ning `server.headers`/`preview.headers` iga va nginx
  shablo­niga beriladi.
- Docker: `output: "standalone"` + Node server o'rniga **statik build** +
  statik fayl serveri.

## Sabab

Reja talabi birinchi navbatda. Undan tashqari ikkita amaliy sabab bor:

1. **Ilova aslida SPA.** Bitta `"use client"` va deyarli barcha mazmun
   `src/components/` dagi klient komponentlarida — App Router'ning server
   komponentlaridan faqat bitta joyda haqiqiy foyda olinadi (landing).
   Qolgan hamma joyda Next server qatlami tekinga to'lanadigan murakkablik.
2. **CSP yaxshilanadi.** `next.config.ts:39` prod'da ham
   `script-src 'self' 'unsafe-inline'` beradi, chunki Next o'zining bootstrap
   va flight payload'ini inline `<script>` sifatida qo'yadi (izoh `:36-38`).
   Vite inline skript chiqarmaydi, shuning uchun
   `frontend/security-headers.ts:66-71` prod'da `'unsafe-inline'` ni butunlay
   olib tashlaydi (`vite.config.ts:47` `modulePreload: { polyfill: false }`
   bilan birga).

## Oqibatlar

**Salbiy — SSR va SEO yo'qoladi.** Landing (`/`) hozir yagona haqiqiy server
tomon fetch: `frontend/src/app/page.tsx:9-15` `<Landing />` ni ataylab child
sifatida uzatadi (izoh `:4-8`), `frontend/src/components/marketing/landing.tsx:55-56`
`async function Landing()` va `frontend/src/lib/showcase.ts:30-40`
`fetch(.../public/showcase/, { next: { revalidate: 60 } })`. Fayl izohi
(`showcase.ts:4-9`) buni ochiq aytadi: "birinchi bo'yoq, JS'siz ko'rinish va
SEO shunga bog'liq". SPA'da bu:

- birinchi bo'yoq bo'sh bo'ladi, mazmun keyin keladi;
- JS o'chirilgan brauzerda / oddiy kraulerda sahifa bo'sh;
- 60 soniyalik server keshi yo'qoladi — har mehmon `/public/showcase/` ga
  o'zi so'rov yuboradi (endpoint throttle'i `settings.py:49` `SHOWCASE` scope
  bilan himoyalangan, ammo yuk ortadi).

Buni qabul qilamiz, chunki mahsulot — ichki, login ortidagi ilova; SEO faqat
bitta marketing sahifasiga tegishli. Agar keyinchalik kerak bo'lsa, yechim
**alohida** qaror bo'ladi (build vaqtida prerender yoki statik landing).

**Salbiy — xavfsizlik sarlavhalari jimgina yo'qolishi mumkin.** Bugun CSP,
HSTS, COOP, Permissions-Policy **faqat** `next.config.ts:56-72` orqali
beriladi; Django tomonda CSP umuman yo'q va repoda nginx konfiguratsiyasi
yo'q. `next.config.ts` o'chirilgan lahzada bu sarlavhalar yo'qoladi va buni
**hech qanday test ushlamaydi**. Shuning uchun ko'chirish DoD'i:
`security-headers.ts` ni `vite.config.ts` ga ulash + nginx shabloni +
parite testi (`src/test/security-headers.test.ts`) — uchalasi ham hozircha
yo'q yoki ulanmagan.

**Salbiy — Docker qurilishi qayta yoziladi.** `frontend/Dockerfile:6-7` va
`:81-83` to'g'ridan-to'g'ri `.next/standalone` + `.next/static` ga tayanadi,
`:93` `CMD ["node", "server.js"]`, va `:56-64` `NEXT_PUBLIC_*` ni build ARG
sifatida bakeydi. Bularning hammasi statik build + `VITE_*` ga almashadi;
`runner` bosqichi statik serverga qisqaradi. CI ham: `ci.yml:536` `next start`
ni ishga tushiradi (e2e job), `ci.yml:346` job nomi "Frontend (Next.js 16)".

**Salbiy — o'tish davri qimmat.** 29 ta fayl `next/*` importini, 5 ta fayl
`metadata` eksportini, `src/app/` ostidagi 26 ta route faylini ko'chirishni
talab qiladi. `env` qatlami ham: `frontend/src/lib/env.ts:2,6,9` va
`frontend/src/lib/showcase.ts:18` `process.env.NEXT_PUBLIC_*` ni o'qiydi →
`import.meta.env.VITE_*`.

**Ijobiy:** dev serveri sezilarli tez (HMR), build sodda, `output: standalone`
ning tracing sehri yo'qoladi, prod CSP dan `'unsafe-inline'` chiqib ketadi, va
frontend testlashiga vitest tabiiy ravishda ulanadi (ADR 0013 — vitest
konfiguratsiyasi allaqachon `vite.config.ts:49-58` ichida).

**Neytral:** `docs/API_CONTRACT.md` va butun backend o'zgarmaydi — bu faqat
klient qatlami qarori.

## Rejadan chetlashish

Yo'q — reja §3 aynan React + Vite ni ko'rsatadi; bu ADR rejaga **qaytish**.
Bu ADR hech qanday oldingi ADR'ni bekor qilmaydi: 0001–0010 backend va
kontrakt qarorlari bo'lib, ular kuchida qoladi.

## Ko'chirish yakunlandi

Yuqoridagi yettita ochiq band ham 2026-08-11 da yopildi. Bugungi holat —
tekshirilgan, taxmin emas:

| Nima | Qayerda |
|---|---|
| Kirish nuqtasi va route jadvali | `frontend/src/main.tsx`, `src/routes/app-routes.tsx` |
| 20 ta URL o'zgarmagani testda qulflangan | `src/routes/app-routes.test.ts` |
| Skriptlar vite/vitest'ga o'tgan | `frontend/package.json` (`dev`/`build`/`preview`/`test`) |
| `next`, `eslint-config-next` bog'liqliklari yo'q | `frontend/package.json` |
| `next.config.ts`, `next-env.d.ts`, `src/app/**` route fayllari o'chirilgan | `src/app/` da faqat `globals.css` + `providers.tsx` qoldi |
| Landing endi klientda yuklanadi | `src/components/marketing/landing.tsx` |
| Xavfsizlik sarlavhalari: dev/preview | `frontend/security-headers.ts` + `src/test/security-headers.test.ts` |
| Xavfsizlik sarlavhalari: prod | `frontend/nginx/default.conf.template`, `frontend/Dockerfile` |
| CI | `.github/workflows/ci.yml` — `frontend` job'ida `npm test`, `e2e` job'ida `vite preview` |
| Compose | `docker-compose.yml` frontend `args:` → `VITE_*`; `docker-compose.prod.yml` dan `NODE_ENV` olib tashlandi |

Prod CSP qattiqlashdi: Vite inline skript emitmagani uchun `script-src` dan
`'unsafe-inline'` **olib tashlandi** (Next'da u majburiy edi). Dev'da
`'unsafe-eval'` qoladi — React Refresh preamble'i haqiqatan inline.

Yopilmagan, lekin bu ADR doirasidan tashqaridagi ish: `dist/` bitta ~1.1 MB
chunk — Next'ning marshrut bo'yicha bo'linishi yo'qoldi, o'rniga `React.lazy`
bilan marshrut darajasidagi kod bo'linishi kerak.
