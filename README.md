# Clickish — ClickUp kloni

Jamoaviy vazifa boshqaruvi ilovasi: ish maydonlari, bo'limlar, ro'yxatlar,
vazifalar, izohlar va real vaqtli hamkorlik. Interfeys to'liq **o'zbek tilida**.

Monorepo: **Django REST** backend + **Next.js** frontend.

---

## Nimalar bor

| Imkoniyat | Tavsif |
|---|---|
| **Ish maydonlari** | Bo'lim → Jild → Ro'yxat → Vazifa iyerarxiyasi; yopiq (private) bo'limlar |
| **Vazifalar** | Status, ustuvorlik, muddat, biriktirilganlar, teglar, kuzatuvchilar, izohlar |
| **Drag & drop** | Kasr pozitsiyalar — ko'chirishda butun jadval qayta raqamlanmaydi |
| **Real vaqt** | WebSocket orqali vazifa, izoh va presence hodisalari; sahifa yangilanmaydi |
| **Granular huquqlar** | 49 ta ruxsat kodi, har bir ish maydonida rol × huquq matritsasi sozlanadi |
| **Rollar** | Egasi / Admin / A'zo / Mehmon — Egasining huquqlari qulflangan |
| **Takliflar** | Token bilan taklif → ro'yxatdan o'tish → avtomatik a'zolik |
| **Fayllar** | Vazifalarga hujjat va rasm biriktirish (bajarilgandan keyin ham) |
| **Chat** | Ish maydoni kanallari + shaxsiy yozishmalar, real vaqtli |
| **Email tekshiruvi** | Ro'yxatni ommaviy tekshirish (MX + SMTP) va taklifdan oldin manzil bor-yo'qligi |
| **Demo rejim** | Ro'yxatdan o'tmasdan sinab ko'rish tugmasi (env bayrog'i bilan boshqariladi) |
| **Boshqaruv paneli** | Ilova ichida admin bo'limi + kuchaytirilgan Django `/admin/` |

---

## Texnologiyalar

**Backend** — Django 5.2 · DRF · SimpleJWT · Channels 4 + Daphne (ASGI) ·
django-cors-headers · django-filter · drf-spectacular · WhiteNoise
**Ma'lumotlar bazasi** — dev'da SQLite, prod'da PostgreSQL (`DATABASE_URL` orqali)
**Frontend** — Next.js 16 (App Router) · React 19 · TypeScript · Tailwind ·
shadcn/ui · TanStack Query · Zustand · native WebSocket
**Testlar** — pytest + pytest-django (backend), Playwright (E2E)

Talab qilinadi: **Python 3.14**, **Node 22+**. Redis ixtiyoriy — bo'lmasa
Channels xotiradagi qatlamga tushadi.

---

## Ishga tushirish

Ikki yo'l bor. Kundalik ish uchun birinchisi qulayroq.

### 1) Lokal (venv + npm)

```bash
# backend — backend/ katalogidan
../.venv/Scripts/python.exe manage.py migrate
../.venv/Scripts/python.exe manage.py runserver     # http://127.0.0.1:8000

# frontend — frontend/ katalogidan
npm install
npm run dev                                          # http://localhost:3000
```

`backend/.env` faylini `backend/.env.example` dan nusxalang.

### 2) Docker Compose

```bash
cp .env.docker.example .env      # PowerShell: Copy-Item .env.docker.example .env
docker compose up -d --build     # backend o'zi migratsiya qiladi
```

PostgreSQL 16 + Redis 7 + backend + frontend ko'tariladi. Batafsil:
[`docs/DOCKER.md`](docs/DOCKER.md).

### Demo ma'lumot

Demo ma'lumot **ixtiyoriy** va standart holatda yo'q. Ilova bo'sh baza bilan
ishlaydi: ro'yxatdan o'tasiz, birinchi ish maydoningizni yaratasiz.

Demo ma'lumotni yaratish (parol hammasida `clickish-demo-2026`):

```bash
../.venv/Scripts/python.exe manage.py seed_demo
```

