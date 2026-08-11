# Master Plan v2 — muvofiqlik holati

| | |
|---|---|
| **Hujjat** | MASTER_PLAN_COMPLIANCE.md |
| **Sana** | 2026-08-11 |
| **Maqsad** | "UzWork Master Plan v2" §18 (umumiy acceptance criteria) va §10 (sifat darvozalari) bandlarining **hozirgi holati** |
| **Nima emas** | Bu rejaning takrori emas va reja o'rnini bosmaydi — faqat holat kartasi |

## O'qishdan oldin: ikkita ogohlantirish

**1. Reja endi repoda.** Bu jadval yozilganda "UzWork Master Plan v2" repoda
alohida fayl sifatida saqlanmagan edi va bandlar rejaning izlaridan
(`docs/prompts/*` dagi "Qabul mezonlari" bloklari, `docs/adr/*`) tiklangan edi.
Reja o'shandan keyin [`docs/MASTER_PLAN.md`](MASTER_PLAN.md) sifatida qo'shildi.
Ya'ni endi har bir band **manba matnga qarab** tekshirilishi mumkin va shunday
qilinishi kerak: quyidagi band nomlari rejadagi nomlar bilan so'zma-so'z mos
kelmasligi, va rejada bo'lib bu yerda tushib qolgan band bo'lishi mumkin.
Har bir qatordagi holat esa taxmin emas: dalil ustuni faqat o'qib
tekshirilgan `fayl:qator` yoki CI qadam nomini keltiradi.

**2. Dalillar o'lchangan, taxmin qilinmagan.** Har bir "Bajarilgan" qatori
ortida yo o'qilgan `fayl:qator`, yo lokal ishga tushirilgan buyruq turibdi
(`pytest`, `ruff`, `mypy`, `npm run lint/typecheck/test/build`,
`docker compose config`). Ishga tushirilmagan yagona darvoza — Playwright E2E
(brauzer va seed talab qiladi); u B28 da alohida belgilangan.

Holat qiymatlari: **Bajarilgan** / **Qisman** / **Bajarilmagan**.

---

## A. §10 — Sifat darvozalari

