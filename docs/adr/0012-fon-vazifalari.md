# 12 — Fon vazifalari: Celery + Redis

Holat: Qabul qilindi (qisman amalga oshirilgan) | Sana: 2026-08-11

## Kontekst

Loyihada hozirgacha hech qanday fon vazifasi infratuzilmasi bo'lmagan: har bir
ish so'rov davomida sinxron bajarilardi. Reja (§3) fon vazifalari uchun
**Celery + Redis** ni talab qiladi.

Redis allaqachon bor, lekin **ixtiyoriy**: `backend/config/settings.py:25`
`REDIS_URL=(str, "")` — ya'ni standart holat "yo'q". `:191-200` shu bo'yicha
Channels qatlamini tanlaydi — `REDIS_URL` bo'lsa `channels_redis`, bo'lmasa
`InMemoryChannelLayer` (`:199-200`). Xuddi shu naqsh kesh uchun ham
(`:206-215`). Bu **dev yo'lining asosi**: `CLAUDE.md` "venv + npm" yo'lini
birlamchi deb belgilaydi va u Redis'siz ishlaydi. Har qanday fon-vazifa qarori
buni buzmasligi shart.

Birinchi haqiqiy ehtiyoj ADR 0003 dan keladi. Soft delete faqat `Task`,
`Comment`, `Message` ga qo'llangan (`docs/adr/0003-soft-delete.md:18-20`), va
`SoftDeleteModel.delete()` (`backend/apps/core/models.py:59-61`) faqat
`deleted_at` ni yozadi — `super().delete()` chaqirilmaydi, demak Django
CASCADE **hech qachon ishga tushmaydi**. ADR 0003 buni ochiq salbiy oqibat
sifatida qayd etgan (`0003-soft-delete.md:51-57`): bola yozuvlarni
(`TaskAttachment`, `TaskActivity`) tozalash uchun "alohida tozalash joyi
(masalan, davriy job) yo'q". Bu ADR o'sha joyni beradi.

## Qaror

**Celery + Redis** fon vazifalari uchun standart qatlam bo'ladi.

- Broker va result backend — `REDIS_URL` (`settings.py:573-574`
  `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` shu qiymatga default qilingan,
  alohida env bilan ustidan yozish mumkin).
- **Broker bo'lmasa — eager.** `settings.py:578-580`
  `CELERY_TASK_ALWAYS_EAGER = env.bool(..., default=not CELERY_BROKER_URL)`:
  `REDIS_URL` bo'sh bo'lgan dev mashinada har bir task chaqiruvi joyida,
  jarayon ichida bajariladi. `CELERY_TASK_EAGER_PROPAGATES = True`
  (`:583`) — eager rejimda xato yutilmaydi.
- Import paytida ulanish ochilmaydi: `backend/config/celery.py` faqat `app`
  obyektini quradi (`:30` `Celery("uzwork")`, `:36` `config_from_object(...,
  namespace="CELERY")`, `:41` `autodiscover_tasks()`), va
  `backend/config/__init__.py:10` uni Django boot'ida ko'rinadigan qiladi.
- Faqat JSON serializatsiya (`settings.py:587-589`) — pickle emas.
- `acks_late=True` + `prefetch_multiplier=1` (`:597-598`), soft/hard vaqt
  limitlari 600/660s (`:601-602`).
- **Birinchi haqiqiy iste'molchi — ADR 0003 qoldirgan tozalash joyi.**
  `CELERY_BEAT_SCHEDULE` (`:619-632`) da ikkita yozuv bor:
  `purge-soft-deleted` → `core.purge_soft_deleted`, har kuni 03:30
  (`:621-624`), va `flush-expired-tokens` → `core.flush_expired_tokens`,
  04:00 (`:628-631`). Saqlash muddati sozlanadi:
  `SOFT_DELETE_RETENTION_DAYS` (`:610`, default 30) va `PURGE_BATCH_SIZE`
  (`:614`, default 500).

## Sabab

Celery — Django ekotizimidagi standart tanlov va Redis allaqachon stack'da
(`requirements.txt:45` `redis==8.1.0`, `:8` `channels_redis==4.3.0`,
`docker-compose.yml:38-46` `redis` servisi). Ikkinchi broker (RabbitMQ)
qo'shish operatsion narxni ikki barobar oshirardi va hech qanday yangi
imkoniyat bermasdi.

