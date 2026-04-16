#!/usr/bin/env bash
# SessionStart hook: rebuild the principia database if a workspace exists
# in this project. Invoked by Claude Code at session startup/resume.
#
# Uses the contract wrapper (pp) rather than the raw principia CLI so
# this hook stays stable across core CLI refactors.

set -euo pipefail

root="${PRINCIPIA_ROOT:-principia}"

# Skip silently if no workspace is present — this hook ships with every
# session regardless of whether the user is working on principia.
if [ ! -d "$root/claims" ] && [ ! -d "$root/context" ]; then
  exit 0
fi

# Rebuild via contract wrapper
tmp=$(mktemp)
if PRINCIPIA_ROOT="$root" "${CLAUDE_PLUGIN_ROOT}/scripts/pp" build > "$tmp" 2>&1; then
  tail -5 "$tmp"
  rm -f "$tmp"
else
  status=$?
  tail -10 "$tmp"
  rm -f "$tmp"
  exit $status
fi
