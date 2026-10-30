#!/usr/bin/env bash
# Semantic layer check (issue #100, semantic/PLAN.md SL-1): host dbt builds the sales, returns and
# finance models on dbt/dev/fixture.sql in the Compose warehouse's dbt_dev database, and asserts that
#   - `make dbt-validate` passes against it (dbt parse, metric descriptions and labels, mf validate-configs),
#   - the time spine lands in semantic.time_spine,
#   - the daily order metrics equal gold.daily_sales row for row, cancellation_rate included,
#   - revenue, returns and net revenue by day equal exposed.net_sales_daily row for row,
#   - the marketing metrics by day and channel equal gold.marketing_daily, their daily ratios equal
#     exposed.channel_performance_daily, and over the whole fixture cost per lead and per booking are
#     total spend over the total count, not an average of the daily ratios (SL-8),
#   - a metric without a description or a label fails the validation.
# Expects `make services-up`; never touches the `warehouse` database.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_dev
OUT=${TMPDIR:-/tmp}/pplk8s-semantic-check
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_dev() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"
}

export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_PROFILES_DIR="$REPO/dbt"
# The pins come from the image's requirements, so host and image run the same dbt and MetricFlow.
dbt_() { (cd "$REPO/dbt" && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt "$@"); }
mf_() { (cd "$REPO/dbt" && uvx --quiet --with-requirements requirements.txt --from dbt-metricflow mf "$@"); }
expect() { [ "$2" = "$3" ] || fail "$1: expected [$3], got [$2]"; }

mkdir -p "$OUT"
psql_dev -c "select 1" >/dev/null 2>&1 || docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse createdb -U warehouse "$DB"
psql_dev <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
echo "ok: fixture loaded into $DB"

# The time spine is tagged sales, so the sales build carries it; tlc has its own fixture and check.
dbt_ build --select tag:sales tag:returns tag:finance tag:marketing --exclude tag:tlc >"$OUT/build.log" 2>&1 ||
  { tail -30 "$OUT/build.log" >&2; fail "dbt build tag:sales tag:returns tag:finance tag:marketing"; }
expect "time spine rows" "$(psql_dev -c "select count(*) from semantic.time_spine")" 1461
echo "ok: sales, returns, finance and marketing built; semantic.time_spine has 1461 days"

make -s -C "$REPO" dbt-validate DBT_DBNAME="$DB" >"$OUT/validate.log" 2>&1 ||
  { tail -30 "$OUT/validate.log" >&2; fail "make dbt-validate against $DB"; }
grep -q "16 metrics described and labelled" "$OUT/validate.log" || fail "check_metrics did not report the 16 metrics"
echo "ok: make dbt-validate (parse, check_metrics, mf validate-configs) passes against $DB"

# Parity: every metric queried by day, loaded back into the warehouse and compared both ways with
# the hand-written aggregates (R1: the metric is the one definition; gold and exposed are the oracle).
mf_ query --metrics orders_total,orders_cancelled,revenue_eur,customers_distinct,cancellation_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/sales.csv" >"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the order metrics"; }
mf_ query --metrics revenue_eur,returns_eur,returns_count,net_revenue_eur \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/net.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the net revenue metrics"; }
psql_dev -c "set client_min_messages = warning" -c "create schema if not exists semantic_check" \
  -c "drop table if exists semantic_check.sales" \
  -c "create table semantic_check.sales (day date, orders_total bigint, orders_cancelled bigint, revenue_eur numeric, customers_distinct bigint, cancellation_rate numeric)" \
  -c "drop table if exists semantic_check.net" \
  -c "create table semantic_check.net (day date, revenue_eur numeric, returns_eur numeric, returns_count bigint, net_revenue_eur numeric)"
psql_dev -c "\\copy semantic_check.sales from stdin with (format csv, header true)" <"$OUT/sales.csv"
psql_dev -c "\\copy semantic_check.net from stdin with (format csv, header true)" <"$OUT/net.csv"
days=$(psql_dev -c "select count(*) from gold.daily_sales")
[ "$days" -ge 2 ] || fail "gold.daily_sales has $days rows; the fixture should give at least 2 days"
expect "mf days" "$(psql_dev -c "select count(*) from semantic_check.sales")" "$days"
# Rows in either side and not the other; the rate is compared at six decimals.
expect "order metrics vs gold.daily_sales (rows differing)" "$(psql_dev -c "
  with gold as (select order_date, orders_total, orders_cancelled, revenue_eur, customers_distinct,
                       round(orders_cancelled::numeric / orders_total, 6) as cancellation_rate from gold.daily_sales),
       mf as (select day, orders_total, orders_cancelled, revenue_eur, customers_distinct, round(cancellation_rate, 6) from semantic_check.sales)
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d")" 0
expect "net metrics vs exposed.net_sales_daily (rows differing)" "$(psql_dev -c "
  with exposed as (select order_date, revenue_eur, returns_eur, returns_count, net_revenue_eur from exposed.net_sales_daily),
       mf as (select * from semantic_check.net)
  select count(*) from ((select * from exposed except select * from mf) union all (select * from mf except select * from exposed)) d")" 0