`demo@` (Egasi), `aziz@` (Admin), `jasur@` / `malika@` (A'zo), `nodira@`
(Mehmon) — hammasi `@clickish.dev`. Yaratgandan keyin `backend/.env` da
`DEMO_MODE=True` qo'ysangiz, kirish sahifasida **«Demo rejimda kirish»**
tugmasi paydo bo'ladi va parolsiz kiritadi.

Tugma `mehmon@clickish.dev` — `is_readonly=True` hisobiga kiritadi. Ilova
ichida uning ustida **«Demo — kuzatish rejimi»** tasmasi va **«Demodan
chiqish»** tugmasi turadi, ya'ni kirgan odam nega yozolmayotganini biladi va
chiqish yo'lini ko'radi. Cheklovning o'zi serverda
(`apps/core/access.py: READONLY_ALLOWED_CODES`); tasma faqat UI signali.

`seed_demo` `Jamoa bo'limi / Boshlash` ro'yxatini ham to'ldiradi. Bu
`bootstrap_workspace` ning teskarisi (u ro'yxatni ataylab bo'sh qoldiradi) va
ataylab: demo hisob kirganda aynan shu ro'yxatga tushadi, u bo'sh bo'lsa
butun demo "ma'lumot yo'q" bo'lib ko'rinardi.

Demo ma'lumotni olib tashlash (`seed_demo` ning teskarisi):

```bash
../.venv/Scripts/python.exe manage.py purge_demo         # faqat ko'rsatadi
../.venv/Scripts/python.exe manage.py purge_demo --yes   # haqiqatan o'chiradi
../.venv/Scripts/python.exe manage.py purge_demo --qa --yes   # + E2E qoldiqlari

# Demo rejimni SAQLAB, faqat eski namuna vazifalarni tozalash
../.venv/Scripts/python.exe manage.py purge_demo --only-placeholders --yes
```

`--only-placeholders` `bootstrap_workspace` ning eski versiyasi har bir yangi
ish maydoniga qo'yib ketgan uchta vazifani (`Birinchi vazifangizni yarating`
va h.k.) oladi. Faqat **tegilmaganlari** — izohi, fayli, biriktirilgani yoki
tavsifi bo'lganini foydalanuvchi o'ziniki qilib olgan deb hisoblab qoldiradi.
Demo ish maydoni va demo hisoblar tegilmaydi.

Buyruq `seed_demo` hisoblarini, ular egalik qilgan ish maydonlarini va
mazmunini oladi; staff/superuser hisobi hech qachon o'chmaydi, nishondan
tashqari ish maydoniga ega hisob esa ogohlantirish bilan qoldiriladi.

> ⚠️ `--yes` **qaytarib bo'lmaydi**, va u E2E to'plamini ishlamay qo'yadi —
> Playwright testlari `seed_demo` ish maydoniga tayanadi
> (`frontend/e2e/README.md`). E2E'dan oldin qayta `seed_demo` bajaring.

### Bosh sahifadagi ma'lumot

Landing (`/`) tizimga kirmagan mehmonga ko'rinadi va butun mazmunini bazadan
oladi — `GET /api/v1/public/showcase/` (API shartnomasi §14.1). Sahifada qo'lda
yozilgan namunaviy qator yo'q.

