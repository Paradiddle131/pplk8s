#!/usr/bin/env bash
# Fold ledger.d/ fragments into LEDGER.md, oldest first, and delete them.
# Each PR adds its own fragment (ledger.d/YYYY-MM-DD-<n>-<slug>.md), so parallel
# PRs never conflict on LEDGER.md; run `make ledger` on main after merges.
set -euo pipefail
cd "$(dirname "$0")/.."

shopt -s nullglob
fragments=(ledger.d/[0-9]*.md)
if [ ${#fragments[@]} -eq 0 ]; then
  echo "ledger: no fragments to fold"
  exit 0
fi

for f in "${fragments[@]}"; do
  head -1 "$f" | grep -qE '^## [0-9]{4}-[0-9]{2}-[0-9]{2} — ' \
    || { echo "ledger: $f does not start with '## YYYY-MM-DD — '" >&2; exit 1; }
done

for f in "${fragments[@]}"; do
  printf '\n' >>LEDGER.md
  cat "$f" >>LEDGER.md
  git rm -q "$f" 2>/dev/null || rm "$f"
  echo "ledger: folded $f"
done
