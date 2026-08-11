#!/usr/bin/env bash
# PostToolUse hook: `tsc --noEmit` after a frontend/src/**/*.{ts,tsx} edit.
#
# Unlike the backend ruff hook, TypeScript's type checker cannot check a
# single file in isolation with correct results (it needs the whole program
# graph for cross-file type inference), so this intentionally runs the full
# frontend project check rather than a single-file check.
#
# Two mitigations keep that from being slow on every keystroke-sized edit:
#   1. .claude/settings.json only fires this hook when the edited path
#      matches "frontend/src/**/*.{ts,tsx}" (the hook's "if" matcher) — a
#      Python-only or CSS-only edit never triggers it.
#   2. `--incremental` + a persisted .tsbuildinfo file (kept outside the repo,
#      under the OS temp dir, so it is never committed and never collides
#      with `frontend`'s own build output) lets tsc skip re-checking files
#      whose dependency graph did not change. Measured on this repo
#      (2026-08-11): ~3s cold, ~2-3s warm — small but real, and the datapoint
#      that justified NOT doing anything fancier (e.g. a file-watcher
#      daemon) here.
#   3. The hook itself is declared `async` + `asyncRewake` in settings.json,
#      so it never blocks the edit that triggered it — Claude is only woken
#      up if tsc actually finds an error (exit 2).
set -uo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

cd "$project_dir/frontend" 2>/dev/null || exit 0

buildinfo_dir="${TMPDIR:-${TEMP:-/tmp}}"
buildinfo_file="$buildinfo_dir/uzwork-tsc-buildinfo.json"

output="$(npx tsc --noEmit --incremental --tsBuildInfoFile "$buildinfo_file" 2>&1)"
status=$?

if [ "$status" -ne 0 ]; then
  echo "tsc --noEmit found type errors after this edit:" >&2
  echo "$output" >&2
  exit 2
fi

exit 0
