#!/usr/bin/env bash
#
# Restore a backup produced by backup.sh.
#
# Written to be followed under pressure: it refuses to guess, it verifies
# before it destroys anything, it keeps a way back, and it says what to do
# next. The full runbook is in scripts/README.md.
#
#   # what is available
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
#     run --rm backup bash /scripts/restore.sh --list
#
#   # dry run: verify a set without touching the database
#   docker compose ... run --rm backup bash /scripts/restore.sh --check 20260810T023000Z
#
#   # the real thing (stop the app containers first)
#   docker compose ... run --rm \
#     -e I_UNDERSTAND_THIS_DESTROYS_DATA=yes \
#     backup bash /scripts/restore.sh latest
#
# The confirmation variable is deliberate: this drops every table in the
# target database and there is no undo beyond the safety dump it takes.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
MEDIA_DIR="${MEDIA_DIR:-/media}"

log()  { printf '[restore %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { printf '[restore %s] ERROR: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
usage: restore.sh [--list | --check <set> | <set>]

  --list           show every backup set on disk, oldest first
  --check <set>    verify checksums and readability, change nothing
  <set>            restore that set; use `latest` for the most recent

<set> is a directory name under $BACKUP_DIR, e.g. 20260810T023000Z.
Restoring requires I_UNDERSTAND_THIS_DESTROYS_DATA=yes in the environment.
USAGE
}

list_sets() {
  find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -printf '%f\n' \
    2>/dev/null | sort
}

resolve_set() {
  local want="$1"
  if [ "$want" = "latest" ]; then
    [ -f "${BACKUP_DIR}/LATEST" ] || fail "no ${BACKUP_DIR}/LATEST — pass an explicit set (--list)"
    want="$(cat "${BACKUP_DIR}/LATEST")"
  fi
  [ -d "${BACKUP_DIR}/${want}" ] || fail "no such backup set: ${want} (try --list)"
  printf '%s\n' "$want"
}

verify_set() {
  local dir="$1"
  log "verifying checksums ..."
  ( cd "$dir" && sha256sum --check --quiet SHA256SUMS ) \
    || fail "checksum mismatch — this backup is damaged, try an older set"
  log "verifying the dump is readable ..."
  pg_restore --list "${dir}/db.dump" > /dev/null \
    || fail "pg_restore cannot read ${dir}/db.dump"
  if [ -f "${dir}/media.tar.gz" ]; then
    log "verifying the media archive ..."
    tar --list --file="${dir}/media.tar.gz" > /dev/null \
      || fail "the media archive is damaged"
  fi
  log "set verified: $(basename "$dir")"
  if [ -f "${dir}/manifest.txt" ]; then
    sed 's/^/    /' "${dir}/manifest.txt"
  fi
}

case "${1:---list}" in
  -h|--help)
    usage
    exit 0
    ;;
  --list)
    sets="$(list_sets)"
    if [ -z "$sets" ]; then
      log "no backups in ${BACKUP_DIR}"
      exit 1
    fi
    printf '%s\n' "$sets"
    if [ -f "${BACKUP_DIR}/LATEST" ]; then
      log "latest = $(cat "${BACKUP_DIR}/LATEST")"
    fi
    exit 0
    ;;
  --check)
    [ $# -ge 2 ] || fail "--check needs a set name"
    verify_set "${BACKUP_DIR}/$(resolve_set "$2")"
    exit 0
    ;;
esac

SET="$(resolve_set "$1")"
DIR="${BACKUP_DIR}/${SET}"

if [ "${I_UNDERSTAND_THIS_DESTROYS_DATA:-}" != "yes" ]; then
  fail "refusing to restore without I_UNDERSTAND_THIS_DESTROYS_DATA=yes.
   This drops every table in '${PGDATABASE:-?}' and replaces it with ${SET}.
   Run 'restore.sh --check ${SET}' if you only wanted to validate the backup."
fi

verify_set "$DIR"

# A dump of the CURRENT state before overwriting it. Restores happen in a
# hurry and sometimes against the wrong database; this is the way back.
SAFETY="${BACKUP_DIR}/pre-restore-$(date -u +%Y%m%dT%H%M%SZ).dump"
log "dumping the current database to ${SAFETY} first ..."
if pg_dump --format=custom --compress=6 --no-owner --no-privileges --file="$SAFETY"; then
  log "safety dump written"
else
  log "WARNING: the safety dump failed (empty or unreachable database?)"
  log "         continuing, but there is no way back from here"
fi

log "restoring ${SET} into ${PGDATABASE} ..."
# --clean --if-exists : drop existing objects first, tolerating ones already gone
# --no-owner/--no-privileges : the roles in the dump need not exist here
# --exit-on-error : stop at the first problem instead of reporting 400 of them
pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error \
           --dbname="${PGDATABASE}" "${DIR}/db.dump" \
  || fail "pg_restore failed — the database is in a partial state. Restore ${SAFETY} or an older set."
log "database restored"

if [ -f "${DIR}/media.tar.gz" ]; then
  if [ -w "$MEDIA_DIR" ]; then
    log "restoring media into ${MEDIA_DIR} ..."
    tar --extract --gzip --file="${DIR}/media.tar.gz" -C "$MEDIA_DIR"
    log "media restored"
  else
    log "WARNING: ${MEDIA_DIR} is not writable — the backup service mounts it"
    log "         read-only on purpose. Extract it by hand into the media volume:"
    log "         tar xzf ${DIR}/media.tar.gz -C <media mount>"
  fi
fi

cat <<NEXT

Restore finished. Next:

  1. Bring the stack back up:
       docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
     The one-shot 'migrate' service runs first and brings the restored schema
     up to the current code. That is expected and safe.
  2. Check the API answers:
       curl -fsS -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/api/v1/health/
  3. Spot-check in the UI that recent tasks, comments and attachments are there.
  4. Keep ${SAFETY} until you are sure, then delete it.

NEXT
