<!--
  BU FAYL QO'LDA YOZILMAYDI.

  Manba — `UzWork_Master_Plan_v2.docx` (foydalanuvchining hujjati). Bu yerdagi
  matn o'sha .docx dan chiqarilib Markdown'ga o'girilgan: sarlavhalar, jadvallar
  va prompt bloklari tiklangan, matnning o'zi o'zgartirilmagan.

  NEGA REPODA TURADI. `docs/MASTER_PLAN_COMPLIANCE.md` shu rejaning §10 va §18
  bandlariga qarshi holat kartasi. Reja repodan tashqarida qolsa, o'sha jadvalni
  hech kim tekshira olmaydi — "reja shunday deydi" degan da'vo dalilsiz bo'ladi.

  ZIDDIYAT BO'LSA. Reja — niyat; `docs/adr/` — qabul qilingan qaror. Ular zid
  bo'lsa ADR yutadi va o'zi nega chetlashganini yozib qo'yadi (masalan 0007,
  0011). Rejani ADR'ni o'zgartirmasdan "bajarilgan" deb hisoblama.
-->

# UZWORK — SENIOR AGENT DEVELOPMENT MASTER PLAN

Versiya 2.0

ClickUp uslubidagi, 100% oʻzbek tilidagi Work Management Platform

Claude Code + GitHub Codespaces + Senior-level agent workflow

## 0. v2 versiyasida nima oʻzgardi

Ushbu versiya v1 rejasining senior-darajadagi tahlili asosida yangilandi. Asosiy oʻzgarishlar:

- Har faza promptiga alohida qabul mezonlari qoʻshildi — “tayyor” soʻzi endi tekshiriladigan checklist bilan isbotlanadi.
- API Contract boʻlimi: drf-spectacular → openapi.json → TypeScript codegen; CI'da sinxronlik tekshiruvi.
- Maʼlumot modeli qoidasi: status/priority DB va API'da kod sifatida saqlanadi; oʻzbekcha matn — faqat display qatlamida.
- Sifat darvozalari: Claude Code hooks + CI required checklar — instruktsiya oʻrniga mexanizm.
- Fazalar va subagentlar ajratildi; sessiya/kontekst boshqaruvi (/clear, faza = yangi sessiya) qoidalari kiritildi.
- Har faza uchun review halqasi: branch → PR → CI → reviewer-agent → inson diff oʻqishi.
- Arxitektura qarorlari (ADR) roʻyxati: fayl saqlash, timezone, soft delete, API versioning, email backend, migratsiya siyosati, app strukturasi.

## 1. Loyiha maqsadi

Maqsad — ClickUp kabi ishlarni boshqarish platformasining asosiy UX va workflow prinsiplarini oʻzlashtirgan, lekin mustaqil kod, mustaqil dizayn va oʻz brendiga ega, toʻliq oʻzbek tilidagi professional SaaS platforma yaratish. ClickUp kodi, assetlari, logotipi yoki yopiq dizayni koʻchirilmaydi.

## 2. Agentlar uchun asosiy talab

- Har bir agent oʻzini 15+ yillik tajribaga ega Senior/Staff/Principal darajadagi mutaxassis sifatida tutadi. Bu rol real tajriba daʼvosi emas; u yuqori sifatli engineering standartini belgilovchi ish rejimidir.
- Avval repository va mavjud architecture'ni tahlil qil, keyin kod yoz.
- Keraksiz rewrite yoki katta refactor qilma.
- Security, permission, data integrity va backward compatibility birinchi oʻrinda.
- Har bir feature test bilan yakunlansin (10-boʻlimdagi darvozalar buni mexanik nazorat qiladi).
- Fake data va hardcoded production logic ishlatma.
- Existing functionality'ni buzmaslik majburiy.
- Noaniqlik boʻlsa: avval docs/adr/ ga qara; u yerda javob boʻlmasa — oʻzing hal qilma, savol ber.
- Har bir yakunda: nima qilindi, fayllar, testlar, muammolar va keyingi qadamlarni yoz.

## 3. Texnologik stack

- Backend: Python, Django, Django REST Framework.
- API contract: drf-spectacular (OpenAPI 3 sxema generatsiyasi).
- Database: PostgreSQL.
- Realtime/background: Redis, Django Channels, Celery.
- Frontend: React, TypeScript, Vite, Tailwind CSS.
- Frontend tiplari: openapi-typescript orqali api/openapi.json'dan codegen.
- Testing: backend — pytest (unit/API/permission); frontend — vitest (component/integration).
- Infrastructure: Docker, GitHub Actions, GitHub Codespaces.
- Repository rules: CLAUDE.md, .devcontainer/devcontainer.json, .env.example, README.md, docs/prompts/, docs/adr/.

