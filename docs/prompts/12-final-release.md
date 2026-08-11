# Faza 12 — Yakuniy chiqarish

## Holat

**Boshlanmagan.** Loyihada versiya teglari, release notes, yoki "release
checklist" yo'q — `git tag` bo'sh (tekshirilmagan bo'lsa, sessiya boshida
tekshiring). Bu faza boshqa barcha fazalar (ayniqsa 06, 09, 10, 11 —
hozir WIP yoki qisman) tugagunga qadar mantiqiy ravishda boshlanishi
mumkin emas: chiqarish checklisti "hamma narsa tayyor" degan taxminga
tayanadi, va hozir bu taxmin noto'g'ri (kamida 5 ta uncommitted komponent,
docs/adr/0009'ning amalga oshirilmagan migratsiyasi bor).

## Prompt

```
Prepare a final release checklist for UzWork. This phase has NOT started
— there is no version tag, no release notes file, no documented release
process yet. Before treating this as "just write the checklist", verify
the actual blocking state:

1. Run git status and git log --oneline -20 (or equivalent) to see what's
   uncommitted and how far the current branch is from main. As of the
   last architecture pass, there were several substantial uncommitted
   frontend components (dashboard, ai, planner, notifications) and an
   accepted-but-unexecuted architecture decision
   (docs/adr/0009-status-modeli.md's StatusSet/Status removal) — a
   release cannot ship with either half-done.
2. Cross-check docs/prompts/README.md's phase index for anything still
   marked "Ishlanmoqda" or "Boshlanmagan" — those are real blockers,
   not just documentation gaps.
3. Confirm docs/API_CONTRACT.md's endpoint inventory count (stated at
   the top of the file) matches what backend/config/urls.py actually
   registers — a release with contract/code drift ships a lie to
   frontend consumers.
4. Confirm .github/workflows/ci.yml is green on the release commit for
   all five jobs (backend, backend-sqlite, frontend, e2e, docker).

Only once the above is genuinely clean: write a release checklist
covering version tagging, docs/DOCKER.md's prod-shaped run
(docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
--build), a smoke pass against that prod-shaped stack, and a rollback
plan (what to do if migrate fails on a real Postgres instance, given
docker-entrypoint.sh runs migrations automatically on boot).

Do not fabricate a "ready to ship" status — if blockers exist, report
them as a punch list instead of writing a checklist that assumes they're
resolved.
```

## Qabul mezonlari

- [ ] Barcha `docs/prompts/`dagi fazalar "Bajarildi" holatida (yoki
      chiqarishga xalaqit bermasligi aniq asoslangan)
- [ ] `docs/adr/0009-status-modeli.md` migratsiyasi yakunlangan yoki
      chiqarish doirasidan ataylab chiqarib tashlangani hujjatlashtirilgan
- [ ] `git status` toza — uncommitted ish yo'q
- [ ] `docs/API_CONTRACT.md` endpoint soni `config/urls.py` bilan mos
- [ ] CI'dagi barcha 5 job release commit'da yashil
- [ ] Prod-shaped stack (`docker-compose.prod.yml`) qo'lda smoke-test
      qilingan
- [ ] Rollback rejasi yozilgan (migratsiya prod'da muvaffaqiyatsiz
      bo'lsa nima qilish)