| # | Band | Holat | Dalil | Qolgan ish |
|---|---|---|---|---|
| A1 | Backend lint (ruff) CI'da bloklovchi | Bajarilgan | `.github/workflows/ci.yml:140` — `ruff check --output-format=github .` (`backend` job, `ci.yml:56`) | — |
| A2 | Backend testlar + coverage darvozasi | Bajarilgan | `ci.yml:143-150` `pytest --cov`; `backend/.coveragerc:47` `fail_under = 83`; ratchet izohi `.coveragerc:36-46` | `backend/pytest.ini:16` `addopts` da `--cov` yo'q — **lokal** `pytest` polni tekshirmaydi, faqat CI. DoD nishoni 85% |
| A3 | Migratsiya drift darvozasi | Bajarilgan | `ci.yml:130-132` `makemigrations --check --dry-run`; lokal ham toza (`No changes detected`) | Faqat `backend` job'ida; `backend-sqlite` da yo'q — ataylab (bir xil migratsiyalar, ikki marta tekshirishning ma'nosi yo'q) |
| A4 | "Bitta PR — bitta migratsiya" qoidasi | Bajarilgan (qoida sifatida) | `docs/adr/0006-migratsiya-siyosati.md`; `CLAUDE.md` §Migrations | Qoida hujjatda, avtomatik tekshirilmaydi — review'ga tayanadi |
| A5 | OpenAPI sxema ratcheti | Bajarilgan | `ci.yml:50` `SCHEMA_UNIQUE_ERROR_BUDGET: "58"`; izoh `ci.yml:31-49`; generatsiya+tekshiruv `ci.yml:185-217` | Budjet 58 — ya'ni 58 ta noyob sxema xatosi hali bor (`serializer_class` siz APIView'lar). Bu ADR 0015 codegen'ining bloki |
| A6 | OpenAPI drift-check (committed artefakt) | Bajarilgan | `ci.yml:288` "OpenAPI drift-check (api/openapi.json)"; generator `scripts/gen-openapi.sh`; artefakt `api/openapi.json` (sarlavha `"UzWork API"`) | — |
| A7 | Frontend lint | Bajarilgan | `ci.yml:419` `npm run lint`; `frontend/eslint.config.mjs` (Next plagini olib tashlangan, `typescript-eslint` + `react-hooks` + `react-refresh`) | O'lchangan: **0 xato**, 4 ta `react-refresh/only-export-components` ogohlantirishi (komponent yonida yordamchi eksport qiladigan 4 fayl) |
| A8 | Frontend type-check | Bajarilgan | `ci.yml:428` `npm run typecheck` → `tsc --noEmit` | O'lchangan: 0 xato |
| A9 | Frontend build | Bajarilgan | `ci.yml:439` `npm run build` → `tsc -b --noEmit && vite build` | `dist/` bitta ~1.1 MB chunk — marshrut bo'yicha `React.lazy` kod bo'linishi hali yo'q (ADR 0011 "Ko'chirish yakunlandi") |
| A10 | Frontend unit testlar (vitest) darvozasi | Bajarilgan | `ci.yml:435` `npm test`; config `frontend/vite.config.ts` `test` bloki + `src/test/setup.ts`; 5 fayl / **46 test** — jumladan `src/hooks/mutations.test.tsx` (optimistik yangilanish + API xatosida rollback, §17.5), `src/routes/app-routes.test.ts` (20 ta URL qulflangan), `src/test/security-headers.test.ts` (dev↔nginx paritesi) | ADR 0013 |
| A11 | E2E (Playwright) CI'da haqiqiy stack ustida | Bajarilgan | `ci.yml` `e2e` job — Postgres 16 + Redis 7, `migrate` + `seed_demo`, Daphne, `ci.yml:592` `vite preview --strictPort`, `npx playwright test`; 8 spec `frontend/e2e/` | E2E bu sessiyada **ishga tushirilmadi** (brauzer + seed talab qiladi) — birinchi CI yugurishi buni tekshiradi |
| A12 | Docker image'lari quriladimi | Bajarilgan | `ci.yml` `docker` matritsasi: backend `target: runtime`, frontend `target: runner`; frontend image endi `nginxinc/nginx-unprivileged` (uid 101) statik `dist/` ni tarqatadi | Frontend image lokal qurilib, `curl` bilan sarlavhalari va SPA fallback'i tekshirilgan |
| A13 | Ikki bazali matritsa (Postgres + SQLite) | Bajarilgan | `ci.yml:56` Linux/PostgreSQL 16, `ci.yml:282` Windows/SQLite | SQLite job'ida coverage/ruff/migration-check yo'q — ataylab (`ci.yml:326-328`) |
| A14 | Xavfsizlik skanerlari, bloklovchi | Bajarilgan | `.github/workflows/security.yml`: `pip-audit` `:96-118`, `bandit -ll -ii` `:131-144`, `check --deploy` `:155-188`, `npm audit` (high/critical) `:240`, `gitleaks` `:303-309`; jadval `:29` (dushanba 04:00 UTC) + har PR; faylda `continue-on-error` yo'q | — |
| A15 | UI matni o'zbekcha — avtomatik tekshiruv | Bajarilgan | `frontend/eslint.config.mjs:93` — qoida **`error`** darajasida (ilgari `warn`); matn `src/i18n/uz.ts` (1183 qator, 47 eksport) | Qoida faqat `JSXText` ni ko'radi: ~38 ta `aria-label`/`placeholder`/`title` atributi hali komponentda — keyingi bosqich |
| A17 | Backend type-check (mypy, bosqichma-bosqich) | Bajarilgan | `ci.yml:156` `mypy --follow-imports=silent apps/core` (qat'iy, **0 xato**, 29 fayl); `ci.yml:160` butun daraxt ratchet'i, `ci.yml:57` `MYPY_ERROR_BUDGET: "46"`; konfiguratsiya `backend/mypy.ini` | Budjet 46 — o'lchangan (boshlang'ich 117 edi). Faqat pasayadi |
| A16 | Prod deploy darvozasi / release job | Bajarilmagan | `ci.yml` da deploy/publish job yo'q (5 job: `backend`, `backend-sqlite`, `frontend`, `e2e`, `docker`); `docs/prompts/12-final-release.md` "Boshlanmagan" | Release checklist va rollback rejasi — 12-faza |

