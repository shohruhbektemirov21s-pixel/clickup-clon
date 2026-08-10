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
| **Granular huquqlar** | 48 ta ruxsat kodi, har bir ish maydonida rol × huquq matritsasi sozlanadi |
| **Rollar** | Egasi / Admin / A'zo / Mehmon — Egasining huquqlari qulflangan |
| **Takliflar** | Token bilan taklif → ro'yxatdan o'tish → avtomatik a'zolik |
| **Fayllar** | Vazifalarga hujjat va rasm biriktirish (bajarilgandan keyin ham) |
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
../.venv/Scripts/python.exe manage.py seed_demo     # demo ma'lumot (ixtiyoriy)
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
docker compose exec backend python manage.py seed_demo
```

PostgreSQL 16 + Redis 7 + backend + frontend ko'tariladi. Batafsil:
[`docs/DOCKER.md`](docs/DOCKER.md).

### Demo hisob

`seed_demo` quyidagilarni yaratadi (parol hammasida `clickish-demo-2026`):

| Email | Rol |
|---|---|
| `demo@clickish.dev` | Egasi |
| `aziz@clickish.dev` | Admin |
| `jasur@clickish.dev`, `malika@clickish.dev` | A'zo |
| `nodira@clickish.dev` | Mehmon |

Kirish sahifasidagi **«Demo rejimda kirish»** tugmasi parol yozmasdan kiritadi
(`DEMO_MODE=True` bo'lganda).

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