`TASK_ALWAYS_EAGER` fallback'i — bu qarordagi eng muhim band. Usiz "venv + npm"
yo'li Redis'ni **majburiy** qilib qo'yardi va `CLAUDE.md` da yozilgan birlamchi
ish oqimini buzardi. Eager rejim mukammal emas (parallellik va retry semantikasi
prod'dagidek emas), lekin dev uchun to'g'ri murosa: kod bir xil yoziladi, faqat
bajarilish joyi boshqa.

Soft-delete tozalashini birinchi iste'molchi qilib tanlash ham ataylab: u
(a) haqiqiy va allaqachon hujjatlashtirilgan bo'shliq, (b) davriy, foydalanuvchi
kutmaydigan ish — ya'ni aynan fon vazifasi shakli, (c) `deleted_at` indeksi
allaqachon bor (`core/models.py:47` `db_index=True`), demak so'rov arzon.

## Oqibatlar

**Ijobiy:** uzoq davom etadigan ish (fayl tozalash, ommaviy email tekshiruvi,
bildirishnoma fan-out) endi so'rov-javob siklidan chiqarilishi mumkin. ADR
0003 ochiq qoldirgan bo'shliq yopiladi.

**Salbiy — prod'da yangi jarayon turlari.** `celery worker` va `celery beat`
alohida konteyner/servis sifatida ishlashi kerak; ular yiqilsa, ilova
"ishlayotgandek" ko'rinadi, lekin davriy ish jimgina to'xtaydi. Monitoring
kerak — hozir yo'q.

**Salbiy — eager va prod semantikasi farq qiladi.** Dev'da task chaqiruvchi
tranzaksiya ichida, sinxron bajariladi; prod'da alohida jarayonda, kechikish
bilan. Tranzaksiya commit bo'lmasdan turib task navbatga qo'yilsa, worker hali
bazada yo'q qatorni o'qiydi — bu klassik xato va u faqat prod'da ko'rinadi.
Har bir task uchun `transaction.on_commit(...)` odat qilinishi kerak.

**Salbiy — hozircha ishlamaydi (muhim).** 2026-08-11 ishchi daraxti holati:

1. `celery` **`backend/requirements.txt` da yo'q** (58 ta pin, `celery`/`kombu`/
   `billiard` bo'yicha nol moslik). U faqat lokal `.venv` da tasodifan bor.
   `settings.py:13` `from celery.schedules import crontab` — ya'ni toza
   muhitda **Django umuman boot bo'lmaydi**, CI shu yerda qulaydi.
2. `backend/apps/` da bironta ham `tasks.py` yo'q — `autodiscover_tasks()`
   (`celery.py:41`) hech nima topmaydi.
3. Beat jadvalidagi ikkala task ham mavjud emas: `purge_soft_deleted` va
   `flush_expired_tokens` butun repoda faqat `settings.py:618,622,629` da
   uchraydi. Beat ularni `NotRegistered` bilan rad etadi.
4. `settings.py:618` ishora qilgan `manage.py purge_soft_deleted` buyrug'i yo'q
   (`backend/apps/core/management/commands/` da faqat `purge_demo.py`,
   `seed_demo.py`, `uzbekify_defaults.py`).
5. `backend/.env.example` da bironta `CELERY_*`, `SOFT_DELETE_RETENTION_DAYS`
   yoki `PURGE_BATCH_SIZE` yo'q.
6. `docker-compose.yml` va `docker-compose.prod.yml` da worker/beat servisi yo'q.

Shuning uchun bu ADR holati **"qisman amalga oshirilgan"**: qaror qabul
qilingan va sozlamalar yozilgan, lekin ishlaydigan zanjir yo'q. Yuqoridagi
1-band — **bloklovchi regressiya**, u tuzatilmaguncha CI qizil qoladi.

## Rejadan chetlashish

Yo'q — reja §3 aynan Celery + Redis ni ko'rsatadi. `TASK_ALWAYS_EAGER`
fallback'i rejada aniq yozilmagan bo'lishi mumkin, lekin u rejaga zid emas:
u faqat brokerless dev muhitini qo'llab-quvvatlaydi.
