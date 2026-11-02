#!/usr/bin/env bash
# GCP image check (#206, semantic/PLAN.md SL-19): the dbt image's GCP build runs the semantic path, not only
# parses it. It builds the image with WAREHOUSE=bigquery (the BigQuery adapter alone, from a lock that leaves
# out Vertex AI, pandas and pyarrow, dbt/requirements-bigquery.exclude), then, on a fresh BigQuery emulator
# holding the dev fixture's sources, runs the image's own `dbt build` of the platform part with its tests (the
# hops include every metric against its gold table) and one MetricFlow query, as Cloud Run would run it.
# The emulator gets dbt/dev/fixture.sql's sources alone (31 orders), whatever ran before: the script loads that
# file into a Postgres database of its own, gcp_image_check, recreated each run, and copies that one, never
# dbt_dev, which agent-fixture.sh extends by six weeks (fixture_weeks.sql) that time out the emulator's hops.
# Expects `make services-up` (the fixture loads through the Postgres warehouse).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE=${GCP_DBT_IMAGE:-pplk8s-dbt-gcp:check}
OUT=${TMPDIR:-/tmp}/pplk8s-gcp-image-check
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml" --profile bigquery)
fail() { echo "FAIL: $*" >&2; exit 1; }
DB=gcp_image_check
psql_db() { "${COMPOSE[@]}" exec -T warehouse psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"; }
rm -rf "$OUT" && mkdir -p "$OUT"

build=(docker build --build-arg WAREHOUSE=bigquery -t "$IMAGE")
# Behind a TLS-intercepting proxy (cloud sessions), the Makefile's BUILD_CA path: the proxy's CA as a secret.
if [ -n "${BUILD_CA:-}" ] && [ -f "$BUILD_CA" ]; then
  build+=(--network host --build-arg HTTPS_PROXY --build-arg HTTP_PROXY --build-arg NO_PROXY --secret "id=build_ca,src=$BUILD_CA")
fi
"${build[@]}" "$REPO/dbt" >"$OUT/build.log" 2>&1 || { tail -30 "$OUT/build.log" >&2; fail "docker build of the GCP dbt image"; }
echo "ok: $IMAGE built (WAREHOUSE=bigquery): its in-image checks found no Postgres package and no TLC path, and it parses"

{ "${COMPOSE[@]}" exec -T warehouse dropdb -U warehouse --if-exists "$DB" &&
  "${COMPOSE[@]}" exec -T warehouse createdb -U warehouse "$DB"; } || fail "recreating the Postgres database $DB"
psql_db <"$REPO/dbt/dev/fixture.sql" >"$OUT/fixture-sql.log" 2>&1 || { tail -20 "$OUT/fixture-sql.log" >&2; fail "loading dbt/dev/fixture.sql into $DB"; }
orders=$(psql_db -c "select count(*) from ds_source.synthetic_orders")
echo "ok: $DB recreated with dbt/dev/fixture.sql alone ($orders orders)"
"${COMPOSE[@]}" up -d --force-recreate --wait bigquery bigquery-api >/dev/null 2>&1 ||
  { "${COMPOSE[@]}" logs --tail 20 bigquery bigquery-api >&2; fail "the emulator did not come up"; }
(cd "$REPO/dbt" && BQ_API_ENDPOINT=http://localhost:9050 uv run --quiet --no-project \
  --with-requirements requirements-postgres.txt --with dbt-bigquery==1.12.1 --with 'psycopg[binary]==3.3.6' \
  python -I "$REPO/tests/e2e/lib/fixture_to_bigquery.py" "host=localhost port=5433 user=warehouse password=warehouse dbname=$DB") \
  >"$OUT/fixture.log" || { cat "$OUT/fixture.log" >&2; fail "copying the fixture into the emulator"; }
echo "ok: a fresh emulator holds the fixture's sources"

run_image() { docker run --rm --network host -e DBT_TARGET=bigquery_emulator -e BQ_API_ENDPOINT=http://localhost:9050 --entrypoint sh "$IMAGE" -c "$1"; }
run_image 'dbt build --select tag:sales tag:returns tag:finance tag:marketing tag:semantic tag:migration' >"$OUT/dbt.log" 2>&1 ||
  { grep -E "ERROR|Error" "$OUT/dbt.log" | tail -20 >&2; fail "the image's dbt build on the emulator"; }
hops=$(grep -c " PASS hop_" "$OUT/dbt.log" || true)
[ "$hops" -eq 31 ] || fail "expected the platform's 31 hops to pass in the image, got $hops"
echo "ok: the image's dbt build: $(grep -o "PASS=[0-9]* WARN=[0-9]* ERROR=[0-9]* SKIP=[0-9]*" "$OUT/dbt.log" | tail -1), the 31 hops of the platform part pass"
# The image ships no target/ (its build discards the parse), so the step parses first, as a job would.
run_image 'dbt parse --quiet >&2 && mf query --metrics revenue_eur,net_revenue_eur --group-by metric_time__day --order metric_time__day --csv /tmp/q.csv >&2 && cat /tmp/q.csv' \
  >"$OUT/query.csv" 2>"$OUT/query.log" || { tail -20 "$OUT/query.log" >&2; fail "the image's mf query on the emulator"; }
[ "$(tail -n +2 "$OUT/query.csv" | wc -l)" -ge 2 ] || fail "the image's mf query returned $(cat "$OUT/query.csv")"
echo "ok: the image's MetricFlow answers on the emulator ($(tail -n +2 "$OUT/query.csv" | wc -l) days)"
echo "PASS: GCP image check"
