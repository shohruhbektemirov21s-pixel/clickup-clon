#!/usr/bin/env bash
# PostToolUse hook: `ruff check --fix` on the single backend/**/*.py file that
# was just edited.
#
# Scoping is two layers deep on purpose:
#   1. .claude/settings.json only fires this hook when the edited path
#      matches "backend/**/*.py" (the hook's "if" matcher).
#   2. This script re-checks the extension and resolves the path relative to
#      backend/ before invoking ruff, so it never falls back to linting the
#      whole tree — one file in, one file linted, every time.
#
# ruff.toml lives in backend/ and its rule set (see that file's header
# comment) is scoped to what the tree passes today; running from backend/ is
# what makes ruff pick it up.
set -uo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
input="$(cat)"

# Parse tool_input.file_path out of the stdin JSON with the venv's own
# Python rather than depending on jq (CLAUDE.md already requires this venv).
if [ -x "$project_dir/.venv/Scripts/python.exe" ]; then
  py="$project_dir/.venv/Scripts/python.exe"
elif [ -x "$project_dir/.venv/bin/python" ]; then
  py="$project_dir/.venv/bin/python"
else
  py="python"
fi

file_path="$("$py" -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
print(data.get("tool_input", {}).get("file_path", ""))
' <<<"$input")"

[ -z "$file_path" ] && exit 0
case "$file_path" in
  *.py) ;;
  *) exit 0 ;;
esac

cd "$project_dir/backend" 2>/dev/null || exit 0

# Normalize to a backend-relative path (handles both / and \ separators —
# hooks can receive either depending on how the edit tool built the path).
rel="$file_path"
case "$file_path" in
  "$project_dir"/backend/*) rel="${file_path#"$project_dir"/backend/}" ;;
  "$project_dir"\\backend\\*) rel="${file_path#"$project_dir"\\backend\\}" ;;
esac

[ -f "$rel" ] || exit 0

output="$("$py" -m ruff check --fix --quiet "$rel" 2>&1)"
status=$?

if [ "$status" -ne 0 ]; then
  # PostToolUse can't undo the edit (it already happened) — exit 2 just
  # surfaces the remaining, non-auto-fixable findings to Claude via stderr.
  echo "ruff check --fix left findings in \"$rel\" that could not be auto-fixed:" >&2
  echo "$output" >&2
  exit 2
fi

exit 0
