# Docker bilan ishlash qo'llanmasi

Bu hujjat ClickUp klonini Docker Compose orqali ishga tushirishni tushuntiradi.

> **Muhim:** Docker — bu *muqobil* yo'l. Kundalik ishlab chiqish uchun asosiy usul
> hamon `.venv` + `npm run dev` bo'lib qoladi (`CLAUDE.md` ga qarang). Docker
> prod'ga yaqin muhitni (PostgreSQL 16 + Redis 7 + Daphne) sinash uchun kerak.

---

## 1. Nima ishga tushadi

| Servis     | Image              | Port (dev)  | Vazifasi |
|------------|--------------------|-------------|----------|
| `db`       | `postgres:16-alpine` | `5432`    | Asosiy ma'lumotlar bazasi |
| `redis`    | `redis:7-alpine`   | `6379`      | Channels layer (WebSocket broadcast) |
| `backend`  | `backend/Dockerfile` | `8000`    | Django 5.2 + DRF + Channels, **Daphne** (ASGI) |
| `frontend` | `frontend/Dockerfile` | `3000`   | Next.js 16, `standalone` build |

Nomlangan volume'lar: `pgdata` (Postgres), `redisdata` (AOF), `static`
(collectstatic natijasi), `media` (yuklangan fayllar).

Ishga tushish tartibi majburiy: `backend` faqat `db` va `redis` **healthy**
bo'lgandan keyin, `frontend` esa `backend` healthy bo'lgandan keyin startlaydi.

---

## 2. Birinchi marta ishga tushirish

Repo ildizidan (`C:\Users\a.abdusalomov\Desktop\clickup`):

```powershell
# 1) env faylini tayyorlang
Copy-Item .env.docker.example .env

# 2) .env ni oching va kamida POSTGRES_PASSWORD va SECRET_KEY ni o'zgartiring
notepad .env

# 3) build qiling va ko'taring
docker compose up -d --build
```

Bash/Git Bash uchun:

```bash
cp .env.docker.example .env
docker compose up -d --build
```

Birinchi build 5–15 daqiqa olishi mumkin: backend image'ida Python 3.14 uchun
tayyor wheel topilmagan paketlar (`cryptography`, `nh3`, `rpds-py`) Rust/C bilan
kompilyatsiya qilinishi mumkin. Keyingi build'lar layer keshidan foydalanadi.

Holatni tekshirish:

```bash
docker compose ps
```

Hammasi `healthy` bo'lganda:

- Frontend — <http://localhost:3000>
- API — <http://localhost:8000/api/v1/health/>
- Swagger — <http://localhost:8000/api/docs/> (`DEBUG=True` yoki `EXPOSE_API_DOCS=True` bo'lganda)
- Django admin — <http://localhost:8000/admin/> (yo'l `.env` dagi `ADMIN_URL` bilan o'zgaradi)

---

## 3. Migratsiyalar

Migratsiyalar **avtomatik** bajariladi: `backend/docker-entrypoint.sh` har
startda bazani kutadi, so'ng `manage.py migrate --noinput` ni ishga tushiradi
(`RUN_MIGRATIONS=1`).