---

## B. §18 — Umumiy acceptance criteria

| # | Band | Holat | Dalil | Qolgan ish |
|---|---|---|---|---|
| B1 | Auth: email bilan ro'yxatdan o'tish/kirish, JWT | Bajarilgan | `backend/apps/accounts/` (`config/urls.py:19`, 9 ta route); E2E `frontend/e2e/auth.spec.ts:22,34,57,76` | — |
| B2 | Ierarxiya: Workspace → Space → Folder → List | Bajarilgan | `backend/apps/workspaces/models.py`; 29 ta route (`config/urls.py:20`); shartnoma `docs/API_CONTRACT.md` §5-§6 | — |
| B3 | Task: maydonlar to'plami, tag, izoh, biriktirma, faoliyat | Bajarilgan | `backend/apps/tasks/` (12 route), `backend/apps/comments/` (2 route); `docs/API_CONTRACT.md` §9-§10 | — |
| B4 | Drag & drop — kasr pozitsiya, butun jadval qayta raqamlanmaydi | Bajarilgan | `docs/DATA_MODEL.md` §8 (fractional index); `Task.position`; qoida `CLAUDE.md` §Conventions; @dnd-kit `frontend/package.json` | — |
| B5 | List va Board ko'rinishlari | Bajarilgan | `frontend/src/components/list/`, `frontend/src/components/board/`; E2E `frontend/e2e/board-columns.spec.ts:29` (to'rt status ustuni) | `board-columns.spec.ts` untracked |
| B6 | Real vaqt: WebSocket hodisalari, sahifa yangilanmaydi | Bajarilgan | `backend/apps/realtime/`; `docs/API_CONTRACT.md` §15 (space-scoped guruhlar); E2E `frontend/e2e/realtime.spec.ts:132,146,171` | — |
| B7 | Realtime maxfiyligi: guruh = avtorizatsiya chegarasi | Bajarilgan | `API_CONTRACT.md` v1.3.4 changelog (§15) — `space.<id>` guruhi, `visible_spaces_q()` bilan bir xil predikat; broadcast'da `email: null` | — |
| B8 | Granular ruxsatlar — rol emas, **kod** | Bajarilgan | `backend/apps/core/permissions.py:114-517` — 49 ta `PermissionDef`, 2 tasi deprecated → **47 faol kod**; `CATALOG_VERSION = 6` (`:56`); `DEFAULT_MATRIX` `:525-528`; kirish qatlami `backend/apps/core/access.py` | — |
| B9 | Ruxsat matritsasi UI'da sozlanadi, Egasi qulflangan | Bajarilgan | E2E `frontend/e2e/permissions.spec.ts:86,106,116,146,165` (matritsa, owner ustuni qulflangan, override saqlanadi, defaultga qaytarish, ruxsatsiz admin bloklanadi) | — |
| B10 | Faqat-o'qish/mehmon hisob yozish affordance'larini ko'rmaydi | Qisman | `frontend/e2e/permissions.spec.ts:218,236` (list-view "Vazifa qo'shish"); commit `e2c4f62` | `dashboard`, `chat`, `notifications`, `planner`, `ai` route'lari uchun shunday test yo'q (`docs/prompts/11-qa.md` "Qamrov bo'shlig'i") |
| B11 | Takliflar: token → ro'yxatdan o'tish → avtomatik a'zolik | Bajarilgan | `docs/API_CONTRACT.md` §2 (register-with-invite, R21); `backend/apps/workspaces/` invitation route'lari | — |
| B12 | 404 vs 403 qoidasi (mavjudlik oshkor qilinmaydi) | Bajarilgan | `docs/API_CONTRACT.md` §1.7; `backend/apps/core/access.py`; `CLAUDE.md` §Security | — |
| B13 | Rate limiting | Bajarilgan | `backend/config/settings.py:264-282` — 15 ta nomlangan throttle scope; env defaultlari `:31-57` | — |
| B14 | Prod xavfsizlik sozlamalari (HSTS, secure cookie, X-Frame, COOP) | Bajarilgan | `backend/config/settings.py:345-353`, `:357-365` (`if not DEBUG`) | — |
| B15 | CSP | Bajarilgan | Dev/preview: `frontend/security-headers.ts` (`vite.config.ts` ga ulangan). Prod: `frontend/nginx/default.conf.template` + `frontend/Dockerfile`. Parite testi: `frontend/src/test/security-headers.test.ts` | Prod CSP **qattiqlashdi** — Vite inline skript emitmagani uchun `script-src` dan `'unsafe-inline'` olib tashlandi. Django tomonda CSP hali yo'q (`django-csp` o'rnatilmagan) — API JSON qaytargani uchun past xavf, lekin ochiq band |
| B16 | WebSocket `Origin` validatsiyasi | Bajarilgan | `backend/config/asgi.py:19-31,48-54` (`AllowedHostsOriginValidator`, `extra_origins`); sozlama `settings.py:332` | — |
| B17 | Fayl yuklash cheklovlari | Bajarilgan | `backend/apps/tasks/attachments.py`; throttle `settings.py:42`; qoida `README.md` §Xavfsizlik | — |
| B18 | Interfeys to'liq o'zbekcha, brend UzWork | Bajarilgan (frontend) / Qisman (backend) | Brend bitta joyda: `frontend/src/i18n/uz.ts` `APP` bo'limi (`brand`, `brandInitial: "U"`); API sxemasi `"UzWork API"` (`backend/config/settings.py`); admin `"UzWork boshqaruvi"` (`apps/workspaces/admin.py`, testi `apps/accounts/test_admin.py`) | `settings.py` hali `LANGUAGE_CODE = "en-us"`; Django `locale/`/`.po`/`LocaleMiddleware` yo'q — server xabarlari inglizcha. Storage kalitlari (`clickish.refresh`) va demo seed identifikatorlari (`@clickish.dev`) **ataylab o'zgartirilmadi**: birinchisi hamma sessiyani uzadi, ikkinchisi `seed_demo`↔`purge_demo` bilan so'zma-so'z bog'langan |
| B19 | Vaqt zonasi Asia/Tashkent, DB'da UTC | Bajarilgan | `backend/config/settings.py:502,505`; `docs/adr/0002-timezone.md` | — |
| B20 | API shartnomasi bog'lovchi va kod bilan mos | Qisman | `docs/API_CONTRACT.md:12` — "93 REST endpoints + 3 WebSocket channels"; `:1386` §16 inventarizatsiya; `api/openapi.json` generatsiya qilinadi va CI drift-check bilan qulflangan | `:1151` dagi eski "84" soni tuzatildi. Sonni `urls.py` ga qarshi **avtomatik** qayta hisoblash hali yo'q — 12-faza qabul mezoni |
| B21 | Arxitektura qarorlari ADR sifatida yozilgan | Bajarilgan | `docs/adr/0001`–`0015` + `README.md` indeksi; har ADR'da `fayl:qator` iqtibosi; 0010 → 0015 bilan almashtirilgan; reja matni `docs/MASTER_PLAN.md` da | — |
| B22 | Faza promptlari va ularning holati yuritiladi | Bajarilgan | `docs/prompts/00`–`12` + `README.md` indeksi (har faylda "Holat" bloki) | 06/09/10/11 fazalar "qisman", 12 "boshlanmagan" |
| B23 | Frontend React + Vite (SPA) | Bajarilgan | `frontend/vite.config.ts`, `index.html`, `src/main.tsx`, `src/routes/app-routes.tsx`; `package.json` da `next`/`eslint-config-next` yo'q; `src/**` da bitta ham `next/*` importi yo'q; `src/app/` da faqat `globals.css` + `providers.tsx` qoldi | Lint/typecheck/test/build — hammasi o'lchab tasdiqlangan. ADR 0011 "Ko'chirish yakunlandi" |
| B24 | Fon vazifalari: Celery + Redis | Bajarilgan | `backend/config/celery.py` (`Celery("uzwork")`, `autodiscover_tasks`), `config/__init__.py`, sozlamalar `settings.py` (`CELERY_TASK_ALWAYS_EAGER = not CELERY_BROKER_URL`), `celery==5.6.3` `requirements.txt` da; vazifalar `apps/core/tasks.py` — `purge_soft_deleted` (ADR 0003 ochiq qoldirgan tozalash joyi + biriktirma fayllari) va `flush_expired_tokens`; testlar `apps/core/tests/test_tasks.py` (20 ta); buyruq `manage.py purge_soft_deleted` (standart — quruq yurish); compose `worker` (`docker-compose.yml:97`) va `beat` (`:131`), prod'da `beat` `replicas: 1` | Birinchi prod purge yillik tarixni bir tunda o'chiradi — avval quruq yurish bilan sonini ko'ring. ADR 0012 |
| B25 | API tiplari kontraktdan chetlashmaydi | Qisman | `frontend/src/types/api.ts` qo'lda yuritiladi; `api/openapi.json` committed artefakt va CI drift-check (`ci.yml:288`) uni backend sxemasi bilan qulflaydi | Artefakt↔TS tiplar mosligini hali hech narsa tekshirmaydi. Yechim — ADR 0015 (openapi-typescript codegen), **amalga oshirilmagan**: uni A5 dagi 58 ta noyob sxema xatosi (`serializer_class` siz ~57 APIView) bloklaydi. Sxema tozalanmasdan generatsiya qilingan tiplar bo'sh chiqadi |
| B26 | Docker Compose bilan to'liq stack ko'tariladi | Bajarilgan | `docker-compose.yml` (db + redis + backend + **worker** + **beat** + frontend), `docker-compose.prod.yml`, `backend/docker-entrypoint.sh`; ikkala fayl ham `docker compose config` dan o'tadi | `name: clickup` **ataylab o'zgarmadi** — u nomlangan volume prefiksi (`clickup_pgdata`), o'zgartirilsa mavjud o'rnatma bo'sh bazaga qarab uyg'onadi |
| B27 | Ishchi daraxt toza, hamma ish commit qilingan | Bajarilgan | Bu hujjat yozilgan paytdagi 220+ o'zgargan/kuzatilmagan fayl `feat/uzwork-master-plan-v2` branchida commit qilindi | — |
| B28 | Barcha CI joblari yashil | Lokal o'lchangan, CI hali yugurmagan | Backend: `manage.py check` toza, `makemigrations --check` drift yo'q, `ruff check` toza, `mypy apps/core` 0 xato / butun daraxt 46 (budjet 46), **pytest to'liq yashil**. Frontend: lint 0 xato, typecheck 0 xato, vitest 46/46, `vite build` muvaffaqiyatli. Ikkala compose fayli `docker compose config` dan o'tadi | `e2e` job **lokal yugurtirilmadi** (brauzer + seed talab qiladi) — uni birinchi CI yugurishi tekshiradi. Shu sababli holat "yashil" emas, "lokal o'lchangan" |

