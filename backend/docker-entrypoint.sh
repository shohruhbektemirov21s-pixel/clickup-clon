#!/bin/sh
#
# Container entrypoint for the Django/Daphne backend.
#
#   1. wait until the database accepts connections
#   2. optionally apply migrations (RUN_MIGRATIONS=1, default OFF — see below)
#   3. optionally re-run collectstatic (RUN_COLLECTSTATIC=1, default off —
#      the image already collected at build time; dev needs it again because
#      the bind mount + named volume replace the built staticfiles dir)
#   4. optionally seed demo data   (RUN_SEED_DEMO=1, default off)
#   5. exec the CMD (daphne ...)
#
# RUN_MIGRATIONS defaults to 0, not 1. Migrating from the app container is
# safe with exactly one replica and unsafe the moment there are two: Django
# takes a lock per migration, not one for the whole run, so two containers
# starting together can interleave and half-apply a release. Migrations
# therefore belong to a one-shot job:
#
#   docker-compose.yml      -> RUN_MIGRATIONS=1 (dev, single container)
#   docker-compose.prod.yml -> a `migrate` service that runs once and exits;
#                              the app containers run with RUN_MIGRATIONS=0
#
# When RUN_MIGRATIONS=1 anyway, step 2 additionally takes a PostgreSQL
# advisory lock so a second container waits instead of racing.
set -e

: "${RUN_MIGRATIONS:=0}"
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
# Serialised with pg_advisory_lock() on a connection that is NOT the one
# migrate uses, so migrate opening/closing its own connection cannot drop the
# lock. The lock is session-scoped: closing the holder releases it, and a
# container that is killed mid-migration releases it too (the backend dies
# with the TCP session) rather than wedging every future deploy.
#
# Anything unexpected about the lock falls through to a plain migrate — the
# lock is a safety net, never a new way for a deploy to fail.
if [ "$RUN_MIGRATIONS" = "1" ]; then
    log "applying migrations ..."
    python - <<'PY'
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.core.management import call_command
from django.db import connections

# Arbitrary but stable; any other process wanting this lock must use the same
# number. 64-bit signed, so it is safe as a single-argument advisory lock key.
LOCK_ID = 5150730291847
connection = connections["default"]

holder = None
if connection.vendor == "postgresql":
    try:
        import psycopg2

        params = {
            key: value
            for key, value in connection.get_connection_params().items()
            if key not in {"cursor_factory", "context"}
        }
        holder = psycopg2.connect(**params)
        holder.autocommit = True
        with holder.cursor() as cursor:
            print("[entrypoint] waiting for the migration lock ...", flush=True)
            cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        print("[entrypoint] migration lock held", flush=True)
    except Exception as exc:  # noqa: BLE001 - the lock is best effort
        print(f"[entrypoint] advisory lock unavailable ({exc}); migrating anyway", file=sys.stderr)
        if holder is not None:
            holder.close()
            holder = None

try:
    call_command("migrate", "--noinput")
finally:
    # Closing the session releases the lock; no explicit unlock needed.
    if holder is not None:
        holder.close()
PY
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
