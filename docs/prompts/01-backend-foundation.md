# Faza 01 — Backend fundamenti

## Holat

**Bajarildi.** Django 5.2 loyihasi to'liq ishlaydi: `backend/config/settings.py`
(env-asosli sozlash, JWT, throttle, xavfsizlik sarlavhalari, Sentry opt-in),
`backend/config/urls.py`, `backend/config/pagination.py`,
`backend/config/exceptions.py`. `apps.core` — abstrakt modellar
(`UUIDModel`, `TimeStampedModel`, `SoftDeleteModel`, `PositionedModel` —
`backend/apps/core/models.py`), ruxsat katalogi (`apps/core/permissions.py`)
va kirish qatlami (`apps/core/access.py`). `apps.accounts` — maxsus `User`
modeli (email = username), JWT auth, profil. CI'da bu faza to'liq qamrovda:
`django check`, `makemigrations --check`, `pytest --cov` (`.github/workflows/ci.yml`).

Keyingi sessiya buni **noldan qurmasin** — faqat quyidagi holatlarda qaytib
kelish kerak: yangi abstrakt model kerak bo'lsa, yangi throttle sinfi
qo'shilsa, yoki `docs/adr/0002-timezone.md` / `0008-pagination-rate-limit.md`
dagi in-flight o'zgarishlar (`TIME_ZONE`, sahifalash sonlari) yakunlanmagan
bo'lsa.

## Prompt

```
Verify and finish the backend foundation for UzWork (Django 5.2 + DRF +
simplejwt + Channels, at backend/). This phase is largely DONE — your job
is to audit it against docs/API_CONTRACT.md §1 (global conventions) and
docs/DATA_MODEL.md, close any gaps, and NOT rewrite what already works.

Check specifically:
- backend/config/settings.py: SECRET_KEY hardening, ALLOWED_HOSTS,
  DATABASE_URL via django-environ, CHANNEL_LAYERS/CACHES redis fallback,
  REST_FRAMEWORK block (auth, pagination, throttling, exception handler).
- apps/core/models.py: abstract bases only, no concrete models.
- apps/core/permissions.py + apps/core/access.py: the permission-code
  catalog and require_perm/require_membership_perm/require_space_perm
  helpers — confirm views resolve codes, never role ranks.
- apps/accounts: custom User (AUTH_USER_MODEL = "accounts.User"), JWT
  issuance/refresh/blacklist, registration, profile endpoints.
- CI gates in .github/workflows/ci.yml (backend + backend-sqlite jobs):
  confirm they still pass and still enforce makemigrations --check.

If you find a genuine gap (missing throttle for a new sensitive endpoint,
a permission code without catalog coverage, a settings drift against
docs/adr/0002 or docs/adr/0008), fix it narrowly. Do not restructure
settings.py, do not introduce a new app, do not change AUTH_USER_MODEL.
Update docs/API_CONTRACT.md in the same commit if behavior changes.
```

## Qabul mezonlari

- [ ] `python manage.py check` va `makemigrations --check --dry-run` toza
- [ ] `pytest` coverage `.coveragerc` dagi `fail_under` dan past emas
- [ ] Har bir sezgir endpoint (`auth`, `register`, `password_change`, ...)
      o'z throttle sinfiga ega (`settings.py:263-282`)
- [ ] Yangi ruxsat kodi qo'shilgan bo'lsa, `apps/core/permissions.py`da va
      `docs/API_CONTRACT.md` §1.7.1 da qayd etilgan
- [ ] `docs/adr/0002-timezone.md` va `0008-pagination-rate-limit.md` dagi
      in-flight holat hal qilingan bo'lsa, ADR'ning "Diqqat" izohi olib
      tashlangan
