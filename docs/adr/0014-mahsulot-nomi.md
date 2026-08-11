# 14 — Mahsulot nomi va brend chegarasi: UzWork

Holat: Qabul qilindi | Sana: 2026-08-11

## Kontekst

Repo o'zini uchta turli nom bilan tanishtiradi va ularning barchasi raqibning
nomiga bog'langan:

- hujjatlarda "ClickUp Clone" / "Clickish (ClickUp clone) MVP";
- API sxemasida `backend/config/settings.py:313-314` —
  `"TITLE": "ClickUp Clone API"`, `"DESCRIPTION": "REST API for the ClickUp
  clone..."`, va bu generatsiya qilingan `api/openapi.json:4,6` ga ham
  tushgan;
- interfeysda `frontend/src/i18n/uz.ts:456` `brand: "Clickish"`, `:504`
  `whyTitle: "Nima uchun Clickish"`, `:563` `footerCopyright: "© 2026
  Clickish ..."`, va `frontend/src/routes/layouts.tsx:31,50` dagi brend
  yozuvi;
- Django admin'da `backend/apps/workspaces/admin.py:27-28`
  `"Clickish boshqaruvi"` / `"Clickish admin"`.

Bu ikki xil muammo tug'diradi. Birinchisi — huquqiy va reputatsion: mahsulot
o'zini raqib mahsulotining **kloni** deb ataydi. Ikkinchisi — texnik: bitta
mahsulotning uchta nomi bor, va ularning bir qismi saqlash kalitlari
(`clickish.refresh`) hamda infra nomlariga (`docker-compose.yml:13`
`name: clickup`) singib ketgan.

Rebrend allaqachon qisman boshlangan: `frontend/index.html:20`
`<title>UzWork</title>`, `frontend/src/hooks/use-page-title.ts` dagi
`DEFAULT_TITLE = "UzWork"`, `backend/config/celery.py:30` `Celery("uzwork")`,
`.devcontainer/devcontainer.json:2`. Ya'ni hozir repo yarim yo'lda.

## Qaror

**Mahsulot nomi — UzWork.**

UzWork ClickUp uslubidagi work-management workflow'laridan **ilhomlangan**,
ammo mustaqil kod, dizayn va brendga ega platforma. Chegarani ikki tomonlama
aniq belgilaymiz.

**Ko'chirilmaydi (hech qachon):**

- ClickUp kodi yoki uning hosilasi;
- ClickUp assetlari: logotip, ikonka to'plami, illyustratsiya, shrift,
  rasm, tovush;
- ClickUp brend elementlari: nom, so'z belgisi, brend ranglari (jumladan
  `#7B68EE` "ClickUp-purple", `docs/UI_SPEC.md` da uchraydi va o'sha hujjat
  **superseded**), slogan;
- ClickUp'ning yopiq (proprietary) dizayni: aniq ekran kompozitsiyasi,
  o'ziga xos vizual yechimlari piksel darajasida qaytarilmaydi;
- ClickUp matnlari va hujjatlari.

**Ilhom sifatida ochiq:**

- umumiy work-management UX naqshlari: Workspace → Space → Folder → List →
  Task ierarxiyasi, kanban/list ko'rinishlari, drag & drop tartiblash,
  izoh oqimi, rol/ruxsat matritsasi, real vaqtli hamkorlik — bular sohaning
  umumiy amaliyoti, birorta kompaniyaning mulki emas;
- ClickUp'ni **taqqoslash nuqtasi** sifatida eslatish: "ClickUp'dagi kabi
  teglar workspace darajasida" — bu foydali va to'g'ri (masalan
  `docs/DATA_MODEL.md:1102`).

**Til qoidasi:** loyiha o'zini "klon" deb atamaydi. To'g'ri formula —
"ClickUp uslubidagi work-management workflow'laridan ilhomlangan mustaqil
implementatsiya".

**Rebrend uch qatlamda, alohida bosqichlarda bajariladi** — chunki ularning
narxi tubdan farq qiladi:

1. **Hujjat qatlami** (`README.md`, `CLAUDE.md`, `docs/**`,
   `frontend/README.md`, `frontend/AGENTS.md`) — narxi nol, birinchi
   bajariladi. Tarixiy hujjatlar (`docs/PRD.md`, `docs/SPRINT_PLAN.md`,
   `docs/UI_SPEC.md`) o'zgartirilmaydi, ularga faqat brend eslatmasi
   qo'yiladi: tarixiy yozuvni qayta yozish uni yolg'onga aylantiradi.
