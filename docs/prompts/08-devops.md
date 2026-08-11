# Faza 08 — DevOps (Docker, CI/CD)

## Holat

**Bajarildi.** `docker-compose.yml` (dev: db + redis + backend + frontend),
`docker-compose.prod.yml` (prod override), `backend/Dockerfile` va
`frontend/Dockerfile` (ikkalasi ham multi-stage), `backend/docker-entrypoint.sh`
(DB kutish + migratsiya + CMD). `.github/workflows/ci.yml` — besh job:
`backend` (Linux/Postgres, coverage darvozasi + OpenAPI ratchet),
`backend-sqlite` (Windows/SQLite), `frontend` (lint+tsc+build), `e2e`
(Playwright haqiqiy stack ustida), `docker` (ikkala image ham quriladimi).
`.github/workflows/security.yml` alohida mavjud. `docs/DOCKER.md` —
konteyner ish oqimi va zaxira nusxalash.

## Prompt

```
Verify and finish DevOps for UzWork. This phase is DONE across dev
(venv+npm), Docker Compose, and CI — audit against what's already
working, do not restructure the pipeline speculatively.

Check specifically:
- .github/workflows/ci.yml's SCHEMA_UNIQUE_ERROR_BUDGET (currently "54",
  see the comment at ci.yml:40-43): this is a RATCHET, only allowed to
  move down as spectacular warnings get fixed one serializer_class at a
  time. If your work adds a new APIView without serializer_class, the
  budget check will catch it — fix the APIView, don't raise the budget.
- backend/.coveragerc's fail_under (currently 83%, per ci.yml:37-38's
  comment): same ratchet discipline — don't lower it to make a red build
  pass.
- docker-compose.yml / docker-compose.prod.yml: confirm any new backend
  app (apps.notifications, apps.chat, apps.emailcheck are recent
  additions per `git log`) doesn't need new env vars that are missing
  from .env.docker.example.
- If docs/adr/0010-api-tiplari.md's api/openapi.json + drift-check has
  been implemented, wire it into ci.yml's existing "OpenAPI sxemasi
  (ratchet)" step (ci.yml:171-219) rather than adding a parallel job —
  that step already generates the schema once per run.

Do not add a new CI provider, do not remove the Windows/SQLite job (it
exists specifically because position-column collation and icontains
semantics differ between SQLite and PostgreSQL — removing it would
silently drop that coverage).
```

## Qabul mezonlari

- [ ] `docker compose up -d --build` toza ishga tushadi, backend o'zi
      migratsiya qiladi
- [ ] CI'dagi barcha 5 job (backend, backend-sqlite, frontend, e2e,
      docker) yashil
- [ ] Coverage va OpenAPI-xato budjetlari faqat pasaygan, ko'tarilmagan
- [ ] Yangi ilova/env-o'zgaruvchi qo'shilgan bo'lsa,
      `.env.docker.example` va `backend/.env.example` sinxron
- [ ] `docs/adr/0010` bo'yicha `api/openapi.json` drift-check qo'shilgan
      bo'lsa, mavjud OpenAPI qadamiga integratsiya qilingan, alohida
      dublikat job emas