Qo'lda bajarish kerak bo'lsa:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py showmigrations
```

Yangi migratsiya yaratish (kod bind-mount qilinganligi uchun fayl host'da ham
paydo bo'ladi):

```bash
docker compose exec backend python manage.py makemigrations
```

> Konteyner ichida `python` allaqachon `PATH` da (`/opt/venv/bin/python`) —
> `../.venv/Scripts/python.exe` prefiksi kerak emas.

---

## 4. Superuser yaratish

```bash
docker compose exec backend python manage.py createsuperuser
```

Interaktiv so'rovlar uchun `exec` (`run` emas) ishlatilgani muhim. Agar terminal
TTY bermasa:

```bash
docker compose exec -it backend python manage.py createsuperuser
```

---

## 5. Demo ma'lumotlar (`seed_demo`)

```bash
docker compose exec backend python manage.py seed_demo
```

Yoki har startda avtomatik bajarilishi uchun `.env` da:

```
RUN_SEED_DEMO=1
```

so'ng `docker compose up -d backend`. Bir marta yurgizgandan keyin buni yana
`0` ga qaytaring.

Boshqa email bilan:

```bash
docker compose exec backend python manage.py seed_demo --email siz@example.com
```

---

## 6. Loglar

```bash
docker compose logs -f                 # hammasi
docker compose logs -f backend         # faqat Django/Daphne
docker compose logs -f frontend
docker compose logs --tail=200 db
```

Entrypoint bosqichlari `[entrypoint] ...` prefiksi bilan chiqadi — DB kutish,
migratsiya, collectstatic shu yerda ko'rinadi.

---

## 7. Kod o'zgarishlarini qo'llash

**Backend.** `./backend` katalogi konteynerga bind-mount qilingan, lekin Daphne'da
avtomatik reload yo'q. Shuning uchun:

```bash
docker compose restart backend
```

Bu rebuild emas — bir necha soniya. Rebuild faqat `requirements.txt` o'zgarganda
kerak:

```bash
docker compose up -d --build backend
```

**Frontend.** Image `next build` natijasidan (`standalone`) yig'iladi, bind-mount
yo'q. Har o'zgarishda:

```bash
docker compose up -d --build frontend
```

Shu sababli frontend ustida faol ishlayotganda lokal `npm run dev` (port 3000)
ancha qulayroq — Docker'dagi `frontend` ni to'xtatib qo'ying:

```bash
docker compose stop frontend
```

---

## 8. To'xtatish va tozalash

```bash
docker compose stop            # konteynerlarni to'xtatadi, ma'lumot saqlanadi
docker compose down            # konteyner + tarmoqni o'chiradi, volume'lar QOLADI
docker compose down -v         # volume'larni ham o'chiradi — BAZA YO'QOLADI
docker compose down -v --rmi local   # image'larni ham o'chiradi
```

Faqat bitta volume'ni tozalash:

```bash
docker compose down
docker volume rm clickup_pgdata
docker compose up -d
```

> Volume nomlari `clickup_` prefiksi bilan — bu `docker-compose.yml` dagi
> `name: clickup` dan keladi.

Toza holatdan boshlash (nol nuqta):

```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

---

## 9. Prod override bilan ishlatish

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Dev'dan farqlari:

- **Bind-mount yo'q** — image o'zi artefakt; kod o'zgarsa qayta build kerak.
- `restart: unless-stopped` — barcha servislarda.
- `DEBUG=False`, `RUN_COLLECTSTATIC=0` (static build vaqtida yig'ilgan, WhiteNoise
  uni ManifestStaticFilesStorage orqali beradi).
- `db` va `redis` host'ga **hech qanday port ochmaydi**.
- `backend` va `frontend` faqat `127.0.0.1` ga bog'lanadi — oldiga TLS terminatsiya
  qiluvchi reverse proxy (nginx / Caddy / Traefik) qo'yiladi.
- CPU/RAM limitlari (`deploy.resources`).

Prod uchun `.env` da albatta o'zgartiring:

```
SECRET_KEY=<kamida 50 belgili tasodifiy qiymat>
POSTGRES_PASSWORD=<kuchli parol>
ALLOWED_HOSTS=sizning-domen.uz,backend,127.0.0.1
CORS_ALLOWED_ORIGINS=https://sizning-domen.uz
CSRF_TRUSTED_ORIGINS=https://sizning-domen.uz
WS_ALLOWED_ORIGINS=https://sizning-domen.uz
NEXT_PUBLIC_API_BASE_URL=https://sizning-domen.uz/api/v1
NEXT_PUBLIC_WS_BASE_URL=wss://sizning-domen.uz
```

`DEBUG=False` va `NUM_PROXIES=1` ni `docker-compose.prod.yml` o'zi o'rnatadi —
`.env` da yozish shart emas.

