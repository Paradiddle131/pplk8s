#!/usr/bin/env bash
# Fails when a tracked file names this checkout's GitHub owner literally: code, config and docs take
# <owner>/<repo> from the origin remote (Makefile GITHUB_REPO) or link the tracker relatively
# (../../issues/N), so a fork builds, syncs and links against itself. History keeps its facts:
# LEDGER.md and ledger.d/ are not checked.
set -euo pipefail
cd "$(dirname "$0")/.."
owner=$(git remote get-url origin 2>/dev/null | sed -E 's#^(git@|[a-z]+://)([^@/]*@)?github\.com[:/]##; s#/.*##')
[ -n "$owner" ] || { echo "check-portable: no GitHub origin remote; nothing to check"; exit 0; }
mapfile -t files < <(git ls-files | grep -vE '^LEDGER\.md$|^ledger\.d/|\.lock$')
if hits=$(grep -nIiwF -- "$owner" "${files[@]}"); then
  printf '%s\n' "$hits"
  echo "check-portable: name the owner through the origin remote (Makefile GITHUB_REPO) or a relative link" >&2
  exit 1
fi
echo "check-portable: ${#files[@]} files, no literal owner"
