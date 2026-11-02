#!/usr/bin/env bash
# `make bigquery-live-load` (#207): the lab project holds what the eval's dbt_dev holds, so the data-agent arm
# (`make agent-eval ARM=data_agent`) asks a data agent over the same rows the expected numbers come from.
# Builds dbt_dev as the eval does (tests/e2e/agent-fixture.sh: dbt/dev/fixture.sql and fixture_weeks.sql, every
# semantic domain), copies its landed sources into the lab project (tests/e2e/lib/fixture_to_bigquery.py, which
# empties the dbt datasets first, never `ops`), then runs `dbt build` of the same domains on the `gcp` target,
# every job capped at the free path's per-query bytes. Live: GCP_PROJECT, the cost check before and after; the
# credential as tests/e2e/bigquery-run-check.sh picks it. Expects `make services-up`.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
fail() { echo "FAIL: $*" >&2; exit 1; }
: "${GCP_PROJECT:?GCP_PROJECT is unset: the load goes to the lab project (platform/gcp/README.md)}"
DB=${DB:-dbt_dev}
OUT=${TMPDIR:-/tmp}/pplk8s-bigquery-live-load
TAGS=(tag:sales tag:returns tag:finance tag:marketing tag:customer_actions tag:partner_outreach tag:recruitment tag:call_transcripts)

if [ -z "${GCP_ACCESS_TOKEN:-}" ]; then
  if [ -n "${CLOUDSDK_AUTH_ACCESS_TOKEN:-}" ]; then
    export GCP_ACCESS_TOKEN=$CLOUDSDK_AUTH_ACCESS_TOKEN
  elif command -v gcloud >/dev/null; then
    account=${GCP_ACCOUNT:-$(gcloud config get-value account 2>/dev/null)}
    if [ -n "$account" ]; then
      GCP_ACCESS_TOKEN=$(gcloud auth print-access-token --account="$account") ||
        fail "gcloud auth print-access-token --account=$account"
      export GCP_ACCESS_TOKEN
    fi
  fi
fi

"$REPO/platform/gcp/cost-check.sh" || [ "${GCP_COST_UNPROVEN_OK:-}" = 1 ] ||
  fail "the cost check did not prove \$0.00 (GCP_COST_UNPROVEN_OK=1 proceeds on the owner's say-so)"
trap '"$REPO/platform/gcp/cost-check.sh" || true' EXIT

DB="$DB" "$REPO/tests/e2e/agent-fixture.sh"
mkdir -p "$OUT"
cd "$REPO/dbt"
run_() { uv run --quiet --no-project --with-requirements requirements-postgres.txt --with dbt-bigquery==1.12.1 "$@"; }
BQ_LIB="$REPO/tests/e2e/lib" run_ --with 'psycopg[binary]==3.3.6' python -I "$REPO/tests/e2e/lib/fixture_to_bigquery.py" \
  "host=localhost port=5433 user=warehouse password=warehouse dbname=$DB" >"$OUT/fixture.log" 2>&1 ||
  { tail -20 "$OUT/fixture.log" >&2; fail "copying $DB's sources into $GCP_PROJECT"; }
echo "ok: $DB's sources copied into $GCP_PROJECT"
DBT_TARGET=gcp DBT_PROFILES_DIR="$REPO/dbt" run_ dbt build --select "${TAGS[@]}" --exclude tag:tlc >"$OUT/build.log" 2>&1 ||
  { grep -E "ERROR|Error" "$OUT/build.log" | tail -20 >&2; fail "dbt build on $GCP_PROJECT"; }
echo "ok: the semantic path built on $GCP_PROJECT: $(grep -o "PASS=[0-9]* WARN=[0-9]* ERROR=[0-9]* SKIP=[0-9]*" "$OUT/build.log" | tail -1)"