> **`SECRET_KEY` haqida.** `settings.py` `DEBUG=False` bo'lganda kalitni
> tekshiradi: kamida 50 belgi bo'lishi va `dev-`, `test-`,
> `django-insecure-` bilan boshlanmasligi kerak. Aks holda konteyner
> `ImproperlyConfigured` bilan darhol yiqiladi. `ALLOWED_HOSTS` ham bo'sh
> bo'lmasligi va `*` saqlamasligi shart.

> **Reverse proxy.** `DEBUG=False` da `SECURE_SSL_REDIRECT` yoqiladi, lekin
> `SECURE_PROXY_SSL_HEADER` ham o'rnatiladi. Ya'ni proxy `X-Forwarded-Proto:
> https` sarlavhasini uzatsa, redirect bo'lmaydi. Proxy bu sarlavhani
> yubormasa — cheksiz redirect halqasi paydo bo'ladi; o'shanda proxy'ni
> to'g'rilang (afzal) yoki `.env` da `SECURE_SSL_REDIRECT=False` qiling.

`SECRET_KEY` generatsiya qilish:

```bash
docker compose run --rm backend python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

> `!reset` / `!override` YAML teglari `docker-compose.prod.yml` da ishlatilgan —
> ular Docker Compose **v2.24+** talab qiladi. `docker compose version` bilan
> tekshiring.

Konfiguratsiyani ishga tushirmasdan tekshirish:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

---

## 10. Muhit o'zgaruvchilari qanday ishlaydi

Uch qatlam bor, ustuvorlik pastdan yuqoriga:

1. `backend/.env` — konteyner ichida ham o'qiladi (bind-mount tufayli).
   django-environ `read_env()` **`setdefault`** ishlatadi, ya'ni haqiqiy env
   o'zgaruvchisi bo'lsa, `.env` dagi qiymat **e'tiborsiz qoldiriladi**.
2. Repo ildizidagi `.env` → compose `env_file` orqali konteynerga uzatiladi.
3. `docker-compose.yml` dagi `environment:` bloki — eng ustun.

Shuning uchun `DATABASE_URL` va `REDIS_URL` `.env.docker.example` da **yo'q**:
ularni compose `db`/`redis` servis nomlaridan yig'ib, `environment:` orqali
beradi. Bu `backend/.env` dagi `sqlite:///db.sqlite3` ni ustidan yozadi.

`NEXT_PUBLIC_*` alohida holat: bular `next build` paytida bundle ichiga
**yozib qo'yiladi**. `docker run -e` bilan keyin o'zgartirib bo'lmaydi —
faqat `--build` bilan.

---

## 11. Tez-tez uchraydigan xatolar

### `env file .env not found`
Repo ildizida `.env` yo'q. `Copy-Item .env.docker.example .env` bajaring.

### `variable is not set. Defaulting to a blank string` → `POSTGRES_USER`
`.env` fayli ildizda emas yoki `POSTGRES_*` qatorlari o'chirilgan. Compose
`${...}` ni faqat **repo ildizidagi `.env`** dan oladi.

### `port is already allocated` (5432 / 6379 / 8000 / 3000)
Host'da o'sha port band (masalan lokal Postgres yoki `manage.py runserver`).
`.env` da portni o'zgartiring:

```
POSTGRES_PORT=5433
BACKEND_PORT=8001
```

### `ImproperlyConfigured: SECRET_KEY is missing, weak or a development placeholder`
`DEBUG=False` bilan ishga tushirdingiz, lekin `SECRET_KEY` hali `dev-...`.
Yangi kalit generatsiya qiling (9-bo'limga qarang) va `.env` ga yozing.

### `ImproperlyConfigured: ALLOWED_HOSTS must be set when DEBUG is off`
`.env` dagi `ALLOWED_HOSTS` bo'sh. Domeningizni, `backend` va `127.0.0.1` ni
kiriting.

### `DisallowedHost at /` yoki healthcheck `unhealthy`
`ALLOWED_HOSTS` da `127.0.0.1` va `backend` bo'lishi shart — healthcheck
konteyner ichidan `http://127.0.0.1:8000/api/v1/health/` ga so'rov yuboradi.

Prod'da healthcheck bu so'rovga `X-Forwarded-Proto: https` sarlavhasini
qo'shadi, chunki `DEBUG=False` da `SECURE_SSL_REDIRECT` yoqiq — busiz 301
qaytib, konteyner hech qachon `healthy` bo'lmasdi (va `frontend` ham
startlamasdi, chunki u `service_healthy` ni kutadi).

