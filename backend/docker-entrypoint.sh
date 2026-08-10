#!/bin/sh
#
# Container entrypoint for the Django/Daphne backend.
#
#   1. wait until the database accepts connections
#   2. apply migrations            (RUN_MIGRATIONS=1, default on)
#   3. optionally re-run collectstatic (RUN_COLLECTSTATIC=1, default off —
#      the image already collected at build time; dev needs it again because
#      the bind mount + named volume replace the built staticfiles dir)
#   4. optionally seed demo data   (RUN_SEED_DEMO=1, default off)
#   5. exec the CMD (daphne ...)
#
set -e

: "${RUN_MIGRATIONS:=1}"
: "${RUN_COLLECTSTATIC:=0}"
: "${RUN_SEED_DEMO:=0}"
: "${DB_WAIT_RETRIES:=60}"
: "${DB_WAIT_DELAY:=2}"

log() { echo "[entrypoint] $*"; }

# --- 1. wait for the database -------------------------------------------------
# Uses Django's own connection so it works for both postgres:// and sqlite://
# DATABASE_URL values without needing psql/pg_isready in the image.
db_ready() {
    python - <<'PY' 2>/dev/null
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connections

try:
    connections["default"].ensure_connection()
except Exception as exc:  # noqa: BLE001 - any driver error means "not ready"
    print(exc, file=sys.stderr)
    sys.exit(1)
PY
}

log "waiting for the database ..."
attempt=0
until db_ready; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$DB_WAIT_RETRIES" ]; then
        log "database still unreachable after ${attempt} attempts — giving up"
        db_ready || true
        exit 1
    fi
    sleep "$DB_WAIT_DELAY"
done
log "database is up"

# --- 2. migrations ------------------------------------------------------------
if [ "$RUN_MIGRATIONS" = "1" ]; then
    log "applying migrations ..."
    python manage.py migrate --noinput
fi

# --- 3. static files ----------------------------------------------------------
if [ "$RUN_COLLECTSTATIC" = "1" ]; then
    log "collecting static files ..."
    python manage.py collectstatic --noinput
fi

# --- 4. demo data (opt-in) ----------------------------------------------------
if [ "$RUN_SEED_DEMO" = "1" ]; then
    log "seeding demo data ..."
    python manage.py seed_demo
fi

log "starting: $*"
exec "$@"
