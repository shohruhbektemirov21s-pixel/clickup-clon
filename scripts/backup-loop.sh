#!/usr/bin/env bash
#
# Scheduler for backup.sh — the entrypoint of the compose `backup` service.
#
# A loop rather than cron: nothing extra to install or supervise inside the
# container, no crontab that silently drifts from this repo, and
# `docker compose logs backup` is the complete history of every run.
#
#   BACKUP_AT               HH:MM in UTC, default 02:30
#   BACKUP_ON_START         1 = also back up now if none exists yet (default 1)
#   BACKUP_MAX_FAILURES     exit non-zero after this many in a row (default 3)
#
# On repeated failure the process exits instead of looping quietly: with
# `restart: unless-stopped` the container then flaps, which is visible in
# `docker ps` and to any orchestrator's restart alerting. A backup job that
# fails silently forever is worse than no backup job, because it also removes
# the worry that would have made someone check.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_AT="${BACKUP_AT:-02:30}"
BACKUP_ON_START="${BACKUP_ON_START:-1}"
MAX_FAILURES="${BACKUP_MAX_FAILURES:-3}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"

log() { printf '[backup-loop %s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

case "$BACKUP_AT" in
  [0-2][0-9]:[0-5][0-9]) ;;
  *) log "ERROR: BACKUP_AT must be HH:MM (UTC), got '${BACKUP_AT}'"; exit 2 ;;
esac

failures=0

run_backup() {
  if bash "${SCRIPT_DIR}/backup.sh"; then
    failures=0
    return 0
  fi
  failures=$((failures + 1))
  log "ERROR: backup failed (${failures}/${MAX_FAILURES} consecutive)"
  if [ "$failures" -ge "$MAX_FAILURES" ]; then
    log "ERROR: giving up so the container restart is visible — FIX THE BACKUPS"
    exit 1
  fi
  return 1
}

mkdir -p "$BACKUP_DIR"

if [ "$BACKUP_ON_START" = "1" ] && [ ! -f "${BACKUP_DIR}/LATEST" ]; then
  log "no backup on disk yet — taking one now"
  run_backup || true
fi

log "scheduled daily at ${BACKUP_AT} UTC; retention ${BACKUP_RETENTION_DAYS:-14} day(s)"

while true; do
  now_epoch="$(date -u +%s)"
  if ! today_target="$(date -u -d "today ${BACKUP_AT}" +%s 2>/dev/null)"; then
    log "ERROR: this image's date(1) cannot parse 'today ${BACKUP_AT}'"
    exit 2
  fi
  if [ "$today_target" -le "$now_epoch" ]; then
    target="$(date -u -d "tomorrow ${BACKUP_AT}" +%s)"
  else
    target="$today_target"
  fi
  sleep_for=$((target - now_epoch))
  log "next run in $((sleep_for / 3600))h $(((sleep_for % 3600) / 60))m"
  sleep "$sleep_for"
  run_backup || true
done