## 4. Product hierarchy

Workspace → Space → Folder → List → Task → Subtask

Workspace → Members / Roles / Permissions / Dashboard / Chat / Docs / Notifications

## 5. MVP modullari

- Authentication: login, registration, logout, password recovery.
- Workspace: yaratish, tahrirlash, oʻchirish, aʼzolarni boshqarish.
- Space / Folder / List: CRUD va hierarchy permissions.
- Task: title, description, status, priority, assignee, creator, dates, tags, comments, attachments, subtasks.
- List View: sorting, filtering, grouping, pagination/search.
- Kanban: drag & drop, optimistic update, rollback on API failure.
- Dashboard: task statistikasi va team/project overview.
- Responsive UI: desktop-first, mobile-friendly.

## 6. Keyingi bosqich modullari

- Calendar: kun/hafta/oy, drag-to-reschedule.
- Gantt: dependencies va timeline.
- Chat: 1-to-1, workspace, task chat, mentions, read status.
- Docs: hujjatlar, editor, permissions.
- Notifications: in-app va keyinchalik email/push.
- Automation: trigger → condition → action.
- AI Agent: task creation, summarization, prioritization, reports, recommendations.

## 7. Til va maʼlumot modeli qoidasi

Foydalanuvchiga koʻrinadigan barcha matnlar oʻzbek tilida boʻladi. Lekin til — faqat display qatlamining masalasi:

Asosiy qoida: DB va API'da status, priority, role kabi qiymatlar kod sifatida saqlanadi. Oʻzbekcha matn faqat UI'da, markaziy lugʻat orqali koʻrsatiladi. DB'ga oʻzbekcha string yozish taqiqlanadi — aks holda sorting, integratsiya va kelajakda til qoʻshish ogʻriqqa aylanadi.

| Kod (DB/API) | UI'da (oʻzbekcha) |
|---|---|
| todo | Boshlanmagan |
| in_progress | Jarayonda |
| review | Tekshirilmoqda |
| done | Bajarildi |
| low | Past |
| medium | Oʻrta |
| high | Yuqori |
| urgent | Shoshilinch |
| i18n qarori (MVP): toʻliq i18n infratuzilma shart emas. Barcha UI stringlar bitta markaziy lugʻatda saqlanadi: frontend — src/i18n/uz.ts, backend xabarlari — constants moduli. Komponent ichida hardcoded matn taqiqlanadi. Keyinchalik til qoʻshish kerak boʻlsa, lugʻat allaqachon tayyor boʻladi. | Tarjima lugʻati (UI terminlari): |

Inglizcha

Oʻzbekcha

| Inglizcha | Oʻzbekcha |
|---|---|
| Workspace | Ish maydoni |
| Members | Aʼzolar |
| Space | Boʻlim |
| Notifications | Bildirishnomalar |
| Folder | Papka |
| Priority | Muhimlik |
| List | Roʻyxat |
| Assignee | Masʼul |
| Task | Vazifa |
| Due date | Tugash sanasi |
| Subtask | Ichki vazifa |
| Comments | Izohlar |
| Dashboard | Boshqaruv paneli |
| Attachments | Biriktirmalar |
| Calendar | Taqvim |
| Board | Doska |
| Docs | Hujjatlar |
| Settings | Sozlamalar |

## 8. Arxitektura qarorlari (ADR)

Quyidagi qarorlar Architect fazasida yakuniy qabul qilinadi va har biri docs/adr/ papkasida qisqa yozib qoʻyiladi. Agentlar bu masalalarda oʻzicha qaror qabul qilmaydi — ADR'ga tayanadi. Har biri uchun tavsiya berilgan:

