#!/usr/bin/env bash
# Source freshness check (#130, semantic/PLAN.md SL-12): host dbt runs `dbt source freshness` on the dev
# fixtures in the Compose warehouse's dbt_freshness database, and asserts that
#   - with every landed table loaded an hour ago, it passes and records `pass` for each checked table
#     in ops.source_freshness, open_meteo_hourly_weather left out (no freshness: loaded by hand),
#   - a table whose loads stopped past its error_after fails it (exit 1) and records `error` for that
#     table only, one past its warn_after records `warn`, and a dropped table records `runtime error`,
#   - re-running replaces each table's row rather than adding one,
#   - `dbt build` runs the same on-run-end hook and leaves the rows untouched,
#   - the warehouse's sql_exporter collector (platform/compose/sql-exporter/source-freshness.collector.yml)
#     exports dbt's verdict and the newest load per table, which SourceStale reads
#     (its promtool tests: tests/monitoring/source-freshness.test.yaml, `make rules-test`).
# Expects `make services-up`; never touches the `warehouse` database.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_freshness
OUT=${TMPDIR:-/tmp}/pplk8s-source-freshness-check
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml")
SQL_EXPORTER_IMAGE=burningalchemist/sql_exporter:0.24.9 # compose.yaml's
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_db() { "${COMPOSE[@]}" exec -T warehouse psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"; }
expect() { [ "$2" = "$3" ] || fail "$1: expected [$3], got [$2]"; }

export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_PROFILES_DIR="$REPO/dbt"
# The pins come from the image's requirements, so host and image (the CronJob's) run the same dbt.
dbt_() { (cd "$REPO/dbt" && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt "$@"); }
freshness() { dbt_ source freshness >"$OUT/freshness-$1.log" 2>&1; }
statuses() { psql_db -F= -c "select table_name, status from ops.source_freshness order by table_name" | paste -sd' '; }
LANDED="partner_returns synthetic_ad_spend synthetic_applications synthetic_bookings synthetic_call_transcripts synthetic_campaigns
  synthetic_customer_actions synthetic_customers synthetic_leads synthetic_orders synthetic_outreach_messages synthetic_outreach_replies
  synthetic_partner_contacts synthetic_partners tlc_green tlc_yellow"
all_with() { local t out=""; for t in $LANDED; do out+="$t=${2:-$1} "; done; echo "${out% }"; }

mkdir -p "$OUT"
psql_db -c "select 1" >/dev/null 2>&1 || "${COMPOSE[@]}" exec -T warehouse createdb -U warehouse "$DB"
psql_db -c "drop schema if exists ops cascade" 2>&1 | grep -v NOTICE || true
for fixture in fixture.sql tlc_fixture.sql; do
  psql_db <"$REPO/dbt/dev/$fixture" 2>&1 | grep -v NOTICE || true
done
# Every landed table, loaded an hour ago (the fixtures' own _loaded_at are fixed dates in the past).
loaded() { psql_db -c "update ds_source.$1 set _loaded_at = now() - interval '$2'"; }
for t in $LANDED open_meteo_hourly_weather; do loaded "$t" "1 hour"; done
echo "ok: fixtures loaded into $DB, every landed table last loaded an hour ago"

freshness fresh || { tail -30 "$OUT/freshness-fresh.log" >&2; fail "dbt source freshness on fresh data"; }
expect "statuses on fresh data" "$(statuses)" "$(all_with pass)"
echo "ok: dbt source freshness passes on fresh data and records pass for the 16 landed tables (open_meteo left out)"

# Orders stopped 40 hours ago (error_after 36 h), leads 30 hours ago (warn_after 26 h), tlc_green is gone.
loaded synthetic_orders "40 hours"
loaded synthetic_leads "30 hours"
psql_db -c "drop table ds_source.tlc_green cascade" 2>&1 | grep -v NOTICE || true
rc=0; freshness stopped || rc=$?
expect "dbt source freshness exit code with a stopped source" "$rc" 1
want=$(all_with pass | sed -e 's/synthetic_orders=pass/synthetic_orders=error/' \
  -e 's/synthetic_leads=pass/synthetic_leads=warn/' -e 's/tlc_green=pass/tlc_green=runtime error/')
expect "statuses with stopped sources" "$(statuses)" "$want"
expect "rows per table" "$(psql_db -c "select count(*) from ops.source_freshness")" 16
age=$(psql_db -c "select round(extract(epoch from checked_at - max_loaded_at) / 3600) from ops.source_freshness where table_name = 'synthetic_orders'")
expect "synthetic_orders' recorded age in hours" "$age" 40
expect "synthetic_orders' error_after" "$(psql_db -c "select error_after_seconds from ops.source_freshness where table_name = 'synthetic_orders'")" 129600
echo "ok: a stopped source fails it (exit 1) and records error, a late one warn, a dropped one runtime error; one row per table"

before=$(psql_db -c "select max(checked_at) from ops.source_freshness")
dbt_ build --select tag:sales --exclude tag:tlc >"$OUT/build.log" 2>&1 || { tail -30 "$OUT/build.log" >&2; fail "dbt build tag:sales"; }
grep -q "OK hook: pplk8s.on-run-end.0" "$OUT/build.log" || fail "dbt build did not run the on-run-end hook"
expect "rows after dbt build" "$(psql_db -c "select max(checked_at) from ops.source_freshness")" "$before"
echo "ok: dbt build runs the same hook, which leaves ops.source_freshness alone"

# The warehouse exporter's own collector file, against this database instead of `warehouse`.
cfg="$OUT/exporter"
mkdir -p "$cfg" && chmod 755 "$cfg"
cp "$REPO/platform/compose/sql-exporter/source-freshness.collector.yml" "$cfg/"
cat >"$cfg/sql_exporter.yml" <<YAML
target:
  data_source_name: "postgresql://set-by-env"
  collectors: [source_freshness]
collector_files: ["*.collector.yml"]
YAML
chmod 644 "$cfg"/*
name=pplk8s-source-freshness-exporter
docker rm -f "$name" >/dev/null 2>&1 || true
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --network pplk8s -v "$cfg:/etc/sql_exporter:ro" \
  -e SQLEXPORTER_TARGET_DSN="postgresql://warehouse:${WAREHOUSE_PASSWORD:-warehouse}@warehouse:5432/$DB?sslmode=disable" \
  "$SQL_EXPORTER_IMAGE" -config.file=/etc/sql_exporter/sql_exporter.yml >/dev/null
metrics=""
for _ in $(seq 30); do
  metrics=$(docker run --rm --network pplk8s curlimages/curl:8.11.1 -sf "http://$name:9399/metrics" 2>/dev/null || true)
  grep -q '^ops_source_freshness_checked_timestamp_seconds' <<<"$metrics" && break
  sleep 1
done
printf '%s\n' "$metrics" >"$OUT/metrics.txt"
expect "exported verdicts" "$(grep -c '^ops_source_freshness_checked_timestamp_seconds{' <<<"$metrics")" 16
grep -q '^ops_source_freshness_checked_timestamp_seconds{source="ds_source",status="error",table="synthetic_orders"[,}]' <<<"$metrics" ||
  fail "the exporter does not show synthetic_orders as error (see $OUT/metrics.txt)"
grep -q '^ops_source_max_loaded_at_seconds{source="ds_source",table="tlc_green"[,}].* 0$' <<<"$metrics" ||
  fail "the exporter does not show tlc_green's load as 0 (see $OUT/metrics.txt)"
loaded_orders=$(grep '^ops_source_max_loaded_at_seconds{source="ds_source",table="synthetic_orders"[,}]' <<<"$metrics" | awk '{printf "%d", $2}')
expect "exported age of synthetic_orders in hours" "$(( ($(date +%s) - loaded_orders + 1800) / 3600 ))" 40
echo "ok: the warehouse sql_exporter's collector exports the 16 verdicts and each table's newest load"

echo "PASS: source freshness check"
