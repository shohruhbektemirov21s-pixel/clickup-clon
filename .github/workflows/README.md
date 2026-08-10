# GitHub Actions workflow'lari

Bu katalogdagi workflow'lar ClickUp klon monorepo'si (Django backend + Next.js frontend) uchun CI/CD ni ta'minlaydi.

---

## `ci.yml` — asosiy CI

**Qachon ishlaydi:** `main` ga `push` va `main` ga qaratilgan `pull_request`.

Ikkita **mustaqil** job (biri ikkinchisini kutmaydi):

### 1) `backend` — Django 5.2 / Python 3.14

- Service konteynerlar: **PostgreSQL 16** (prod DB shu — SQLite emas) va **Redis 7** (Channels uchun).
- `pip install -r backend/requirements.txt`, pip keshi `backend/requirements.txt` bo'yicha.
- Qadamlar:
  1. `manage.py check`
  2. `manage.py makemigrations --check --dry-run` — **migratsiya drift gate**: model o'zgargan, lekin migratsiya yozilmagan bo'lsa CI qulaydi.
  3. `manage.py migrate --noinput`
  4. `pytest -q`
  5. `ruff check` + `ruff format --check` — `ruff` `requirements.txt` da yo'q, shuning uchun workflow ichida o'rnatiladi va **non-blocking** (`continue-on-error: true`). Kod bazasi tozalangach `continue-on-error` ni olib tashlash kerak.
- Env o'zgaruvchilar `backend/.env.example` bilan sinxron: `DEBUG=False`, `SECRET_KEY` (CI-only dummy), `ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `CORS_ALLOWED_ORIGINS`, token/throttle sozlamalari.

### 2) `frontend` — Next.js / Node 22

- npm keshi `frontend/package-lock.json` bo'yicha.
- `npm ci` → `npm run lint` → `npx tsc --noEmit` → `npm run build`.
- Build uchun `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_BASE_URL`, `NEXT_PUBLIC_API_MODE` beriladi (`frontend/.env.example` bilan mos).

---

## `security.yml` — xavfsizlik skanerlari

**Qachon ishlaydi:** haftalik `schedule` (har dushanba 04:00 UTC), har `pull_request`, va qo'lda `workflow_dispatch`.

| Job | Nima qiladi |
| --- | --- |
| `python` | `pip-audit` (bog'liqliklardagi CVE), `bandit -r backend/apps backend/config` (statik tahlil), `manage.py check --deploy` (prod sozlama tekshiruvi) |
| `frontend` | `npm audit --audit-level=high` |
| `secrets` | `gitleaks/gitleaks-action@v2` — repo tarixida sir qidiradi (`fetch-depth: 0`) |

**Hammasi `continue-on-error: true`** — mavjud kod bazasi hali toza emas, shuning uchun bu workflow PR ni bloklamaydi. Har bir skaner natijasi **Job Summary** ga (`$GITHUB_STEP_SUMMARY`) yoziladi, shuning uchun natijani ko'rish uchun logni ochish shart emas.

Kod bazasi tozalangach `continue-on-error` ni bosqichma-bosqich olib tashlang (tavsiya etilgan tartib: gitleaks → pip-audit → npm audit → bandit → check --deploy).

---

## `../dependabot.yml`

Haftalik (dushanba) yangilanish PR'lari:

- `pip` → `/backend`
- `npm` → `/frontend`
- `github-actions` → `/`

Har biri uchun `open-pull-requests-limit: 5`, commit prefiksi `chore(deps)` / `chore(ci)`.

---

## `../pull_request_template.md`

O'zbekcha PR shabloni: o'zgarish tavsifi, tekshirish usuli va **xavfsizlik checklist'i** (workspace scope, 404-vs-403, mass assignment, throttle, migratsiya reverse, `docs/API_CONTRACT.md`, o'zbekcha UI matni, testlar).

---

## Kerakli secret'lar

CI ishga tushishi uchun **hech qanday majburiy secret yo'q**. Barcha CI qiymatlari workflow ichidagi dummy'lar.

| Secret | Majburiymi | Nima uchun |
| --- | --- | --- |
| `GITHUB_TOKEN` | Yo'q — GitHub avtomatik beradi | gitleaks action uchun |
| `GITLEAKS_LICENSE` | Faqat repo GitHub **Organization** ga tegishli bo'lsa | gitleaks-action v2 organization repolarida litsenziya talab qiladi. Shaxsiy/public repoda kerak emas — bo'sh qolsa job shunchaki non-blocking tarzda tushadi. |

Qo'shish: `Settings → Secrets and variables → Actions → New repository secret`.

---

## Lokal takrorlash

Windows'da venv global aktivatsiya qilinmagan — Python'ni to'liq yo'l bilan chaqiring.

```bash
# Backend (backend/ ichidan)
../.venv/Scripts/python.exe manage.py check
../.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
../.venv/Scripts/python.exe manage.py migrate
../.venv/Scripts/python.exe -m pytest -q

# Lint (ixtiyoriy, CI'da non-blocking)
../.venv/Scripts/python.exe -m pip install ruff
../.venv/Scripts/python.exe -m ruff check .
../.venv/Scripts/python.exe -m ruff format --check .

# Xavfsizlik
../.venv/Scripts/python.exe -m pip install pip-audit bandit
../.venv/Scripts/python.exe -m pip_audit -r requirements.txt
../.venv/Scripts/python.exe -m bandit -r apps config -ll
../.venv/Scripts/python.exe manage.py check --deploy
```

```bash
# Frontend (frontend/ ichidan)
npm ci
npm run lint
npx tsc --noEmit
npm run build
npm audit --audit-level=high
```

CI PostgreSQL'da ishlaydi, lokal dev esa odatda SQLite'da. Lokalda CI bilan bir xil sharoitni takrorlash uchun `backend/.env` da:

```
DATABASE_URL=postgres://clickup:clickup@localhost:5432/clickup_ci
REDIS_URL=redis://localhost:6379/0
```

Workflow YAML'ini o'zgartirgandan keyin sintaksisni tekshirish:

```bash
.venv/Scripts/python.exe -c "import yaml,sys; yaml.safe_load(open(sys.argv[1],encoding='utf-8')); print('OK', sys.argv[1])" .github/workflows/ci.yml
```

---

## Konvensiyalar

- Action versiyalari **major tag** bilan pin qilingan (`@v4`, `@v5`, `@v2`) — Dependabot `github-actions` ularni yangilab turadi.
- Har bir workflow'da `permissions: contents: read` (eng kam huquq) va `concurrency` bilan eski run'lar bekor qilinadi.
- Workflow fayllarida **hech qachon** haqiqiy sir yozilmaydi — faqat `${{ secrets.* }}` yoki CI-only dummy qiymat.