| Qaror | Tavsiya |
|---|---|
| Fayl saqlash (attachments) | Dev: lokal disk; prod: S3-compatible (masalan, MinIO). Kodda storage abstraction (django-storages) — keyin almashtirish oson. |
| Timezone | DB'da UTC saqlanadi (USE_TZ=True); koʻrsatishda Asia/Tashkent. Calendar'da yarim tun chegara holatlari testlanadi. |
| Soft delete | Workspace va Task uchun soft delete (deleted_at); qattiq oʻchirish faqat alohida admin jarayoni orqali. |
| API versioning | /api/v1/ prefiksi. Breaking change faqat yangi versiyada. |
| Email backend | Dev: console backend; prod: SMTP (env orqali). Password recovery shu orqali ishlaydi. |
| Migratsiya siyosati | Bitta PR — bitta migratsiya. CI'da makemigrations --check. Destructive migratsiya — alohida PR va inson tasdigʻi bilan. |
| App strukturasi | Variant A: har domen alohida app (spaces, folders, lists…) — modullar aniq, lekin circular import xavfi. Variant B (tavsiya): hierarchy bitta projects app ichida (Space/Folder/List/Task birga) — migratsiya va bogʻliqliklar sodda. Yakuniy qaror — Architect'da. |
| Pagination va limitlar | Default page size: 25, maksimum: 100. Auth endpointlarda rate limiting. |

## 9. API Contract — backend va frontend oʻrtasidagi shartnoma

