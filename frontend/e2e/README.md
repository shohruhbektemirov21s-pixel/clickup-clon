# E2E testlar (Playwright)

Bu katalogda ilovaning uchidan-uchiga (end-to-end) testlari joylashgan. Testlar
**haqiqiy** backend va frontend serverlariga qarshi ishlaydi — Playwright hech
qanday serverni o'zi ko'tarmaydi (`playwright.config.ts` da `webServer` ataylab
yozilmagan).

## Oldindan shartlar

1. **Backend ishlab turishi kerak** — `http://127.0.0.1:8000`:

   ```bash
   cd backend
   ../.venv/Scripts/python.exe manage.py migrate
   ../.venv/Scripts/python.exe manage.py runserver
   ```

2. **Frontend ishlab turishi kerak** — `http://localhost:3000`:

   ```bash
   cd frontend
   npm run dev
   ```

3. **Demo ma'lumot ekilgan bo'lishi kerak** (`seed_demo`):

   ```bash
   cd backend
   ../.venv/Scripts/python.exe manage.py seed_demo
   ```

   Bu quyidagi hisoblarni yaratadi (parol hammasida `clickish-demo-2026`):

   | Email | Rol |
   |---|---|
   | `demo@clickish.dev` | Egasi (owner) |
   | `aziz@clickish.dev` | Admin |
   | `malika@clickish.dev` | A'zo |
   | `jasur@clickish.dev` | A'zo |
   | `nodira@clickish.dev` | Mehmon (guest) |

4. Chromium binary o'rnatilgan bo'lishi kerak:

   ```bash
   cd frontend
   npx playwright install chromium
   ```

## Ishga tushirish

```bash
cd frontend

npm run test:e2e                    # hammasi (list + html hisobot)
npm run test:e2e:ui                 # interaktiv UI rejim
npx playwright test e2e/auth.spec.ts        # bitta fayl
npx playwright test -g "presence"           # nom bo'yicha filtr
npx playwright test --headed --workers=1    # brauzerni ko'rib turib
```

HTML hisobot `playwright-report/` ichiga yoziladi (avtomatik ochilmaydi):

```bash
npx playwright show-report
```

## Manzillarni o'zgartirish

Standart qiymatlar: frontend `http://localhost:3000`, backend REST
`http://localhost:8000/api/v1`. Boshqa portda ishlatish uchun:

```bash
E2E_BASE_URL=http://localhost:3001 E2E_API_BASE_URL=http://localhost:8001/api/v1 npm run test:e2e
```

## Fayllar

| Fayl | Nima tekshiriladi |
|---|---|
| `fixtures.ts` | Umumiy yordamchilar: `login`, `apiLogin`, `USERS`, `gotoFirstList`, REST yordamchilari |
| `auth.spec.ts` | Kirish, noto'g'ri parol, chiqish, himoyalangan URL redirecti |
| `dashboard.spec.ts` | Ish maydoni bosh sahifasi: statistika, "Mening vazifalarim", "Jamoa" |
| `realtime.spec.ts` | WebSocket: `connection.ack`, `presence.sync`, `task.created`, `presence.join` |
| `smoke.spec.ts` | Asosiy sahifalar konsol/sahifa xatosisiz yuklanadi |

## Test ma'lumoti

- Test vazifalari **faqat REST API orqali** yaratiladi, DB'ga to'g'ridan-to'g'ri
  tegilmaydi.
- Yaratilgan vazifalar nomi **`E2E ` prefiksi** bilan boshlanadi va test oxirida
  o'chiriladi. Agar test yarim yo'lda uzilib qolsa, qoldiqni topish oson:
  ilovadagi qidiruvda `E2E` deb yozing.
- Har bir test o'z ma'lumotini yaratadi; mavjud `seed_demo` ma'lumoti faqat
  **o'qish** uchun ishlatiladi.

## Debug

```bash
# Qadam-baqadam inspektor bilan
npx playwright test e2e/auth.spec.ts --debug

# Yiqilgan testning trace faylini ochish
npx playwright show-trace test-results/<papka>/trace.zip
```

Trace, skrinshot faqat **xato** bo'lganda saqlanadi.

Foydali maslahatlar:

- `--headed` bilan brauzer ko'rinadi; `PWDEBUG=1` inspektorni ochadi.
- WebSocket testlari yiqilsa, avval backend Daphne orqali ishlayotganini
  tekshiring (`runserver` Channels bilan ASGI rejimida ko'tariladi) — oddiy
  WSGI serverda `ws://` ulanmaydi.
- `login()` hidratsiya tugashini kutadi: `networkidle` + qiymatni
  `inputValue()` bilan tasdiqlaydigan qayta urinish sikli. Login sekin ishlasa,
  frontend dev serverining birinchi kompilyatsiyasi tugaganini kuting.
- Konsol xatolari testi (`smoke.spec.ts`) **hech qanday** `console.error` va
  `pageerror` bo'lmasligini talab qiladi. Yiqilsa, xato matni assertion
  xabarida ko'rinadi.