echo "ok: the eight sales metrics equal gold.daily_sales and exposed.net_sales_daily on $days days"

# Marketing (SL-8): the simple metrics by day and channel against gold.marketing_daily, the ratios
# against exposed.channel_performance_daily (per day), then the whole fixture as one period.
mf_ query --metrics ad_spend_eur,ad_clicks,leads,bookings,booking_value_eur,cost_per_lead_eur,cost_per_booking_eur \
  --group-by metric_time__day,campaign__channel --order metric_time__day --csv "$OUT/marketing.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the marketing metrics"; }
mf_ query --metrics ad_spend_eur,leads,bookings,cost_per_lead_eur,cost_per_booking_eur,lead_to_booking_rate \
  --csv "$OUT/marketing_period.csv" >>"$OUT/query.log" 2>&1 || { cat "$OUT/query.log" >&2; fail "mf query of the marketing period"; }
psql_dev -c "set client_min_messages = warning" -c "drop table if exists semantic_check.marketing" \
  -c "create table semantic_check.marketing (day date, channel text, ad_spend_eur numeric, ad_clicks bigint, leads bigint, bookings bigint, booking_value_eur numeric, cost_per_lead_eur numeric, cost_per_booking_eur numeric)" \
  -c "drop table if exists semantic_check.marketing_period" \
  -c "create table semantic_check.marketing_period (ad_spend_eur numeric, leads bigint, bookings bigint, cost_per_lead_eur numeric, cost_per_booking_eur numeric, lead_to_booking_rate numeric)"
psql_dev -c "\\copy semantic_check.marketing from stdin with (format csv, header true)" <"$OUT/marketing.csv"
psql_dev -c "\\copy semantic_check.marketing_period from stdin with (format csv, header true)" <"$OUT/marketing_period.csv"
expect "marketing metrics vs gold.marketing_daily (rows differing)" "$(psql_dev -c "
  with gold as (select activity_date, channel, ad_spend_eur, ad_clicks, leads, bookings, booking_value_eur from gold.marketing_daily),
       mf as (select day, channel, ad_spend_eur, ad_clicks, leads, bookings, booking_value_eur from semantic_check.marketing)
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d")" 0
expect "marketing ratios vs exposed.channel_performance_daily (rows differing)" "$(psql_dev -c "
  with exposed as (select activity_date, channel, round(cost_per_lead_eur, 4), round(cost_per_booking_eur, 4) from exposed.channel_performance_daily),
       mf as (select day, channel, round(cost_per_lead_eur, 4), round(cost_per_booking_eur, 4) from semantic_check.marketing)
  select count(*) from ((select * from exposed except select * from mf) union all (select * from mf except select * from exposed)) d")" 0
expect "the fixture's cost per lead and per booking, and its lead-to-booking rate" "$(psql_dev -c "
  select round(cost_per_lead_eur, 2) || ' ' || round(cost_per_booking_eur, 2) || ' ' || round(lead_to_booking_rate, 2) from semantic_check.marketing_period")" "39.00 130.00 0.30"
expect "spend over count, from gold" "$(psql_dev -c "
  select round(sum(ad_spend_eur) / sum(leads), 2) || ' ' || round(sum(ad_spend_eur) / sum(bookings), 2) from gold.marketing_daily")" "39.00 130.00"
expect "the average of exposed's daily cost per booking (what the metric is not)" "$(psql_dev -c "
  select round(avg(cost_per_booking_eur), 2) from (select activity_date, sum(ad_spend_eur) / nullif(sum(bookings), 0) as cost_per_booking_eur from exposed.channel_performance_daily group by activity_date) d")" "152.50"
echo "ok: the marketing metrics equal gold.marketing_daily and exposed.channel_performance_daily; cost per booking 130.00 over the fixture, not the daily average 152.50"

# A metric without words fails the stage: drop a labelled, undescribed metric beside the real ones.
stray="$REPO/dbt/models/semantic/zz_semantic_check_stray.yml"
trap 'rm -f "$stray"' EXIT
cat >"$stray" <<'YAML'
version: 2
metrics:
  - name: zz_stray_orders
    label: Stray
    type: simple
    type_params:
      measure: orders_total
YAML
if make -s -C "$REPO" dbt-validate DBT_DBNAME="$DB" >"$OUT/stray.log" 2>&1; then fail "dbt-validate passed with an undescribed metric"; fi
grep -q "check_metrics: metric zz_stray_orders: no description" "$OUT/stray.log" ||
  { tail -20 "$OUT/stray.log" >&2; fail "the validation failed, but not on the undescribed metric"; }
rm -f "$stray"
echo "ok: a metric without a description fails make dbt-validate"

echo "PASS: semantic check"
