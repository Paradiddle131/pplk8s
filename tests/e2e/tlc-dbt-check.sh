#!/usr/bin/env bash
# tlc dbt check (issue #55, PLAN.md D36): host dbt builds the tlc models month by month against
# dbt/dev/tlc_fixture.sql in the Compose warehouse's dbt_dev database, and asserts that
#   - re-building one month leaves the other month's rows untouched,
#   - bronze = silver + quarantine per month (the dbt test) and the expected rows land in each,
#   - a rebuild is idempotent and a half-loaded file version stays invisible,
#   - a second etag for a month replaces that month,
#   - a month above 10 % quarantined fails the build.
# Expects `make services-up`; never touches the `warehouse` database.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_dev
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_dev() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"
}

export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_PROFILES_DIR="$REPO/dbt"
# The pins come from the image's requirements, so host and image run the same dbt.
dbt_tlc() {
  (cd "$REPO/dbt" && uvx --quiet --with-requirements requirements.txt --from dbt-core \
    dbt build --select tag:tlc --vars "{data_month: $1}") >"/tmp/pplk8s-tlc-dbt-$1.log" 2>&1
}
build() { dbt_tlc "$1" || { tail -30 "/tmp/pplk8s-tlc-dbt-$1.log" >&2; fail "dbt build tag:tlc data_month=$1"; }; }

# "trip_type month count" lines of a silver table, sorted.
counts() { psql_dev -F' ' -c "select trip_type, data_month, count(*) from silver.$1 group by 1, 2 order by 2, 1"; }
expect() { [ "$2" = "$3" ] || fail "$1: expected [$3], got [$2]"; }
# The transaction ids that wrote a month's silver rows: unchanged ids mean the rows were not rewritten.
writers() { psql_dev -c "select string_agg(distinct xmin::text, ',') from silver.tlc_trips where data_month = '$1'"; }

psql_dev -c "select 1" >/dev/null 2>&1 || docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse createdb -U warehouse "$DB"
psql_dev <"$REPO/dbt/dev/tlc_fixture.sql" 2>&1 | grep -v NOTICE || true
echo "ok: fixture loaded into $DB"

build 2024-12
expect "silver after 2024-12" "$(counts tlc_trips)" "green 2024-12 2
yellow 2024-12 255"
expect "quarantine after 2024-12" "$(counts tlc_trips_quarantine)" "yellow 2024-12 1"
before=$(writers 2024-12)
echo "ok: 2024-12 built (257 clean, 1 quarantined)"

build 2025-01
expect "silver after 2025-01" "$(counts tlc_trips)" "green 2024-12 2
yellow 2024-12 255
green 2025-01 3
yellow 2025-01 253"
expect "quarantine after 2025-01" "$(counts tlc_trips_quarantine)" "yellow 2024-12 1
green 2025-01 1
yellow 2025-01 3"
expect "2024-12 rewritten by the 2025-01 build" "$(writers 2024-12)" "$before"
expect "half-loaded version y2 visible" \
  "$(psql_dev -c "select count(*) from silver.tlc_trips where _etag = '\"y2\"'")" 0
expect "quarantine reasons 2025-01" \
  "$(psql_dev -c "select string_agg(quarantine_reason, ',' order by quarantine_reason) from silver.tlc_trips_quarantine where data_month = '2025-01'")" \
  "dropoff_before_pickup,negative_amount,over_24_hours,pickup_outside_month"
echo "ok: 2025-01 built; 2024-12 untouched; the half-loaded version stays invisible"

build 2025-01
expect "silver after rebuilding 2025-01" "$(counts tlc_trips)" "green 2024-12 2
yellow 2024-12 255
green 2025-01 3
yellow 2025-01 253"
echo "ok: rebuilding 2025-01 is idempotent"

psql_dev <"$REPO/dbt/dev/tlc_republish.sql"
build 2025-01
expect "silver after republishing 2025-01" "$(counts tlc_trips)" "green 2024-12 2
yellow 2024-12 255
green 2025-01 3
yellow 2025-01 253"
expect "quarantine after republishing 2025-01" "$(counts tlc_trips_quarantine)" "yellow 2024-12 1
green 2025-01 1"
expect "yellow 2025-01 etags" \
  "$(psql_dev -c "select string_agg(distinct _etag, ',') from silver.tlc_trips where trip_type = 'yellow' and data_month = '2025-01'")" '"y2"'
expect "2024-12 rewritten by the republish rebuild" "$(writers 2024-12)" "$before"
expect "exposed trips 2025-01" \
  "$(psql_dev -c "select sum(trips) from exposed.tlc_daily_trips_by_borough where data_month = '2025-01'")" 256
expect "unknown-zone trips 2025-01" \
  "$(psql_dev -c "select sum(trips) from exposed.tlc_daily_trips_by_borough where data_month = '2025-01' and borough = 'Unknown'")" 1
echo "ok: a second etag replaces 2025-01 (yellow 253 rows, all y2); exposed reads gold and the zone seed"

# 30 more negative fares: 31 of 288 rows of 2024-12 (10.8 %) are quarantined, above the 10 % error.
psql_dev -c "insert into ds_source.tlc_yellow (_run_id, _source_uri, _etag, _chunk, tpep_pickup_datetime, tpep_dropoff_datetime, fare_amount, total_amount)
  select 'fixture__2024-12', 'fixture://trip-data/yellow_tripdata_2024-12.parquet', '\"y1\"', 3,
         timestamp '2024-12-20 10:00', timestamp '2024-12-20 10:10', -1, -1 from generate_series(1, 30)"
if dbt_tlc 2024-12; then fail "2024-12 at 10.8 % quarantined built without error"; fi
grep -q "FAIL 1 tlc_quarantine_share_error" /tmp/pplk8s-tlc-dbt-2024-12.log ||
  { tail -30 /tmp/pplk8s-tlc-dbt-2024-12.log >&2; fail "the build failed, but not on tlc_quarantine_share_error"; }
echo "ok: a month above 10 % quarantined fails the build"

echo "PASS: tlc dbt check"