- Backend va frontend alohida fazalarda, alohida sessiyalarda quriladi. Ular oʻrtasida yagona, generatsiya qilinadigan shartnoma boʻlmasa — drift muqarrar. Shartnoma ogʻzaki kelishuv emas, artefakt:
- Backend har endpoint oʻzgarishida drf-spectacular orqali api/openapi.json faylini yangilaydi (repo'da commit qilinadi).
- Frontend API tiplari qoʻlda yozilmaydi: openapi-typescript openapi.json'dan src/types/api.ts generatsiya qiladi.
- CI'da sinxronlik tekshiruvi: sxema qayta generatsiya qilinadi va commit qilingani bilan solishtiriladi — farq boʻlsa build yiqiladi.
- Ish tartibi: endpoint oʻzgardi → sxema yangilandi → tiplar regeneratsiya qilindi → keyin UI kodi.

## 10. Sifat darvozalari: hooks va CI

- “Har feature test bilan yakunlansin” kabi qoidalar instruktsiya sifatida ishonchsiz — agent unutishi mumkin. Ular mexanizmga aylantiriladi: hook va CI unutmaydi.
- Claude Code hooks (.claude/settings.json):
- PostToolUse (har edit'dan keyin): backend faylda ruff check --fix; frontend faylda tsc --noEmit.
- Hook xato qaytarsa, natija agentga koʻrinadi — agent muammoni oʻzi darhol tuzatadi, sizgacha yetib kelmaydi.
- CI required checklar (GitHub Actions):
- Lint: ruff (backend), eslint (frontend).
- Typecheck: mypy (backend, bosqichma-bosqich), tsc --noEmit (frontend).
- Testlar: pytest (backend), vitest (frontend).
- python manage.py makemigrations --check --dry-run — unutilgan migratsiyani ushlaydi.
- OpenAPI sync check (9-boʻlim).
- Qoida: hech bir PR required checklar yashil boʻlmasdan merge qilinmaydi.

## 11. Ish oqimi: fazalar, sessiyalar va kontekst boshqaruvi

- Bu plandagi “agentlar” aslida ketma-ket fazalardir. Ularni parallel subagent qilib yuborish foyda bermaydi — kontekst boʻlinadi, yaxlit fikrlash yoʻqoladi. Toʻgʻri model:
- Faza promptlari repo'da versiyalanadi: docs/prompts/00-architect.md, 01-foundation.md, … Prompt oʻzgarsa — git tarixida koʻrinadi.
- Har faza — yangi sessiya (/clear). Fazalar orasida kontekst tashish vositasi — kod, testlar, docs/adr/, openapi.json; suhbat tarixi emas.
- Haqiqiy subagent faqat ikkita: reviewer (.claude/agents/reviewer.md — read-only, diff'ni tanqid qiladi, fayl oʻzgartirmaydi) va auditor (Security/QA ogʻir tekshiruvlari uchun).
- Uzun izlanish (yuzlab fayl boʻylab qidiruv/tahlil) kerak boʻlsa — subagentga topshiriladi; asosiy sessiyaga faqat xulosa qaytadi.

## 12. Har faza uchun review halqasi

- Faza feature/<faza-nomi> branch'da bajariladi.
- Yakunda PR ochiladi; CI required checklar yashil boʻlishi shart.
- Reviewer subagent diff boʻyicha hisobot beradi: bug, xavfsizlik, permission, N+1, keraksiz oʻzgarishlar.
- Inson (siz) diff'ni oʻqiydi. Auth, permission, migratsiya, oʻchirish/pul bilan bogʻliq diff'lar — majburiy, delegatsiya qilinmaydi.
- Shundan keyingina merge. Keyingi faza main'dan boshlanadi.
- Bu halqa tufayli QA/Security fazasi “birinchi tekshiruv” emas, “yakuniy chuqur audit” boʻladi — xatolar 9 faza davomida toʻplanib qolmaydi.

## 13. Tavsiya etiladigan repository

```
uzwork/
├── .github/workflows/           # CI: lint, typecheck, test, migrate-check, openapi-sync
├── .devcontainer/devcontainer.json
├── .claude/
│   ├── agents/reviewer.md       # read-only reviewer subagent
│   └── settings.json            # hooks (PostToolUse: ruff / tsc)
├── docs/
│   ├── prompts/                 # faza promptlari (00-architect.md, 01-foundation.md, …)
│   └── adr/                     # arxitektura qarorlari (8-boʻlim)
├── api/openapi.json             # generatsiya qilinadigan shartnoma (9-boʻlim)
├── backend/
│   ├── config/
│   ├── apps/
│   │   ├── accounts/
│   │   ├── workspaces/
│   │   ├── projects/            # Variant B: Space/Folder/List/Task shu yerda
│   │   ├── comments/
│   │   ├── notifications/
│   │   ├── chat/
│   │   └── ai/
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── src/components/
│   ├── src/pages/
│   ├── src/layouts/
│   ├── src/features/
│   ├── src/hooks/
│   ├── src/services/
│   ├── src/i18n/uz.ts           # markaziy oʻzbekcha lugʻat
│   └── src/types/api.ts         # openapi.json'dan codegen — qoʻlda tahrirlanmaydi
├── tests/
├── docker-compose.yml
├── .env.example
├── CLAUDE.md
├── README.md
└── LICENSE
```

## 14. CLAUDE.md — tayyor asosiy fayl (v2)

```markdown
# CLAUDE.md

## ROLE
Sen ushbu repository'da 15+ yillik professional tajribaga ega Senior/Staff/Principal
Software Engineer darajasida ishlaysan. Bu rol yuqori engineering standartini anglatadi:
production-grade code, security, maintainability, testing, performance, clean architecture.

## PRODUCT
Loyiha: UzWork. ClickUp uslubidagi work-management workflow'larni oʻzlashtirgan,
ammo mustaqil dizayn va kodga ega, 100% oʻzbek tilidagi SaaS platforma.
ClickUp kodi, assetlari, logotipi yoki yopiq implementatsiyasi koʻchirilmaydi.

## LANGUAGE & DATA
- User-facing UI 100% oʻzbek tilida.
- DB va API'da status/priority/role qiymatlari KOD sifatida saqlanadi:
  status: todo, in_progress, review, done
  priority: low, medium, high, urgent
- Oʻzbekcha matn faqat display qatlamida. DB'ga oʻzbekcha string yozish TAQIQLANADI.
- Barcha UI stringlar markaziy lugʻatdan: src/i18n/uz.ts. Hardcoded matn yozma.

## API CONTRACT
- api/openapi.json — backend va frontend oʻrtasidagi yagona shartnoma.
- Endpoint oʻzgarsa: avval sxemani yangila, keyin frontend tiplarini regeneratsiya qil.
- Frontend API tiplarini qoʻlda yozma — faqat openapi-typescript codegen.

## ENGINEERING PRINCIPLES
- Avval repository'ni inspect qil; mavjud architecture'ni tushunmasdan kod yozma.
- Minimal, xavfsiz va maintainable change qil. Keraksiz rewrite/refactor qilma.
- DRY, SOLID, separation of concerns, clear boundaries.
- Business logic'ni view/component ichiga tiqma; reusable service/domain qatlam yarat.
- Database integrity'ni saqla; N+1 query'dan saqlan.
- Permissionlarni server-side tekshir; user boshqa workspace maʼlumotini koʻrmasin.
- Secrets'ni source code'ga yozma.

## MIGRATIONS
- Bitta PR — bitta migratsiya. CI'da makemigrations --check ishlaydi.
- Destructive migratsiya: alohida PR, aniq ogohlantirish va inson tasdigʻi bilan.

## DOMAIN HIERARCHY
Workspace -> Space -> Folder -> List -> Task -> Subtask
Workspace aʼzolari role/permission orqali boshqariladi.

## TASK
Fields: title, description, status, priority, creator, assignee, start_date, due_date,
estimated_time, tags, comments, attachments, subtasks, dependencies, timestamps.
Status/priority — yuqoridagi kodlar; oʻzbekcha nomlari UI lugʻatida.

## SECURITY
- Har object access server-side permission bilan tekshirilsin. Workspace isolation majburiy.
- IDOR, CSRF, XSS, SQL injection, privilege escalation'ga qarshi himoya.
- AI ham permissionlarni chetlab oʻtmasin.

## API
- /api/v1/ prefiksi, consistent response/error format.
- Pagination (default 25, max 100), filtering, sorting, validation standart.

## FRONTEND
- Responsive, accessible, fast UI.
- Har async view: loading / empty / error / success holatlari.
- Kanban drag-and-drop: optimistic update + API failure'da rollback.

## TESTING
- Backend: model, API, permission, validation testlari. List endpointlarda
  assertNumQueries bilan N+1 nazorati.
- Frontend: component va interaction/integration testlari.
- Har feature test bilan yakunlanadi; CI required checklar yashil boʻlishi shart.

## GIT
- Branch: feature/<nom>, fix/<nom>, refactor/<nom>.
- Commit: feat|fix|refactor|test|docs: tavsif. Unrelated oʻzgarishlarni aralashtirma.

## WORKFLOW
1. Inspect  2. Plan  3. Implement  4. Test  5. Review  6. Summarize
- Har faza docs/prompts/ dagi prompt boʻyicha, YANGI sessiyada bajariladi.
- Arxitektura savoli chiqsa — docs/adr/ ga qara. Javob boʻlmasa, oʻzing hal qilma, soʻra.
- Kod yozishdan oldin plan tuz; katta ishni kichik, review qilinadigan bosqichlarga boʻl.

## DO NOT
- Fake production data ishlatma. Secrets commit qilma.
- Existing functionality'ni sababsiz buzma. Massive rewrite qilma.
- Duplicate component/service yaratma. Permission'ni faqat frontend'da qoldirma.
- Testlarni oʻchirib muammoni yashirma.
- Status/priority'ni DB'ga oʻzbekcha string qilib yozma.
- API tiplarini qoʻlda yozma (faqat codegen).

## FINAL RESPONSE FORMAT
Har task yakunida: 1) Summary  2) Changed files  3) Tests executed
4) Security/performance notes  5) Remaining issues  6) Next recommended step.
Agar test ishlamasa, sababini yashirma.
```

## 15. Rollar: fazami yoki subagentmi

| # | Rol | Turi | Masʼuliyat |
|---|---|---|---|
| 00 | Architect | Faza (read-only) | Architecture, ADR qarorlari, DB/API contract, roadmap. |
| 01 | Backend Foundation | Faza | Auth, user, workspace, membership, permissions, /api/v1/. |
| 02 | Domain/Hierarchy | Faza | Space/Folder/List/Task hierarchy, authorization. |
| 03 | Task | Faza | Task API, comments, attachments, dependencies. |
| 04 | Frontend Foundation | Faza | App shell, auth, routing, tiplar codegen, i18n lugʻat. |
| 05 | Kanban/List | Faza | Task views, drag-and-drop, filtrlar. |
| 06 | Dashboard | Faza | Real statistika, aggregate query'lar. |
| 07 | Realtime | Faza | Channels, Redis, WebSocket, notifications, chat asosi. |
| 08 | DevOps | Faza | Docker, Codespaces, CI/CD, environments. |
| 09 | AI | Faza | Permission-aware AI assistant. |
| — | Reviewer | Doimiy subagent (read-only) | Har faza PR'ida diff tanqidi; fayl oʻzgartirmaydi. |
| — | Security/QA auditor | Subagent | Chuqur audit, regression, threat modeling. |

## 16. Fazalarni ishga tushirish tartibi

- Architect: repository audit + ADR + architecture plan. Kod yozmaydi. Plan inson tomonidan tasdiqlanadi.
- Backend Foundation: auth, user, workspace, membership, permissions, OpenAPI sxema.
- Domain: Space/Folder/List/Task hierarchy.
- Backend Task: task API, comments, attachments, dependencies.
- Frontend Foundation: app shell, auth, routing, tiplar codegen, i18n lugʻat.
- Frontend Workspace: sidebar, workspace switcher, hierarchy navigatsiyasi.
- Kanban/List: task views, drag-and-drop, filtrlar.
- Dashboard: real statistika.
- Realtime: notifications, chat asosi.
- Security + QA audit: toʻliq tekshiruv va regression.
- DevOps: CI/CD, container, environment, deployment.
- Final review: performance, accessibility, hujjatlar, release-readiness.
- Eslatma: har faza 12-boʻlimdagi review halqasi bilan yopiladi — Security/QA fazasini kutmasdan.

## 17. Master promptlar (qabul mezonlari bilan)

Har prompt docs/prompts/ da alohida fayl sifatida saqlanadi va yangi sessiyada yuboriladi. Qabul mezonlari promptning ajralmas qismi — agent yakunda har bir bandni tekshirib, holatini yozadi.

### 17.0. Faza 0 — Architect (read-only)

**Prompt:**

```text
You are the Lead Software Architect for UzWork.
Act like a 15+ year Senior/Staff/Principal engineer.
DO NOT WRITE CODE. Do not modify files in this phase.

Inspect the entire repository and produce:
- architecture assessment and current stack
- domain model and database model
- API boundaries and versioning
- frontend architecture
- authentication/authorization model
- security risks, testing strategy, CI/CD strategy

Resolve every open decision listed in section 8 (file storage, timezone,
soft delete, API versioning, email backend, migration policy, app structure,
pagination/rate limits) and record each as a short ADR in docs/adr/ (text only).

At the end provide a concrete, ordered implementation plan with dependencies
and acceptance criteria for every phase. Respect CLAUDE.md.
```

**Qabul mezonlari:**

- Hech qanday kod fayli oʻzgartirilmagan (read-only faza).
- Barcha ochiq ADR qarorlar yakuniy qabul qilingan va yozilgan.
- Domain/DB model va API boundary tavsifi toʻliq.
- Har faza uchun dependency va qabul mezonlari bilan roadmap mavjud.
- Plan inson tomonidan oʻqib tasdiqlangan — keyingi faza shundan keyin boshlanadi.

### 17.1. Faza 1 — Backend Foundation

**Prompt:**

```text
Implement the project foundation.
Create/verify Django, DRF, PostgreSQL configuration, custom user model and
authentication (login, registration, logout, password recovery), workspace and
membership models, role/permission boundaries, /api/v1/ structure with a
consistent response/error format, drf-spectacular schema generation,
migrations and tests.
Do not touch unrelated modules. Run tests and fix failures before finishing.
```

**Qabul mezonlari:**

- Auth oqimi (register/login/logout/recovery) testlar bilan yashil.
- Workspace + membership modellari; permissionlar server-side.
- /api/v1/ prefiksi va yagona error format ishlaydi.
- api/openapi.json generatsiya boʻladi va commit qilingan.
- pytest yashil; makemigrations --check toza.

### 17.2. Faza 2 — Hierarchy

**Prompt:**

```text
Implement Workspace -> Space -> Folder -> List -> Task hierarchy.
Add CRUD, validation, membership-aware authorization, serializers, services
and API tests.
A user outside the workspace must not access its objects.
Check for IDOR and N+1 query risks. Update the OpenAPI schema.
```

**Qabul mezonlari:**

- Workspace tashqarisidagi user obyektlarga 403/404 oladi — permission testlarda isbotlangan.
- IDOR testlari: boshqa workspace obyekt ID'lari bilan urinishlar rad etiladi.
- List endpointlarda N+1 yoʻqligi assertNumQueries bilan tekshirilgan.
- CRUD + validation testlari yashil; openapi.json yangilangan.

### 17.3. Faza 3 — Task

**Prompt:**

```text
Implement production-grade task management:
title, description, status, priority, creator, assignee, dates, tags,
comments, attachments, subtasks, dependencies, estimated time.
Statuses and priorities are stored as codes
(todo/in_progress/review/done; low/medium/high/urgent).
Add search, filtering, sorting, pagination and bulk-safe operations.
Write unit/API/permission tests. Update the OpenAPI schema.
```

**Qabul mezonlari:**

- Status/priority DB va API'da kod sifatida; oʻzbekcha matn faqat UI lugʻatida.
- Search/filter/sort/pagination testlari yashil.
- Comments, attachments, subtasks, dependencies uchun permission testlari mavjud.
- Bulk operatsiyalar tranzaksiyada va permission-safe.
- openapi.json yangilangan.

### 17.4. Faza 4 — Frontend Foundation

**Prompt:**

```text
Build the React/TypeScript application shell.
Generate API types from api/openapi.json (do not hand-write API types).
Create authentication screens, protected routing, workspace shell, collapsible
sidebar, navigation hierarchy, task list, task detail panel/modal,
loading/empty/error states and responsive layout.
Use real API data; no fake production data.
All user-facing text must come from the central Uzbek dictionary (src/i18n/uz.ts).
```

**Qabul mezonlari:**

- TS tiplar openapi.json'dan generatsiya qilingan; qoʻlda yozilgan duplicate API tip yoʻq.
- Auth + protected routing ishlaydi.
- Har async view: loading / empty / error / success holatlari mavjud.
- Barcha UI matnlar markaziy lugʻatdan; komponentda hardcoded matn yoʻq.
- tsc --noEmit xatosiz; component testlar yashil.

### 17.5. Faza 5 — Kanban

**Prompt:**

```text
Build a professional Kanban board.
Columns map status codes to Uzbek labels:
todo → Boshlanmagan, in_progress → Jarayonda,
review → Tekshirilmoqda, done → Bajarildi.
Implement drag-and-drop, optimistic status update, rollback on API failure,
filters by assignee/priority/date/tag and search.
Keep accessibility and keyboard interaction in mind.
```

**Qabul mezonlari:**

- Optimistic update + API xatoda rollback — testda simulyatsiya qilingan.
- Filtrlar va qidiruv real API bilan ishlaydi.
- Kartani klaviatura bilan koʻchirish mumkin (accessibility).
- Ustunlar status kodlariga bogʻlangan; matnlar lugʻatdan.

### 17.6. Faza 6 — Dashboard

**Prompt:**

```text
Build a real-data dashboard:
total tasks, completed, in progress, overdue, urgent, project/team load.
Add date filters: Today, This Week, This Month, Custom.
Compute statistics with aggregate queries; never query per item in loops.
```

**Qabul mezonlari:**

- Statistika aggregate query bilan; assertNumQueries chegarasi qoʻyilgan.
- Sana filtrlari toʻgʻri chegaralar bilan (timezone hisobga olingan).
- Fake data yoʻq — real API.

### 17.7. Faza 7 — Realtime

**Prompt:**

```text
Implement Django Channels + Redis realtime features:
notifications, task updates and chat foundations.
Enforce authentication and workspace permissions on every channel.
Handle reconnects, authorization failures and race conditions.
```

**Qabul mezonlari:**

- Ruxsatsiz WebSocket ulanish testda rad etiladi.
- Reconnect va authorization failure ssenariylari qamrab olingan.
- Bir taskni ikki user parallel oʻzgartirishi (race) testlangan.

### 17.8. Calendar (keyingi bosqich)

**Prompt:**

```text
Build Calendar view with Day/Week/Month modes.
Render task start and due dates.
Support drag-to-reschedule with backend synchronization.
Store datetimes in UTC; display in Asia/Tashkent. Use Uzbek labels.
```

**Qabul mezonlari:**

- UTC saqlash / Asia/Tashkent koʻrsatish — yarim tun chegara holatlari testlangan.
- Drag-to-reschedule backend bilan sinxron; xatoda rollback.
- Kun/Hafta/Oy rejimlari ishlaydi.

### 17.9. Security Audit (auditor subagent)

**Prompt:**

```text
Perform a full security audit.
Check authentication, authorization, workspace isolation, IDOR, CSRF, XSS,
SQL injection, file upload risks, secrets, rate limiting, privilege
escalation and unsafe WebSocket access.
Fix Critical and High findings. Add regression tests.
```

**Qabul mezonlari:**

- Critical/High topilmalar tuzatilgan; har biriga regression test.
- Hisobot formati: topilma → jiddiylik → tuzatish → test.
- Auth endpointlarda rate limiting mavjud.

### 17.10. QA (auditor subagent)

**Prompt:**

```text
Act as Senior QA. Run the complete test suite.
Create tests for happy paths, permission boundaries, invalid input,
concurrency-sensitive updates, pagination, filtering, drag-and-drop behavior
and responsive critical flows.
Fix regressions, not symptoms.
```

**Qabul mezonlari:**

- Toʻliq suite yashil; flaky testlar aniqlanib barqarorlashtirilgan.
- Permission boundary va concurrency testlari mavjud.
- Regressiyalar sabab darajasida tuzatilgan (simptom emas).

### 17.11. DevOps

**Prompt:**

```text
Prepare production-grade developer infrastructure:
.devcontainer/devcontainer.json, Docker/Docker Compose, environment template,
health checks, deployment documentation.
Configure the CI required checks from section 10:
lint, typecheck, tests, makemigrations --check, OpenAPI sync.
Never commit secrets. Keep local and Codespaces setup reproducible.
```

**Qabul mezonlari:**

- docker compose up toza mashinada ishga tushadi.
- CI required checklar (lint, typecheck, pytest/vitest, makemigrations --check, OpenAPI sync) sozlangan va yashil.
- Secrets faqat env orqali; .env.example toʻliq.
- Codespaces devcontainer ishlaydi.

### 17.12. AI Agent

**Prompt:**

```text
Implement a permission-aware AI assistant.
Capabilities: create task, summarize task/project, prioritize tasks,
generate weekly report, identify overdue work and suggest next actions.
The AI must only access data the current user is authorized to access.
Any destructive or externally visible action requires confirmation.
```

**Qabul mezonlari:**

- AI faqat joriy user ruxsatidagi maʼlumotni koʻradi — permission testlar bilan isbotlangan.
- Destructive/tashqi koʻrinadigan amallar tasdiq talab qiladi.
- AI tool'lari server-side permission bilan cheklangan (prompt injection himoyasi).

### 17.13. Final Release

**Prompt:**

```text
Perform a release-readiness review as a Principal Engineer.
Inspect architecture, security, tests, performance, accessibility, database
migrations, API compatibility, error handling, logging, documentation and
deployment. Do not add unnecessary features.
Fix release-blocking issues and provide a final checklist with remaining risks.
```

**Qabul mezonlari:**

- 18-boʻlimdagi umumiy acceptance criteria toʻliq bajarilgan.
- Release-blocking muammo yoʻq; qolgan risklar roʻyxati berilgan.
- Migratsiyalar production-safe deb tekshirilgan.

## 18. Umumiy acceptance criteria

- 100% user-facing MVP UI oʻzbek tilida; barcha stringlar markaziy lugʻatdan.
- Status/priority DB va API'da kod sifatida saqlanadi.
- Workspace isolation server-side enforce qilinadi; IDOR testlari mavjud.
- CRUD va permission testlari mavjud; list endpointlarda N+1 nazorati.
- api/openapi.json va frontend tiplar sinxron (CI check yashil).
- Task List va Kanban real API bilan ishlaydi; drag-and-drop failure'da rollback qiladi.
- Hooks sozlangan; CI required checklar (lint, typecheck, testlar, migrate-check, OpenAPI sync) yashil.
- No secrets in Git; .env.example toʻliq.
- Har faza oʻz qabul mezonlarini bajargan va review halqasidan oʻtgan.
- Production migratsiyalar xavfsiz; destructive migratsiyalar inson tasdigʻi bilan.
- Responsive critical flows tekshirilgan.
- README, CLAUDE.md, docs/adr/, docs/prompts/ va development setup hujjatlashtirilgan.

## 19. GitHub Codespaces

Repository'da .devcontainer/devcontainer.json saqlanadi. GitHub Codespaces Docker asosidagi development container orqali reproducible environment beradi; devcontainer.json tools, runtimes, extensions va port forwarding'ni belgilaydi. Tavsiya: Python + Node.js + Git + GitHub CLI + Docker workflow uchun project-specific dev container.

Manba: GitHub Codespaces documentation — https://docs.github.com/en/codespaces

## 20. Boshlash tartibi

- Repo'ni tayyorlang: CLAUDE.md (14-boʻlim), docs/prompts/ (17-boʻlim promptlari), docs/adr/ (boʻsh shablonlar), .claude/settings.json (hooks) va .claude/agents/reviewer.md.
- Claude Code'ni repository rootida oching — yangi, toza sessiya.
- docs/prompts/00-architect.md ni yuboring. Agent read-only tahlil, ADR qarorlari va roadmap beradi.
- Planni OʻZINGIZ oʻqing va tasdiqlang. Kerak boʻlsa tuzating — bu eng arzon tuzatish nuqtasi.
- Har keyingi faza: /clear → navbatdagi prompt → ish → 12-boʻlim review halqasi → merge.

## 21. Muhim eslatma

Bu hujjat agentlarni juda yuqori engineering standartida boshqarish uchun yozilgan. “15+ yil tajriba” iborasi agentga rol va sifat mezonini beradi; bu agentning haqiqiy insoniy ish tajribasi borligini anglatmaydi. Hujjatdagi qoidalarning kuchi ikki manbadan keladi: aniq qabul mezonlari va ularni mexanik nazorat qiladigan darvozalar (hooks, CI, review halqasi).
