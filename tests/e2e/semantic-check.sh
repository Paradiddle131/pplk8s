#!/usr/bin/env bash
# Semantic layer check (issue #100, semantic/PLAN.md SL-1): host dbt builds the sales, returns and
# finance models on dbt/dev/fixture.sql in the Compose warehouse's dbt_dev database, and asserts that
#   - `make dbt-validate` passes against it (dbt parse, the agent-ready standard, mf validate-configs),
#   - the time spine lands in semantic.time_spine,
#   - the daily order metrics equal gold.daily_sales row for row, cancellation_rate included,
#   - revenue, returns and net revenue by day equal exposed.net_sales_daily row for row,
#   - the marketing metrics by day and channel equal gold.marketing_daily, their daily ratios equal
#     exposed.channel_performance_daily, and over the whole fixture cost per lead and per booking are
#     total spend over the total count, not an average of the daily ratios (SL-8),
#   - the order metrics by customer country equal exposed.sales_by_country_daily, and revenue by
#     signup cohort equals a direct join of silver (the customers semantic model),
#   - a public model whose SQL renames or retypes a column its contract declares fails dbt build,
#   - a metric without a description or a label, or a public column without a data_type, fails the validation,
#   - every layer hop reconciles in dbt build, and a return seeded on a day without orders lands in
#     exposed.net_sales_daily as a day with revenue 0, every hop passing (semantic/PLAN.md SL-9, #150).
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
expect "layer hops passed" "$(grep -c " PASS hop_" "$OUT/build.log")" 26
echo "ok: the 26 layer hops (bronze -> silver -> gold -> exposed, metric -> gold) reconcile in dbt build"

make -s -C "$REPO" dbt-validate DBT_DBNAME="$DB" >"$OUT/validate.log" 2>&1 ||
  { tail -30 "$OUT/validate.log" >&2; fail "make dbt-validate against $DB"; }
grep -q "7 semantic models and 16 metrics described" "$OUT/validate.log" || fail "check_standard did not report the 7 semantic models and 16 metrics"
echo "ok: make dbt-validate (parse, check_standard, mf validate-configs) passes against $DB"

# Parity: every metric queried by day, loaded back into the warehouse and compared both ways with
# the hand-written aggregates (R1: the metric is the one definition; gold and exposed are the oracle).
# A simple metric is NULL where gold says 0, in a day or group it has no rows (dbt-core 1.12.6 drops
# fill_nulls_with, #137), so the counts and sums are compared through coalesce.
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
       mf as (select day, revenue_eur, coalesce(returns_eur, 0), coalesce(returns_count, 0), net_revenue_eur from semantic_check.net)
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
       mf as (select day, channel, coalesce(ad_spend_eur, 0), coalesce(ad_clicks, 0), coalesce(leads, 0), coalesce(bookings, 0),
                     coalesce(booking_value_eur, 0) from semantic_check.marketing)
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

# Customers: the orders metrics group by the customer's country and signup cohort through the
# customer entity alone, and equal exposed.sales_by_country_daily and a direct join of silver.
mf_ query --metrics orders_total,revenue_eur --group-by metric_time__day,customer__country \
  --order metric_time__day --csv "$OUT/country.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the order metrics by customer country"; }
mf_ query --metrics revenue_eur --group-by customer__signup_date__month \
  --csv "$OUT/cohort.csv" >>"$OUT/query.log" 2>&1 || { cat "$OUT/query.log" >&2; fail "mf query of revenue by signup cohort"; }
psql_dev -c "set client_min_messages = warning" -c "drop table if exists semantic_check.country" \
  -c "create table semantic_check.country (day date, country text, orders_total bigint, revenue_eur numeric)" \
  -c "drop table if exists semantic_check.cohort" -c "create table semantic_check.cohort (signup_month date, revenue_eur numeric)"
psql_dev -c "\\copy semantic_check.country from stdin with (format csv, header true)" <"$OUT/country.csv"
psql_dev -c "\\copy semantic_check.cohort from stdin with (format csv, header true)" <"$OUT/cohort.csv"
[ "$(psql_dev -c "select count(*) from exposed.sales_by_country_daily")" -ge 2 ] || fail "exposed.sales_by_country_daily has fewer than 2 rows"
expect "order metrics by country vs exposed.sales_by_country_daily (rows differing)" "$(psql_dev -c "
  with exposed as (select order_date, country, orders, revenue_eur from exposed.sales_by_country_daily),
       mf as (select day, country, orders_total, coalesce(revenue_eur, 0) from semantic_check.country)
  select count(*) from ((select * from exposed except select * from mf) union all (select * from mf except select * from exposed)) d")" 0
expect "revenue by signup cohort vs silver (rows differing)" "$(psql_dev -c "
  with silver as (select date_trunc('month', c.signup_date)::date, coalesce(sum(case when o.status <> 'cancelled' then o.amount end), 0)
                  from silver.orders o join silver.customers c on c.customer_id = o.customer_id group by 1),
       mf as (select signup_month, coalesce(revenue_eur, 0) from semantic_check.cohort)
  select count(*) from ((select * from silver except select * from mf) union all (select * from mf except select * from silver)) d")" 0
echo "ok: orders metrics by customer country equal exposed.sales_by_country_daily; revenue by signup cohort equals silver"

