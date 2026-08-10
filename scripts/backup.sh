#!/usr/bin/env bash
#
# One backup: PostgreSQL dump + the uploaded-media tree + a checksum manifest.
#
# Run it from the compose `backup` service (see docker-compose.prod.yml) or by
# hand from anywhere that can reach the database:
#
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
#     run --rm backup bash /scripts/backup.sh
#
# Environment (all have defaults except the PG* connection settings, which the
# compose service supplies from the repo-root .env):
#
#   PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD   libpq connection settings
#   BACKUP_DIR              default /backups     where artefacts land
#   MEDIA_DIR               default /media       uploaded attachments
#   BACKUP_RETENTION_DAYS   default 14           prune older sets after success
#
# Exit code is 0 only when a *verified* backup exists on disk. Anything else
# is non-zero, so cron / the loop / your alerting can tell the difference
# between "backed up" and "wrote a file".
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
MEDIA_DIR="${MEDIA_DIR:-/media}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="${BACKUP_DIR}/.in-progress-${STAMP}"
FINAL="${BACKUP_DIR}/${STAMP}"

log()  { printf '[backup %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { printf '[backup %s] ERROR: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; exit 1; }

cleanup_failed() {
  # Never leave a half-written set where the restore script could pick it up.
  [ -d "$WORK" ] && rm -rf "$WORK"
}
trap cleanup_failed EXIT

command -v pg_dump >/dev/null || fail "pg_dump not on PATH"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"

mkdir -p "$WORK"

# --- 1. database ------------------------------------------------------------
# -Fc (custom format), not plain SQL: compressed, and pg_restore can then
# restore a single table or list the contents without replaying everything.
log "dumping ${PGDATABASE} from ${PGHOST:-local}:${PGPORT:-5432} ..."
pg_dump --format=custom --compress=6 --no-owner --no-privileges \
        --file="${WORK}/db.dump" \
  || fail "pg_dump failed"

# --- 2. verify the dump NOW, not at 3 a.m. during an incident ---------------
# Reading the archive's table of contents catches truncation and corruption
# here, where it is a failed job, instead of six months later where it is a
# failed restore.
log "verifying the dump ..."
pg_restore --list "${WORK}/db.dump" > "${WORK}/db.contents.txt" \
  || fail "the dump is unreadable — pg_restore --list refused it"
entries="$(grep -c . < "${WORK}/db.contents.txt" || true)"
[ "${entries:-0}" -gt 0 ] || fail "the dump contains no objects"
log "dump ok — ${entries} archive entries"

# --- 3. uploaded media ------------------------------------------------------
# Attachments live on disk, not in PostgreSQL. A database-only backup restores
# a tracker in which every attachment link 404s.
if [ -d "$MEDIA_DIR" ]; then
  log "archiving media from ${MEDIA_DIR} ..."
  tar --create --gzip --file="${WORK}/media.tar.gz" -C "$MEDIA_DIR" . \
    || fail "media archive failed"
  tar --test --file="${WORK}/media.tar.gz" >/dev/null 2>&1 \
    || tar --list --file="${WORK}/media.tar.gz" >/dev/null \
    || fail "media archive is unreadable"
else
  log "no media directory at ${MEDIA_DIR} — skipping (db-only backup)"
fi

# --- 4. manifest ------------------------------------------------------------
{
  echo "created_utc=${STAMP}"
  echo "database=${PGDATABASE}"
  echo "host=${PGHOST:-local}"
  echo "pg_dump_version=$(pg_dump --version | tr -d '\n')"
  echo "archive_entries=${entries}"
} > "${WORK}/manifest.txt"

( cd "$WORK" && sha256sum ./* > SHA256SUMS ) || fail "checksum generation failed"

# --- 5. publish atomically --------------------------------------------------
mv "$WORK" "$FINAL"
trap - EXIT
printf '%s\n' "$STAMP" > "${BACKUP_DIR}/LATEST"
log "backup complete: ${FINAL} ($(du -sh "$FINAL" | cut -f1))"

# --- 6. prune (only ever AFTER a verified new backup) -----------------------
# Retention runs last on purpose: a failed backup must never be the reason an
# old good one disappeared.
if [ "$RETENTION_DAYS" -gt 0 ]; then
  pruned=0
  while IFS= read -r old; do
    [ -z "$old" ] && continue
    rm -rf "$old"
    pruned=$((pruned + 1))
  done < <(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d \
             -name '20*' -mtime "+${RETENTION_DAYS}" 2>/dev/null || true)
  log "pruned ${pruned} set(s) older than ${RETENTION_DAYS} days"
fi

remaining="$(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' | wc -l)"
log "${remaining} backup set(s) on disk"