---

## Xulosa

- **§10 darvozalari** endi ikkala tomonda ham o'rnatilgan va bloklovchi:
  backend (ruff, coverage poli, migratsiya drift, sxema ratcheti, **mypy**,
  xavfsizlik skanerlari) va frontend (eslint — jumladan o'zbekcha-matn qoidasi
  endi `error`, tsc, **vitest**, build). Qolgan bo'shliq — A16: release/deploy
  job yo'q.
- **§18 mezonlari** bo'yicha uchta katta arxitektura bandi yopildi: Vite
  ko'chishi (B23), Celery (B24) va brend (B18). Ochiq qolgani — B25: tip
  codegen'i, va uni bloklayotgan sabab aniq: 58 ta drf-spectacular sxema
  xatosi (A5).
- **Ilgari eng qattiq deb belgilangan xavf (B15) yopildi.** Xavfsizlik
  sarlavhalari `next.config.ts` bilan birga yo'qolishi mumkin edi; endi ular
  ikki joyda (`security-headers.ts` va nginx shabloni) va ularni bir-biriga
  bog'lab turadigan parite testi bor.
- **Keyingi eng foydali qadam** — `serializer_class` siz APIView'larni
  `@extend_schema` bilan annotatsiya qilib, sxema xatolarini nolga tushirish:
  u bitta o'zida A5 ni yopadi va B25 ni ochadi.
