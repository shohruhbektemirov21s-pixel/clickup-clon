# E2E testlar (Playwright)

Ilovaning uchidan-uchiga testlari. Ular **haqiqiy** backend va frontend
serverlariga qarshi ishlaydi — Playwright serverlarni o'zi ko'tarmaydi
(`playwright.config.ts` da `webServer` ataylab yo'q; sabablari o'sha faylning
boshida yozilgan).

CI'da bu to'plam har PR'da avtomatik ishlaydi: `.github/workflows/ci.yml` →
`e2e` job (Postgres + Redis service'lari, `migrate`, `seed_demo`, Daphne,
`next start`, so'ng `npx playwright test`). Yiqilganda HTML hisobot, trace
fayllari va ikkala server logi artefakt bo'lib yuklanadi.

## Oldindan shartlar (lokal)

1. **Backend** — `http://127.0.0.1:8000`:

   ```bash
   cd backend
   ../.venv/Scripts/python.exe manage.py migrate
   AUTH_THROTTLE_RATE=1000/min AUTH_BURST_THROTTLE_RATE=1000/min \
     ../.venv/Scripts/python.exe manage.py runserver
   ```

   Throttle nega bo'shatiladi — pastdagi "Login va throttle" bo'limiga qarang.
   Bo'shatmasangiz ham ko'p hollarda ishlaydi, lekin to'plamni ketma-ket bir
   necha marta ishga tushirsangiz `429` ga urilasiz. CI aynan shu qiymatlarni
   qo'yadi.

2. **Frontend** — `http://localhost:3000`:

   ```bash
   cd frontend
   npm run dev
   ```

3. **Demo ma'lumot** (`seed_demo`):

   ```bash
   cd backend
   ../.venv/Scripts/python.exe manage.py seed_demo
   ```

   Hisoblar (parol hammasida `clickish-demo-2026`):

   | Email | Rol |
   |---|---|
   | `demo@clickish.dev` | Egasi (owner) |
   | `aziz@clickish.dev` | Admin |
   | `malika@clickish.dev` | A'zo |
   | `jasur@clickish.dev` | A'zo |
   | `nodira@clickish.dev` | Mehmon (guest) |

4. Chromium:

   ```bash
   cd frontend
   npx playwright install chromium
   ```

Bularning biri yetishmasa, to'plam 23 ta timeout emas, **bitta aniq xabar**
beradi: `e2e/global-setup.ts` har run boshida ikkala serverni va demo
hisobini tekshiradi.

## Ishga tushirish

```bash
cd frontend

npm run test:e2e                    # hammasi (list + html hisobot)
npm run test:e2e:ui                 # interaktiv UI rejim
npx playwright test e2e/auth.spec.ts        # bitta fayl
npx playwright test -g "presence"           # nom bo'yicha filtr
npx playwright test --headed                # brauzerni ko'rib turib
```

HTML hisobot `playwright-report/` ichida (avtomatik ochilmaydi):

```bash
npx playwright show-report
```

## Manzillarni o'zgartirish

```bash
E2E_BASE_URL=http://localhost:3001 \
E2E_API_BASE_URL=http://localhost:8001/api/v1 \
  npm run test:e2e
```

## Fayllar

| Fayl | Nima qiladi |
|---|---|
| `fixtures.ts` | Umumiy yordamchilar: `signIn`, `signedInContext`, `login`, REST yordamchilari, deterministik kutishlar |
| `global-setup.ts` | Run boshida: serverlar va demo ma'lumot bormi; huquqlar matritsasini standart holatga qaytaradi |
| `global-teardown.ts` | Run oxirida: matritsani qaytaradi (majburiy), qolgan `E2E ` vazifalarini supuradi |
| `auth.spec.ts` | Kirish, noto'g'ri parol, chiqish, himoyalangan URL redirecti |
| `dashboard.spec.ts` | Ish maydoni bosh sahifasi: statistika, "Mening vazifalarim", "Jamoa" |
| `member-profile.spec.ts` | A'zo profili: statistika, tablar, dashboard'dan havola |
| `permissions.spec.ts` | Huquqlar matritsasi: ko'rish, tahrirlash, reset, admin uchun yopiqligi |
| `realtime.spec.ts` | WebSocket: `connection.ack`, `presence.sync`, `task.created`, `presence.join` |
| `smoke.spec.ts` | Asosiy sahifalar konsol/sahifa xatosisiz yuklanadi |

---

## Login va throttle

Backend `auth/login/` ni cheklaydi: email bo'yicha `AUTH_BURST_THROTTLE_RATE`
(standart 5/min), IP bo'yicha `AUTH_THROTTLE_RATE` (standart 10/min).

**To'plam bu cheklovni UXLAB O'TKAZMAYDI.** Ilgari `login()` `429` ni ko'rsa
62 soniya kutardi, test byudjeti esa 60 soniya edi — ya'ni retry yo'li hech
qachon oxiriga yetmasdi va sabab o'rniga "Test timeout" ko'rinardi. To'rtta
spec buni 240 soniyalik hook timeout'i bilan yamardi, `auth.spec.ts` esa
yamamagan edi.

Hozirgi tartib:

1. **Login formasi faqat `auth.spec.ts` da bosiladi** — chunki aynan o'sha
   fayl login oqimini tekshiradi.
2. Qolgan hamma joyda sessiya REST orqali olinadi: `apiLogin()` token
   juftligini oladi, `clickish.refresh` `localStorage` ga qo'yiladi, ilova
   yuklanganda `SessionBootstrap` uni `auth/refresh/` ga almashtiradi.
   `auth/refresh/` throttle qilinmagan, ya'ni bu yo'l rate limiter'ga
   umuman tegmaydi. Bu `signIn(page, user)` va `signedInContext(browser, user)`.
3. Har brauzer kontekstiga **yangi** sessiya beriladi: SimpleJWT
   (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`) refresh tokenni
   birinchi ishlatilishida almashtirib eskisini blacklist qiladi, ya'ni bitta
   tokenni ikki kontekst bo'lisha olmaydi.
4. Shunga qaramay bir run'da ~10 ta `auth/login/` so'rovi ketadi, bu esa
   standart 10/min ni chetlab o'tishi mumkin. Shuning uchun CI va yuqoridagi
   lokal buyruq throttle'ni bo'shatadi. Throttle mantig'ining o'zi backend
   testlarida (`apps/accounts`) tekshiriladi — uni E2E'da qayta tekshirish
   shart emas.
5. Agar `429` baribir kelsa, `login()` **darhol** tushunarli xato beradi va
   qaysi env o'zgaruvchini qo'yish kerakligini aytadi. Hech qayerda uyqu yo'q.

## Test ma'lumoti va izolyatsiya

To'plam `seed_demo` ning bitta ish maydonini bo'lishadi, ya'ni har qanday
qoldiq keyingi runga o'tadi. Buning uchun uch qavat himoya bor:

- **`global-setup.ts`** har run boshida rol-huquq matritsasini standart
  holatga qaytaradi — oldingi uzilib qolgan run keyingisini ifloslantirmaydi.
- **`permissions.spec.ts`** (yagona yozadigan spec) har testdan keyin va
  `afterAll` da qaytaradi. Xato **yutilmaydi**: ilgari `.catch(() => {})` bor
  edi va yiqilgan reset demo ish maydonini butunlay o'zgargan holda
  qoldirardi. Fayllar alifbo tartibida ishlagani uchun bu `realtime` va
  `smoke` dan OLDIN yuradi.
- **`global-teardown.ts`** run oxirida matritsani yana qaytaradi (bu qadam
  yiqilsa run ham yiqiladi) va `E2E ` prefiksli qolgan vazifalarni supuradi.
  Qoldiqning o'zi runni yiqitmaydi — yiqilgan test o'z `finally` blokiga
  yetmasligi tabiiy — lekin **o'chirib bo'lmagan** qoldiq yiqitadi.

Vazifalar faqat REST API orqali yaratiladi (DB'ga to'g'ridan-to'g'ri
tegilmaydi) va nomi `E2E ` bilan boshlanadi, shuning uchun qoldiqni qo'lda
topish ham oson: ilovadagi qidiruvda `E2E` deb yozing.

## Kutish qoidalari

Bu to'plamda `waitForTimeout()` va `waitForLoadState("networkidle")` **yo'q**.

- `networkidle` ni Playwright tavsiya qilmaydi, bu sahifalar esa ochiq
  WebSocket ushlab turadi — "500 ms jimlik" hech qachon kelmaydi.
- Hidratsiya poygasi `waitForHydration()` bilan hal qilinadi: React
  hidratsiya paytida DOM tuguniga `__reactFiber$…` xususiyatini o'rnatadi, u
  paydo bo'lgani "element endi React nazoratida" degani. Ilgari bu yerda
  "8 marta yozib ko'r, orasida 200 ms kut" sikli bor edi — u poygani
  tuzatmasdan yashirardi.
- Sahifa tayyorligi `waitForAppShell()` bilan: hisob menyusi ko'rindimi.
- Soket yopilishi `WebSocket.isClosed()` bilan (`realtime.spec.ts`), taxminiy
  1 soniyalik uyqu bilan emas.

## Debug

```bash
# Qadam-baqadam inspektor bilan
npx playwright test e2e/auth.spec.ts --debug

# Yiqilgan testning trace faylini ochish
npx playwright show-trace test-results/<papka>/trace.zip
```

Trace, skrinshot va video faqat **xato** bo'lganda saqlanadi. CI'da ular
`playwright-report` artefaktida, Daphne va Next loglari bilan birga.

Foydali maslahatlar:

- `--headed` bilan brauzer ko'rinadi; `PWDEBUG=1` inspektorni ochadi.
- WebSocket testlari yiqilsa, avval backend Daphne/ASGI rejimida ishlayotganini
  tekshiring (`runserver` Channels bilan ASGI'ni o'zi ko'taradi) — oddiy WSGI
  serverda `ws://` ulanmaydi.
- `smoke.spec.ts` **hech qanday** `console.error` va `pageerror` bo'lmasligini
  talab qiladi. Yiqilsa, xato matni assertion xabarida ko'rinadi.
