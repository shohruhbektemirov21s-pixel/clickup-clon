# 15 — API tiplari: openapi-typescript codegen

Holat: Qabul qilindi (amalga oshirilmagan) | Sana: 2026-08-11

ADR 0010 ni almashtiradi (`docs/adr/0010-api-tiplari.md`).

## Kontekst

`frontend/src/types/api.ts` — 1100 qator, 103 ta eksport (101 tasi `type`/
`interface`) — qo'lda yozilgan va qo'lda yuritiladigan fayl. U
`docs/API_CONTRACT.md` ni "field-for-field" aks ettirishi kerak (fayl sarlavhasi
`:1-10`), va uni 52 ta fayl import qiladi (`grep -rl 'from "@/types/api"'
frontend/src` → 52; boshqa yozilish shakli yo'q).

ADR 0010 "codegen YO'Q" deb qaror qilgan edi va uning o'rniga ikkita narsani
taklif qilgan: committed `api/openapi.json` artefakti va CI drift-check.
**O'sha ikkalasi bajarildi:** `scripts/gen-openapi.sh:44`
(`manage.py spectacular --format openapi-json --file api/openapi.json`) va
`.github/workflows/ci.yml:228-275` ("OpenAPI drift-check (api/openapi.json)")
— u `git status --porcelain -- api/openapi.json` bilan tekshiradi, chunki
kuzatilmagan fayl `git diff` da yolg'on yashil beradi (izoh `:248-252`).

Ammo ADR 0010 ning o'zi tan olgan asosiy muammo hal bo'lmadi
(`0010-api-tiplari.md:47-57`): drift-check faqat "sxema ↔ committed artefakt"
mosligini ushlaydi, "artefakt ↔ qo'lda yozilgan TS tiplari" mosligini emas.
Ya'ni backend maydon nomini o'zgartirsa, `api/openapi.json` yangilanadi, CI
yashil bo'ladi, va `api.ts` jimgina yolg'on gapirishda davom etadi.

Foydalanuvchi endi rejaga moslashni — `openapi-typescript` codegen'ini —
tanladi. Tarixiy eslatma: `docs/SPRINT_PLAN.md` (FE-03, `:173-174`) buni
allaqachon talab qilgan edi, lekin qurilmagan; `docs/API_CONTRACT.md:1474`
(R32) shu sababli "qo'lda yozilgan fayl yutadi" deb hukm chiqargan. Bu ADR
o'sha hukmni **kelajakka** qaratib o'zgartiradi.

## Qaror

`frontend/src/types/api.ts` **`openapi-typescript` codegen'i bilan
almashtiriladi**, lekin ikki bosqichli shaklda:

1. `api/openapi.json` dan `frontend/src/types/openapi.d.ts` generatsiya
   qilinadi (`openapi-typescript` + `npm run gen:api` skripti).
2. `frontend/src/types/api.ts` **yupqa qayta-eksport qatlamiga** aylanadi:

   ```ts
   import type { components } from "./openapi";
   export type Task = components["schemas"]["Task"];
   export type Role = components["schemas"]["RoleEnum"];
   ```

Ya'ni `@/types/api` import yo'li **o'zgarmaydi** va 52 ta iste'molchi fayl
qayta yozilmaydi.

**Bu hali amalga oshirilmagan va shartsiz boshlanmasligi kerak.**
Bloklovchi sabab: `drf-spectacular` sxemasi hozir **58 ta noyob xato** beradi
(`.github/workflows/ci.yml:50` `SCHEMA_UNIQUE_ERROR_BUDGET: "58"`; izoh
`:31-50`). Sabab — `serializer_class` siz `APIView`'lar: backend'da ~57 ta
`APIView` bor va ularning deyarli hech birida `serializer_class` yo'q,
atigi 6 tasi `@extend_schema` bilan annotatsiya qilingan. Masalan:

- `backend/apps/accounts/views.py:35` `class RegisterView(APIView)` —
  serializer faqat handler ichida, `:42`;
- `backend/apps/tasks/views.py:135` `class ListTasksView(APIView)` — sinf
  atributlari umuman yo'q;
- `backend/apps/comments/views.py:28` `class TaskCommentsView(APIView)`.

Bunday view uchun spectacular javob sxemasini taxmin qila olmaydi va
generatsiya qilingan tip `unknown` yoki bo'sh obyekt bo'lib chiqadi. Shunday
holatda codegen'ni yoqish — tiplarni **yaxshilash emas, yo'qotish**.

### Bosqichlar va ularning shartlari

| # | Bosqich | Boshlash sharti | Tugash mezoni |
|---|---|---|---|
| 1 | `api/openapi.json`, `scripts/gen-openapi.sh` va drift-check qadamini **commit qilish** | — | `git status` toza; `ci.yml:242-275` haqiqiy darvoza |
| 2 | `APIView`'larni annotatsiyalash (`serializer_class` yoki `@extend_schema`), app-ma-app | 1 | `SCHEMA_UNIQUE_ERROR_BUDGET` 58 → 0; `--fail-on-warn` yoqiladi |
| 3 | `openapi-typescript` ni qo'shish + `npm run gen:api` → `src/types/openapi.d.ts` | 2 | Generatsiya qilingan faylda `unknown` sxema yo'q |
| 4 | `api.ts` ni qayta-eksportga aylantirish, blok-blok | 3 | `tsc --noEmit` yashil; `@/types/api` yo'li o'zgarmagan |
| 5 | CI'ga "tiplarni qayta generatsiya qil va drift bo'lsa yiqil" qadami | 4 | Backend maydon o'zgarishi frontend build'ini qizartiradi |

2-bosqich ratchet bilan boshqariladi: budjet **faqat pasayadi**. (Eslatma:
`ci.yml:32-34` va `:43` izohlari bir-biriga zid — biri "faqat yuqoriga",
ikkinchisi "faqat pasayadi" deydi. Amaldagi niyat va kod
`:209-215` — **pasayish**; izohni tuzatish kerak.)

## Sabab

ADR 0010 ning "codegen yo'q" qarori o'sha paytda `CLAUDE.md` konventsiyasiga
tayangan edi. Konventsiya endi o'zgardi va sabab ham kuchli: qo'lda yuritilgan
1100 qatorli tip fayli **kontraktdan chetlashishi muqarrar**, buni hech qanday
avtomatik tekshiruv ushlamaydi, va 52 ta iste'molchi fayl noto'g'ri tipga
ishonadi. Codegen bu sinf xatolarni butunlay yo'q qiladi.

Yupqa qayta-eksport qatlami tanlanishining sababi — migratsiya narxi.
`components["schemas"]["Task"]` ni to'g'ridan-to'g'ri 52 ta faylga tarqatish
katta, mexanik va xavfli diff bo'lardi; `api.ts` ni fasad sifatida saqlash
esa o'zgarishni bitta faylga qamaydi va kerak bo'lsa orqaga qaytarishni
osonlashtiradi.

Bosqichlarning tartibi ham majburiy: sxema sifati oshirilmasdan generatsiya
qilingan tiplar bugungi qo'lda yozilgan tiplardan **yomonroq** bo'ladi.

## Oqibatlar

**Ijobiy:** backend serializer'idagi har qanday o'zgarish frontend
type-check'ida ko'rinadi; kontrakt/kod drift'i sinf sifatida yo'qoladi;
`API_CONTRACT.md` uchinchi manba bo'lib qolmaydi.

**Salbiy — qo'lda yozilgan JSDoc yo'qoladi.** `api.ts` da izohlar bor va
ularning ba'zilari haqiqiy bilim tashiydi, masalan `:411-412`
("Server-computed fractional base-62 key; never written by clients") va
`:1024` (`SHOWCASE_WORKSPACE_ID` sozlanmagan bo'lsa `null`). Codegen ularni
o'chiradi. Chora: bunday izohlarni qayta-eksport qatlamida saqlash yoki
backend serializer'iga `help_text` sifatida ko'chirish — ikkinchisi afzal,
chunki u sxemaga ham tushadi.

**Salbiy — generatsiya qilingan tip nomlari xunuk.** `drf-spectacular`
enum'larni `RoleEnum`, `StatusEnum` kabi nomlar bilan chiqaradi va ba'zi
nomlarni `PatchedTaskRequest` shaklida yasaydi. Qayta-eksport qatlami buni
yashiradi, lekin xaritalash qo'lda yoziladi.

**Salbiy — 2-bosqich katta ish.** ~57 ta `APIView` ni annotatsiyalash
backend tomonda sezilarli mehnat. Uni app-ma-app, alohida PR'larda bajarish
kerak; har PR budjetni pasaytiradi.

**Neytral:** `api/openapi.json` (2788 qator) va drift-check ADR 0010 dan
meros bo'lib **qoladi** — endi ular codegen'ning kirish manbai. Ya'ni 0010
ning infratuzilma qismi bekor qilinmaydi, faqat "codegen yo'q" bandi bekor
qilinadi.

## Rejadan chetlashish

Yo'q — reja `openapi-typescript` codegen'ini talab qiladi va bu ADR shunga
qaytadi. Chetlashish faqat **vaqt** bo'yicha: qaror qabul qilindi, ammo
sxema sifati darvozasi (2-bosqich) tugamaguncha ishga tushirilmaydi.