2. **Foydalanuvchiga ko'rinadigan matn** (`frontend/src/i18n/uz.ts`,
   layout'lardagi brend yozuvi va logotip harfi, `admin.py:27-28`,
   `settings.py:313-314`) — arzon, buziladigan narsa yo'q.
3. **Identifikatorlar va infra nomlari** — **buzuvchi o'zgarish**, alohida
   reja bilan (pastga qarang).

## Sabab

"Klon" so'zi mahsulotni raqibning hosilasi sifatida ta'riflaydi — bu ham
noto'g'ri (kod mustaqil yozilgan), ham zararli. Ilhom manbasini oshkor
aytish esa halol va foydali: u dizayn qarorlarini tushuntiradi.

Rebrendni qatlamlarga bo'lish — chunki uchinchi qatlam foydalanuvchi
seansini yoki ma'lumot bazasini buzishi mumkin, birinchi ikkisi esa yo'q.
Hammasini bitta PR'da qilish "brend o'zgarishi" tufayli hamma foydalanuvchini
tizimdan chiqarib yuborish demakdir.

## Oqibatlar

**Ijobiy:** loyiha o'z nomi bilan tanishtiriladi; hujjat, UI va API sxemasi
bitta nomga keladi.

**Salbiy — uchinchi qatlam qimmat.** Quyidagi identifikatorlarni o'zgartirish
kuzatiladigan oqibatga ega, shuning uchun ularning har biri ataylab qaror
talab qiladi:

| Joy | Oqibat |
|---|---|
| `frontend/src/stores/auth-store.ts:6` `"clickish.refresh"` | **Har bir mavjud foydalanuvchi tizimdan chiqadi** (localStorage refresh token). E2E ham bog'langan: `frontend/e2e/fixtures.ts:21`, `e2e/auth.spec.ts:71` |
| `frontend/src/lib/client-id.ts:11` `"clickish.client-id"` | Ochiq tablar yangi client-id oladi — realtime echo-suppression vaqtincha buziladi |
| `frontend/src/components/auth/invite-view.tsx:35` `"clickish.invite-handoff"` | Deploy paytida yarim yo'ldagi taklif oqimi uziladi |
| `frontend/src/components/search/recent-items.ts:33` `"clickish.recent"` | "Yaqinda ochilganlar" tarixi jimgina yo'qoladi |
| `backend/config/settings.py:211` `KEY_PREFIX: "clickup"` | Redis kesh nomlar fazosi butunlay almashadi — sovuq kesh, throttle hisoblagichlari nolga tushadi |
| `docker-compose.yml:13` `name: clickup` | Volume prefikslari (`clickup_pgdata`, `clickup_media`) o'zgaradi — **mavjud ma'lumot yetim qoladi** |
| `.env.docker.example:14-15` `POSTGRES_DB`/`POSTGRES_USER` | Mavjud volume'da baza topilmaydi |
| `seed_demo.py` dagi `@clickish.dev` hisoblari va `"Clickish Demo"` | `purge_demo.py:30` bilan **so'zma-so'z** mos bo'lishi shart; `settings.py:62` `DEMO_USER_EMAIL`, `backend/.env.example:109` va `frontend/e2e/fixtures.ts:27-46` bilan bir vaqtda o'zgaradi, aks holda "Demo rejimda kirish" tugmasi jimgina ishlamay qoladi |

Tavsiya: saqlash kalitlarini o'zgartirganda eski kalitni bir marta o'qib,
yangisiga ko'chiradigan migratsiya yozing (yoki relizni "hamma qayta kiradi"
deb e'lon qiling). Infra nomlarini esa **faqat** yangi muhitda o'zgartiring —
ishlab turgan volume ustida emas.

**Neytral:** `frontend/package.json:2` `"name": "frontend"` — brendsiz, teginish
shart emas. CSS klass prefikslari brendga bog'lanmagan (`globals.css` da
`--color-brand-*` umumiy).

## Rejadan chetlashish

Yo'q — reja §1 va §14 aynan shuni talab qiladi: UzWork nomi, mustaqil
implementatsiya, ClickUp materiallarini ko'chirmaslik.