# Contracts: gold.daily_sales as an agent reads it, with its SQL changed under the same YAML, fails the
# build before it replaces the table: one model renames order_date, the other casts revenue_eur to text.
contract_yml="$REPO/dbt/models/gold/zz_semantic_check_contract.yml"
renamed="$REPO/dbt/models/gold/gld_zz_contract_renamed.sql"
retyped="$REPO/dbt/models/gold/gld_zz_contract_retyped.sql"
trap 'rm -f "$contract_yml" "$renamed" "$retyped"' EXIT
echo "select order_date as sale_date, revenue_eur from {{ ref('gld_daily_sales') }}" >"$renamed"
echo "select order_date, cast(revenue_eur as text) as revenue_eur from {{ ref('gld_daily_sales') }}" >"$retyped"
{ printf 'version: 2\nmodels:\n'; for model in gld_zz_contract_renamed gld_zz_contract_retyped; do cat <<YAML; done; } >"$contract_yml"
  - name: $model
    description: gold.daily_sales with a changed column.
    columns:
      - name: order_date
        description: Natural key.
        data_type: date
      - name: revenue_eur
        description: Sum of amount for non-cancelled orders.
        data_type: numeric
YAML
if dbt_ build --select gld_zz_contract_renamed gld_zz_contract_retyped >"$OUT/contract.log" 2>&1; then
  fail "dbt build passed a public model off its contract"
fi
# dbt's mismatch table: the renamed column is missing in the contract, the retyped one mismatches.
for row in "order_date *\| *\| DATE *\| missing in definition" "sale_date *\| DATE *\| *\| missing in contract" \
  "revenue_eur *\| TEXT *\| DECIMAL *\| data type mismatch"; do
  grep -Eq "\| $row" "$OUT/contract.log" || { tail -40 "$OUT/contract.log" >&2; fail "the build failed, but not on: $row"; }
done
[ "$(grep -c "This model has an enforced contract that failed" "$OUT/contract.log")" -eq 2 ] ||
  { tail -40 "$OUT/contract.log" >&2; fail "expected both models to fail on their contract"; }
rm -f "$contract_yml" "$renamed" "$retyped"
echo "ok: a renamed and a retyped column of a public model fail dbt build on its contract"

# A return recorded on a day without orders gets its own row of exposed.net_sales_daily, revenue 0, so
# finance's table still agrees with the returns metrics and every hop passes (#150).
psql_dev -c "insert into ds_source.partner_returns values ('R-SEEDED', 'O-9', '2026-10-03 11:00+00', 9.00, 'damaged',
  'gcs-run-c', 'gs://landing/returns/2026-10-03.jsonl', 1, '2026-10-04 06:00+00')"
seeded_ok=0
dbt_ build --select tag:returns tag:finance >"$OUT/hop.log" 2>&1 && seeded_ok=1
seeded_row=$(psql_dev -c "select round(revenue_eur, 2), returns_count, round(returns_eur, 2), round(net_revenue_eur, 2)
  from exposed.net_sales_daily where order_date = '2026-10-03'")
psql_dev -c "delete from ds_source.partner_returns where return_id = 'R-SEEDED'"
[ "$seeded_ok" = 1 ] || { grep " FAIL \| ERROR " "$OUT/hop.log" >&2; fail "dbt build failed on a return recorded on a day without orders"; }
expect "exposed.net_sales_daily on the seeded return's day" "$seeded_row" "0.00|1|9.00|-9.00"
dbt_ build --select tag:returns tag:finance >"$OUT/hop.log" 2>&1 || { tail -30 "$OUT/hop.log" >&2; fail "rebuild after the seeded return"; }
echo "ok: a return on a day without orders lands in exposed.net_sales_daily with revenue 0, every hop passing"

# Straying from the standard fails the stage: a labelled, undescribed metric beside the real ones, and
# a gold model without the layer's prefix, a description, a described column or a column type.
stray="$REPO/dbt/models/semantic/zz_semantic_check_stray.yml"
stray_model="$REPO/dbt/models/gold/zz_semantic_check_stray.sql"
trap 'rm -f "$stray" "$stray_model"' EXIT
echo "select 1 as stray_id" >"$stray_model"
cat >"$stray" <<'YAML'
version: 2
models:
  - name: zz_semantic_check_stray
    columns:
      - name: stray_id
metrics:
  - name: zz_stray_orders
    label: Stray
    type: derived
    expr: orders_total
    input_metrics: [orders_total]
YAML
if make -s -C "$REPO" dbt-validate DBT_DBNAME="$DB" >"$OUT/stray.log" 2>&1; then fail "dbt-validate passed off the standard"; fi
for problem in "metric zz_stray_orders: no description" \
  "model zz_semantic_check_stray: in gold, so its name starts with gld_" \
  "public model zz_semantic_check_stray: no description" \
  "public model zz_semantic_check_stray: column stray_id has no description" \
  "public model zz_semantic_check_stray: column stray_id has no data_type"; do
  grep -qF "check_standard: $problem" "$OUT/stray.log" ||
    { tail -20 "$OUT/stray.log" >&2; fail "the validation failed, but not on: $problem"; }
done
rm -f "$stray" "$stray_model"
echo "ok: an undescribed metric and an unprefixed, undescribed, untyped gold model fail make dbt-validate"

echo "PASS: semantic check"
