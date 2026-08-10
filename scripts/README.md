# Operator scripts

Backup and restore for the production stack, plus a couple of measurements CI
depends on. Everything here is meant to be run by a person on a bad day, so it
verifies more than it assumes and it never fails silently.

> **Link me from `docs/DOCKER.md`.** Its §12.1 ("Nimani saqlash kerak") is
> correct and complementary — keep it. Its §12.2 ("Qo'lda olish") is a
> copy-pasteable `pg_dump` + `tar` recipe that somebody has to remember to
> run; that is the part this directory replaces. The `docs/` owner should
> swap §12.2 for a link to `scripts/README.md`, so there is one backup
> procedure instead of two that drift apart.
>
> One thing `backup.sh` deliberately does **not** cover, and §12.1 is right
> about: the repo-root **`.env`**. It holds `SECRET_KEY` and the database
> password, it is not reachable from inside the backup container, and writing
> secrets into a backup volume that gets synced to object storage is a worse
> problem than the one it solves. Keep `.env` in a secrets manager. Losing it
> costs every issued JWT; losing it *together with* the database costs
> everything.

| File | What it is |
|---|---|
| `backup.sh` | One backup: PostgreSQL dump + uploaded media + checksums. Verifies the dump before declaring success. |
| `backup-loop.sh` | The scheduler. Entrypoint of the compose `backup` service; runs `backup.sh` daily. |
| `restore.sh` | Guided restore: `--list`, `--check`, then the real thing. Takes a safety dump of the current database first. |

---

## Why this exists

`pgdata` is a **local named volume**. Every task, comment, attachment and
audit row in the tracker lives on one host's disk. Before this directory
existed there was no automated backup at all — only a `pg_dump` command in the
docs that somebody had to remember to run. For a tool teams plan their work
in, that was the single highest-consequence gap in the project.

Two things are backed up, because either one alone restores a broken product:

- **the database** — tasks, comments, permissions, activity;
- **`media/`** — uploaded attachments. They are files on disk, not rows. A
  database-only restore gives you a tracker where every attachment link 404s.

---

## Running backups

The `backup` service in `docker-compose.prod.yml` starts with the stack and
needs nothing else:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose logs -f backup          # every run, with timings
```

Defaults (override in the repo-root `.env`):

| Variable | Default | Meaning |
|---|---|---|
| `BACKUP_AT` | `02:30` | Daily run time, **UTC**, `HH:MM` |
| `BACKUP_RETENTION_DAYS` | `14` | Sets older than this are pruned — only ever *after* a new verified backup |
| `BACKUP_ON_START` | `1` | Take one immediately if no backup exists yet |
| `BACKUP_MAX_FAILURES` | `3` | Exit (and so restart-flap, visibly) after this many consecutive failures |

Take one right now:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  run --rm backup bash /scripts/backup.sh
```

### What a backup set looks like

```
/backups/
  LATEST                       # the newest set's name, one line
  20260810T023000Z/
    db.dump                    # pg_dump --format=custom (compressed)
    db.contents.txt            # pg_restore --list output, i.e. proof it parses
    media.tar.gz               # uploaded attachments
    manifest.txt               # when, which database, which pg_dump
    SHA256SUMS                 # checksums for every file above
```

Sets are published atomically: `backup.sh` writes into `.in-progress-<stamp>/`
and renames on success, so a set that exists is a set that finished.

### Prefer host cron?

Same script, no long-running container. Drop the `backup` service and add:

```cron
30 2 * * * cd /srv/clickup && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps backup bash /scripts/backup.sh >> /var/log/clickup-backup.log 2>&1
```

`backup.sh` exits non-zero on any failure, so cron's `MAILTO` (or whatever
scrapes that log) is your alerting.

### Off-host copies

The `backups` volume is on the **same disk** as `pgdata`. It protects against
`DROP TABLE`, a bad migration and a bad deploy — **not** against losing the
host. Ship the directory somewhere else too; anything that can read a
directory works:

```bash
# example: nightly sync of the volume to object storage
docker run --rm -v clickup_backups:/backups:ro -v ~/.aws:/root/.aws:ro \
  amazon/aws-cli s3 sync /backups s3://your-bucket/clickup/ --delete
```

---

## Restoring — the runbook

Follow it in order. Do not skip step 2.

**1. Find a set and check it is intact.**

```bash
C="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
$C run --rm backup bash /scripts/restore.sh --list
$C run --rm backup bash /scripts/restore.sh --check 20260810T023000Z
```

`--check` verifies the checksums, that `pg_restore` can read the dump, and
that the media tarball opens. It changes nothing. If it reports a mismatch,
**stop and try an older set** — restoring from a damaged dump loses the
current database too.

**2. Stop everything that writes.**

```bash
$C stop backend frontend backup
```

`pg_restore --clean` drops tables. An app still holding connections gets 500s,
and a background write during the restore lands in a half-restored schema.

**3. Restore.**

```bash
$C run --rm -e I_UNDERSTAND_THIS_DESTROYS_DATA=yes \
  backup bash /scripts/restore.sh latest
```

The script dumps the *current* database to
`/backups/pre-restore-<stamp>.dump` before touching anything. If you picked
the wrong set, that file is the way back.

Media is mounted read-only in the backup service, so the script will tell you
to extract it separately. Do that with:

```bash
$C run --rm -v clickup_media:/restore-media \
  backup tar xzf /backups/20260810T023000Z/media.tar.gz -C /restore-media
```

**4. Bring the stack back.**

```bash
$C up -d
```

The one-shot `migrate` service runs before the app containers and brings the
restored schema up to the current code. That is expected: a backup from an
older release restores an older schema.

**5. Verify.**

```bash
curl -fsS -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/api/v1/health/
$C logs --tail=50 backend
```

Then open the app and spot-check recent tasks, a comment thread, and one
attachment download.

**6. Clean up.** Delete `pre-restore-<stamp>.dump` once you are confident.

### Practise it

A restore procedure nobody has run is a hypothesis. Once a quarter, restore
the latest set into a scratch database and check it comes up:

```bash
$C run --rm -e PGDATABASE=clickup_restore_drill \
  -e I_UNDERSTAND_THIS_DESTROYS_DATA=yes \
  backup bash -c 'createdb clickup_restore_drill 2>/dev/null; /scripts/restore.sh latest'
```

---

## Re-measuring the CI ratchets

Two gates in CI are pinned to measured numbers rather than aspirations. Both
may only move **up**.

**Coverage floor** — `backend/.coveragerc`, `fail_under` (83 as of
2026-08-10, measured 83.04%):

```bash
cd backend
../.venv/Scripts/python.exe -m pytest --cov --cov-report=term
# read TOTAL, floor it, raise fail_under to match
```

**OpenAPI error budget** — `.github/workflows/ci.yml`,
`SCHEMA_UNIQUE_ERROR_BUDGET` (54 as of 2026-08-10):

```bash
cd backend
../.venv/Scripts/python.exe manage.py spectacular --file /dev/null 2>&1 | tail -3
# "Errors: N (M unique)" -> M is the budget
```

Lowering either number is the same thing as deleting the gate. If a change
legitimately reduces coverage, say so in the PR body.
