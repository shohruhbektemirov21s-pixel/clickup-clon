# 10 — API tiplari

Holat: **Bekor qilindi (0015 bilan almashtirildi)** | Sana: 2026-08-11

> **Bekor qilinish sababi.** Bu ADR ning markaziy bandi — "codegen YO'Q" —
> endi amal qilmaydi: foydalanuvchi rejaga moslashni va `openapi-typescript`
> codegen'ini tanladi. Yangi qaror:
> [`0015-api-tiplari-codegen.md`](0015-api-tiplari-codegen.md).
>
> **Nima kuchida qoladi:** bu ADR ning infratuzilma qismi —
> committed `api/openapi.json` artefakti va CI drift-check'i — bekor
> qilinmaydi. Ular amalga oshirildi (`scripts/gen-openapi.sh:44`,
> `.github/workflows/ci.yml:228-275`) va ADR 0015 da codegen'ning **kirish
> manbai** bo'lib xizmat qiladi.
>
> **Eskirgan raqamlar:** quyidagi matnda `SCHEMA_UNIQUE_ERROR_BUDGET=54`
> va `ci.yml:171-219` / `ci.yml:178-210` iqtiboslari bor; hozirgi qiymat
> **58** (`ci.yml:50`) va ratchet qadami `ci.yml:178-217`. Tarixiy yozuv
> sifatida o'zgartirilmadi.

## Kontekst

Frontend backend API javoblari uchun TypeScript tiplariga muhtoj.
`CLAUDE.md`ning konventsiyasi aniq: "TypeScript types for API payloads live
in `frontend/src/types/api.ts` and mirror `docs/API_CONTRACT.md` field-for-field.
This file is **hand-written and hand-maintained**; there is no codegen
(`docs/SPRINT_PLAN.md` claims otherwise and is wrong)". Ya'ni codegen
YO'Q degan qaror allaqachon `CLAUDE.md`da yozilgan. Ammo kontrakt (backend)
va tiplar (frontend) qo'lda sinxronlashtirilgani uchun ular sekin-asta bir-biridan
uzoqlashishi (drift) tabiiy xavf.

Hozirgi holat: `.github/workflows/ci.yml:171-219` ("OpenAPI sxemasi (ratchet)"
qadami) `python manage.py spectacular --file openapi-schema.yml` ni ishga
tushiradi, YAML sifatida yaroqliligini tekshiradi, noyob sxema xatolari
sonini budjet (`SCHEMA_UNIQUE_ERROR_BUDGET=54`) bilan solishtiradi va natijani
`openapi-schema` nomli CI artefakti sifatida yuklaydi (`ci.yml:212-219`). Bu
mavjud, lekin ikki narsa yo'q: (a) sxema repo'ga **committed artefakt**
sifatida (`api/openapi.json`) saqlanmaydi — faqat vaqtinchalik CI artefakti;
(b) hech qanday **drift-check** yo'q — ya'ni committed sxema bilan haqiqiy
generatsiya qilingan sxema orasidagi farqni tekshiradigan qadam yo'q, va
qo'lda yozilgan `frontend/src/types/api.ts` bilan solishtiradigan avtomatik
tekshiruv ham yo'q.

## Qaror

Codegen YO'Q — `frontend/src/types/api.ts` qo'lda yozilgan/saqlanadigan
holicha qoladi (`CLAUDE.md` konventsiyasi o'zgarmaydi). Buning ustiga
ikkita qo'shimcha qadam qo'shiladi: (1) `drf-spectacular`dan generatsiya
qilingan OpenAPI sxemasi **`api/openapi.json`** sifatida repo'ga
committed artefakt bo'ladi (hozirgi `backend/openapi-schema.yml` vaqtinchalik
CI artefaktining o'rnini bosmaydi — ikkalasi bir xil generatordan chiqadi,
lekin `api/openapi.json` versiyalangan va PR diff'ida ko'rinadi); (2) CI'ga
**drift-check** qadami qo'shiladi — har PR'da sxema qayta generatsiya
qilinadi va committed `api/openapi.json` bilan solishtiriladi; farq bo'lsa
job qizil bo'ladi ("sxemani yangilab, committed qiling" degan xabar bilan).

## Sabab

To'liq codegen (`api.ts`ni avtomatik generatsiya qilish) `CLAUDE.md`da
allaqachon rad etilgan yo'l — buni qayta ochish katta qayta yozishni talab
qiladi va loyiha konventsiyasiga zid. Lekin "qo'lda yozilgan tiplar
kontraktdan chetlashmasligi" muammosi haqiqiy — hozir buni ushlaydigan
hech narsa yo'q. `api/openapi.json` + drift-check bu ikkisi orasidagi
murosa: tiplar qo'lda qoladi (loyiha stili saqlanadi), lekin backend'ning
haqiqiy sxemasi versiyalangan artefakt sifatida ko'rinadi va PR
ko'rib chiquvchisi (yoki kelajakda avtomatik diff-tool) uni
`api.ts`/`API_CONTRACT.md` bilan qo'lda solishtira oladi. Bu shuningdek
mavjud `openapi-schema` ratchet infratuzilmasini (`ci.yml:178-210`) qayta
ishlatadi — noldan qurish shart emas.

## Oqibatlar

**Ijobiy:** backend sxemasidagi har qanday o'zgarish PR diff'ida
`api/openapi.json` orqali ko'rinadi (drift-check tufayli committed nusxa
har doim yangilangan bo'lishi shart) — bu review paytida "bu backend
o'zgarishi `api.ts`ni yangilashni talab qiladimi?" savolini javob berish
osonlashtiradi, garchi avtomatik tekshirilmasa ham.

**Salbiy:** `api/openapi.json` va `api.ts` orasidagi MUVOFIQLIK hali ham
avtomatik tekshirilmaydi — drift-check faqat "sxema va committed fayl bir
xilmi" ni tekshiradi, "committed fayl va qo'lda yozilgan TS tiplari bir
xilmi" ni emas. Ya'ni bu ADR asosiy muammoni (qo'lda tiplarning eskirishi)
to'liq hal qilmaydi, faqat ko'rinishni yaxshilaydi. To'liq hal — kelajakda
alohida tekshiruv skripti (`openapi.json`ni parse qilib `api.ts`dagi
maydon nomlari bilan solishtiruvchi) qo'shishni talab qiladi; bu hozircha
doirasidan tashqarida.

## Rejadan chetlashish

Yo'q — bu foydalanuvchi tomonidan aniq tanlangan variant
("codegen yo'q, lekin `api/openapi.json` artefakt + CI drift-check").

> **2026-08-11 yangilanishi.** Aynan shu band o'zgardi: rejaning
> `openapi-typescript` codegen talabidan chetlashish bekor qilindi.
> ADR [`0015`](0015-api-tiplari-codegen.md) ga qarang.
