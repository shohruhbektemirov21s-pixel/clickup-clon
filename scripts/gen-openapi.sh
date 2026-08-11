#!/usr/bin/env bash
# Regenerate api/openapi.json from the current Django/DRF codebase.
#
# This is the ONE canonical command for the committed schema artifact — the
# CI drift-check (`.github/workflows/ci.yml`, backend job, "OpenAPI drift-check"
# step) runs the exact same command and fails the build if the committed
# artifact differs from what it produces. Whenever this message appears in
# CI:
#
#     api/openapi.json is stale — regenerate it: bash scripts/gen-openapi.sh
#
# ...running this script and committing the result is the fix.
#
# Deliberately separate from `.github/workflows/ci.yml`'s pre-existing
# "OpenAPI sxemasi (ratchet)" step: that step tracks the COUNT of unresolved
# drf-spectacular warnings against SCHEMA_UNIQUE_ERROR_BUDGET (a backlog
# ratchet, YAML output, stdout-only artifact upload) and must not be touched.
# This script produces a different, committed JSON artifact and checks
# CONTENT drift, not a warning count. The two run side by side.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# CI exports PYTHON=python (actions/setup-python puts the right interpreter
# directly on PATH there). Locally, prefer this repo's own venv so nobody
# needs to activate anything first — same convention as every command in
# CLAUDE.md ("Always use the venv Python explicitly").
if [ -z "${PYTHON:-}" ]; then
  if [ -x "$repo_root/.venv/Scripts/python.exe" ]; then
    PYTHON="$repo_root/.venv/Scripts/python.exe"
  elif [ -x "$repo_root/.venv/bin/python" ]; then
    PYTHON="$repo_root/.venv/bin/python"
  else
    PYTHON="python"
  fi
fi

echo "gen-openapi: using interpreter: $PYTHON"

mkdir -p "$repo_root/api"

(
  cd "$repo_root/backend"
  "$PYTHON" manage.py spectacular --format openapi-json --file "$repo_root/api/openapi.json"
)

echo "gen-openapi: wrote api/openapi.json"
