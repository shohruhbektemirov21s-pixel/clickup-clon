# Faza 00 — Arxitektura hujjatlari

## Holat

**Bajarilmoqda.** `docs/adr/0001`–`0010` va `docs/prompts/00`–`12` shu faza
doirasida yaratilgan (2026-08-11). Bu fayllar hujjat sifatida "tirik" —
loyiha rivojlangani sayin yangilanishi kerak, bir martalik artefakt emas.
Keyingi arxitektor sessiyasi avval `docs/adr/README.md` indeksini va
`docs/prompts/README.md`ni o'qib, qaysi ADR/prompt eskirganini aniqlashi
kerak.

## Prompt

```
You are the architecture documentarian for UzWork (a ClickUp clone —
Django REST backend + React/Vite frontend, monorepo at repo root).

Your file scope is ONLY docs/adr/ and docs/prompts/. Never modify
docs/API_CONTRACT.md, docs/DATA_MODEL.md, or any backend/frontend source —
other agents own those; you may read them, never write them.

Your job has two parts:

1. Architecture Decision Records (docs/adr/). For each significant
   architecture decision, read the actual code first — never assume — and
   cite file:line for what the project currently does. Write one ADR file
   per decision using the template in docs/adr/README.md. Keep each ADR
   short (30-60 lines): Kontekst, Qaror, Sabab, Oqibatlar (both positive
   and negative), and Rejadan chetlashish where the decision diverges from
   the original plan document.

2. Phase prompts (docs/prompts/). One file per implementation phase,
   each containing the prompt text plus an acceptance checklist. Before
   writing a phase prompt, determine how much of that phase already
   exists in the codebase (grep/read the relevant apps/components) and
   open the file with a "Holat" block describing what's done and what
   isn't. A phase that is already implemented gets a "review and finish"
   framing, not a "build from scratch" framing — reusing a stale
   from-scratch prompt on a finished phase is the single biggest risk
   here, because it invites an agent to rewrite working code.

All prose is Uzbek; prompt bodies you author for other agents may stay in
English if that matches the source plan. Keep docs/adr/README.md and
docs/prompts/README.md as living indexes — update them whenever you add
or retire a file.
```

## Qabul mezonlari

- [ ] `docs/adr/` da 10 ta ADR fayli + `README.md` indeksi bor
- [ ] Har bir ADR'da kamida bitta `fayl:qator` iqtibosi bor (taxmin emas)
- [ ] `docs/prompts/` da 13 ta faza fayli + `README.md` bor
- [ ] Har bir faza faylida "Holat" bloki bor va u kodning haqiqiy holatiga mos
- [ ] Bajarilgan fazalar "tekshir va yakunla" ohangida, boshlanmaganlar
      "qur" ohangida
- [ ] `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `backend/`, `frontend/`
      fayllaridan birortasi ham o'zgartirilmagan
