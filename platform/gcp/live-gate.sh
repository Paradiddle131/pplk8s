#!/usr/bin/env bash
# The gate before and after a live step (platform/gcp/README.md, the $0.00 rule; #313): the usage check must pass,
# minutes behind; the billing export's cost check, hours behind, stops the step on a cost (exit 1) and is only
# reported while it cannot prove $0.00 yet (exit 3). Exit 0: go on; anything else: stop.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
"$HERE/cost-check.sh"
cost=$?
if [ "$cost" -eq 1 ]; then
  echo "live-gate: STOP: the billing export shows a cost" >&2
  exit 1
fi
[ "$cost" -eq 0 ] || echo "live-gate: the billing export cannot prove \$0.00 yet (exit $cost); the usage check gates" >&2
uv run --no-project --quiet --with pyyaml==6.0.2 python "$HERE/usage_check.py" --share "${USAGE_SHARE:-50}" ||
  { echo "live-gate: STOP: the usage check did not pass" >&2; exit 1; }
