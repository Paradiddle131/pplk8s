#!/usr/bin/env bash
# The governed tables' dbt models (semantic/PLAN.md SL-24, #314), generated from MetricFlow's compiled SQL on the
# compile-only `bigquery` target, offline: in a copy of dbt/ (MetricFlow reads <project>/target), `dbt parse` on
# that target, then dbt/scripts/build_governed.py writes dbt/models/governed/ there.
#   governed-models.sh --write   copies the generated folder into the repo (`make governed-models`);
#   governed-models.sh           fails when the repo's folder differs from what the generator writes now
#                                (`make bigquery-check` runs it), so a semantic-layer change that moves a
#                                governed table cannot land without its regenerated model.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/dbt-deps.sh
source "$REPO/tests/e2e/lib/dbt-deps.sh"
OUT=${TMPDIR:-/tmp}/pplk8s-governed-models
PROJECT="$OUT/dbt"
fail() { echo "FAIL: $*" >&2; exit 1; }

export DBT_TARGET=bigquery DBT_PROFILES_DIR="$PROJECT"
run_() { (cd "$PROJECT" && uv run --quiet --no-project --with-requirements requirements-postgres.txt --with dbt-bigquery==1.12.1 "$@"); }

rm -rf "$OUT" && mkdir -p "$PROJECT"
(cd "$REPO/dbt" && tar --exclude=./target --exclude=./logs --exclude=./dbt_packages -cf - .) | tar -xf - -C "$PROJECT"
dbt_deps "$PROJECT"
run_ dbt parse --quiet || fail "dbt parse on the bigquery target"
rm -rf "$PROJECT/models/governed"
run_ python scripts/build_governed.py target models/governed || fail "build_governed.py on the bigquery target"

if [ "${1:-}" = --write ]; then
  rm -rf "$REPO/dbt/models/governed"
  cp -r "$PROJECT/models/governed" "$REPO/dbt/models/governed"
  echo "ok: dbt/models/governed/ regenerated ($(find "$REPO/dbt/models/governed" -name '*.sql' | wc -l) models)"
elif diff -ru "$REPO/dbt/models/governed" "$PROJECT/models/governed" >"$OUT/drift.diff"; then
  echo "ok: dbt/models/governed/ is what build_governed.py generates from the semantic layer now"
else
  head -40 "$OUT/drift.diff" >&2
  fail "dbt/models/governed/ drifted from the semantic layer: run make governed-models"
fi