Jamlangan sonlar va ruxsat katalogi har doim qaytadi. Ish maydonining
**mazmuni** (bo'lim nomlari, vazifa sarlavhalari, faoliyat tasmasi) esa faqat
`backend/.env` da `SHOWCASE_WORKSPACE_ID` sozlangan bo'lsa. Bo'sh qoldirilsa —
standart holat — hech kimning yozuvi anonim ko'rinmaydi. Sozlansa: email hech
qachon chiqmaydi (faqat bosh harflar), yopiq bo'limlar nomsiz sanaladi, ammo
qolgan hamma narsa **butun internetga ochiq** deb hisoblanishi kerak.

---

## Testlar

```bash
# backend — backend/ katalogidan
../.venv/Scripts/python.exe -m pytest

# frontend — frontend/ katalogidan
npm run lint
npx tsc --noEmit
npm run build
npx playwright test          # E2E: serverlar ishlab turishi shart
```

E2E testlari haqiqiy brauzerda kirish, bosh sahifa, huquqlar matritsasi va
real vaqtli yangilanishni tekshiradi.

---

## Loyiha tuzilishi

```
clickup/
  backend/
    config/            settings, urls, asgi
    apps/
      accounts/        User (email login), JWT, profil, demo kirish
      workspaces/      Workspace, Member, Invitation, Space, Folder, List, Status,
                       RolePermission, SpaceMember
      tasks/           Task, Tag, biriktirilgan fayllar, tartiblash
      comments/        Izohlar
      core/            ruxsat katalogi, access layer, umumiy modellar
      realtime/        Channels consumer'lari va hodisa emitterlari
      chat/            kanallar, shaxsiy yozishmalar, xabarlar
      emailcheck/      ommaviy email tekshiruvi (sintaksis/MX/SMTP/API)
  frontend/
    src/app/           App Router sahifalari
    src/components/    UI, shell, settings, task, auth
    src/hooks/         TanStack Query hooklari, WebSocket kanallari
    e2e/               Playwright testlari
  docs/                PRD, DATA_MODEL, API_CONTRACT, UI_SPEC, DESIGN_PERMISSIONS, DOCKER
  .github/workflows/   CI va xavfsizlik skanerlari
```

---

## Hujjatlar

| Fayl | Mazmuni |
|---|---|
| [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) | **Majburiy shartnoma** — barcha endpointlar, xato formati, WebSocket hodisalari |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Modellar, constraint'lar, tartiblash strategiyasi |
| [`docs/DESIGN_PERMISSIONS.md`](docs/DESIGN_PERMISSIONS.md) | Ruxsat katalogi va matritsa dizayni |
| [`docs/UI_SPEC.md`](docs/UI_SPEC.md) | Ekranlar spetsifikatsiyasi |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Konteynerlar, muhit o'zgaruvchilari, xatolar |
| [`docs/PRD.md`](docs/PRD.md) | Mahsulot talablari |

API hujjati dev rejimida: `http://127.0.0.1:8000/api/docs/`.

---

## Xavfsizlik

Ilova quyidagi choralar bilan qattiqlashtirilgan:

- **Huquqlar serverda tekshiriladi.** Frontend `can()` helperi faqat tugmani
  ko'rsatish/yashirish uchun; har bir endpoint mustaqil tekshiradi.
- **404 vs 403 qoidasi.** Ish maydonidan tashqaridagi resurs har doim `404` —
  mavjudligi oshkor qilinmaydi. Ichkarida rol taqiqlasa `403`.
- **Egasi qulflangan.** `RolePermission` jadvalida `owner` qatori bo'lishi DB
  constraint bilan taqiqlangan; admin o'z rolining huquqini oshira olmaydi.
- **Rate limiting** — login (IP va email bo'yicha alohida), ro'yxatdan o'tish,
  taklif, demo kirish, fayl yuklash.
- **Fayl yuklash** — turlar ro'yxati (SVG/HTML/exe taqiqlangan), hajm limiti,
  fayl nomi serverda generatsiya qilinadi.
- **Prod tekshiruvlari** — `SECRET_KEY` zaif bo'lsa ilova ishga tushmaydi,
  HSTS, secure cookie'lar, CSP, WebSocket `Origin` validatsiyasi.

Xavfsizlik skanerlari (`pip-audit`, `bandit`, `npm audit`, `gitleaks`) har hafta
GitHub Actions orqali ishlaydi.

---

## Kelishuvlar

- API asosiy yo'li `/api/v1/`. `docs/API_CONTRACT.md` — **binding shartnoma**;
  o'zgartirilsa, hujjat ham o'sha commitda yangilanadi.
- Real vaqt hodisalari servis qatlamidan chiqariladi, view'lardan emas — shunda
  REST va WebSocket bir-biriga mos qoladi.
- Frontend'da server holati faqat TanStack Query orqali; Zustand faqat UI holati.
- Barcha foydalanuvchiga ko'rinadigan matn o'zbek tilida.

---

## Chat

Ish maydoni ichida **kanallar** va **shaxsiy yozishmalar** (DM) — `/w/{id}/chat`.

- Kanal ochiq (hamma a'zoga ko'rinadi) yoki yopiq bo'ladi. Ochiq kanalni
  o'qish uchun a'zolik shart emas, **yozish uchun** — «Qo'shilish».
- DM idempotent: `A→B` va `B→A` bitta yozishmaga tushadi (tartibdan qat'i
  nazar hisoblanadigan `dm_key` + DB constraint).
- Xabar **oddiy matn**, HTML emas — chat kiritishi saqlangan-XSS uchun eng
  keng darvoza, shuning uchun boy matn qabul qilinmaydi.
- Real vaqt: `ws/chat/{conversation_id}/`. Soket faqat o'qiydi, yuborish
  REST orqali — validatsiya, throttle va broadcast bitta joyda qoladi.

Batafsil: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) §14.2.

## Email tekshiruvi

Ommaviy ro'yxatni tekshirish (sintaksis → MX → SMTP `RCPT TO`):

```bash
# backend/ katalogidan
../.venv/Scripts/python.exe manage.py verify_emails royxat.csv \
    --output natija.csv --helo domeningiz.uz --mail-from probe@domeningiz.uz

# tashqi API bilan (ishonchliroq)
../.venv/Scripts/python.exe manage.py verify_emails royxat.csv \
    --output natija.csv --verifier zerobounce --api-key $KALIT
```

Chiqish: `email, status (valid|invalid|risky|unknown), sabab, tekshirilgan_vaqt`
+ qisqa hisobot. Domenga soniyasiga 1 so'rov, 2 marta qayta urinish, natija
oqim bilan yoziladi (katta ro'yxatda xotira to'lmaydi).

> **Chegara:** Gmail/Outlook SMTP tekshiruvni ataylab qiyinlashtiradi va
> ko'pincha `unknown` beradi. Ishonchlilik kerak bo'lsa `--verifier` ni
> tashqi xizmatga o'tkazing — interfeys almashtiriladigan qilib yozilgan
> (`apps/emailcheck/verifiers/`).

Ilova ichida: mas'ul tanlagichida va bo'lim a'zolari panelida email yozsangiz,
«Tekshirish» tugmasi manzil bor-yo'qligini aytadi va «Taklif qilish» beradi
(`POST workspaces/{id}/check-email/`, `member.invite` ruxsati bilan).