### Frontend startlamayapti, `dependency failed to start`
`backend` `healthy` bo'lmaguncha `frontend` kutadi. Avval
`docker compose logs backend` ni ko'ring — sabab deyarli har doim yuqoridagi
konfiguratsiya xatolaridan biri.

### Frontend'da CORS yoki `Failed to fetch`
`CORS_ALLOWED_ORIGINS` frontend origin'iga (`http://localhost:3000`) mos
kelishini va `NEXT_PUBLIC_API_BASE_URL` to'g'ri ekanini tekshiring. Brauzer
konteyner tarmog'ini ko'rmaydi — shuning uchun bu qiymat `http://backend:8000`
emas, `http://localhost:8000` bo'lishi kerak.

### WebSocket ulanmayapti
`REDIS_URL` o'rnatilgan bo'lsa Channels Redis layer'dan foydalanadi. Tekshiring:

```bash
docker compose exec redis redis-cli ping     # PONG
docker compose exec backend python -c "import os; print(os.environ.get('REDIS_URL'))"
```

### `exec /usr/local/bin/docker-entrypoint.sh: no such file or directory`
Skript CRLF bilan saqlangan. `backend/Dockerfile` da `sed -i 's/\r$//'` buni
tuzatadi; agar baribir chiqsa, `git config core.autocrlf input` qilib faylni
qayta checkout qiling.

### `password authentication failed for user`
`.env` dagi `POSTGRES_PASSWORD` ni **mavjud** `pgdata` volume'i yaratilgandan
keyin o'zgartirgansiz. Postgres parolni faqat birinchi initdb'da o'rnatadi:

```bash
docker compose down -v      # DIQQAT: baza o'chadi
docker compose up -d
```

### Backend `db` ga ulana olmayapti
`docker compose logs backend` da `[entrypoint] waiting for the database ...`
takrorlanaveradi. `docker compose logs db` ni ko'ring — odatda initdb xatosi
yoki eski/buzilgan `pgdata`. Kutish limiti `.env` dagi `DB_WAIT_RETRIES` va
`DB_WAIT_DELAY` bilan sozlanadi (default 60 × 2s = 2 daqiqa).

### `next build` da TypeScript xatosi
Build image ichida to'xtaydi. Avval lokal tekshiring:

```bash
cd frontend
npm run build
```

### Static fayllar (admin CSS) ko'rinmayapti
`RUN_COLLECTSTATIC=1` ekanini va `static` volume mavjudligini tekshiring:

```bash
docker compose exec backend ls /app/staticfiles | head
docker compose exec backend python manage.py collectstatic --noinput
```

### Build juda sekin / disk to'lib ketdi
```bash
docker builder prune          # build keshi
docker system df              # nima joy egallayotganini ko'rish
docker system prune -a        # DIQQAT: ishlatilmayotgan hamma image o'chadi
```

---

## 12. Foydali buyruqlar to'plami

```bash
# konteyner ichiga kirish
docker compose exec backend bash
docker compose exec frontend sh          # alpine — bash yo'q

# Django shell
docker compose exec backend python manage.py shell

# testlar
docker compose exec backend python -m pytest

# psql
docker compose exec db psql -U clickup -d clickup

# baza dump / restore
docker compose exec db pg_dump -U clickup clickup > backup.sql
docker compose exec -T db psql -U clickup -d clickup < backup.sql

# resurs sarfi va jarayonlar
docker stats
docker compose top
```
