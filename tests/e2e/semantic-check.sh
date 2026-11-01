#!/usr/bin/env bash
# Semantic layer check (issue #100, semantic/PLAN.md SL-1): host dbt builds the sales, returns and
# finance models on dbt/dev/fixture.sql in the Compose warehouse's dbt_dev database, and asserts that
#   - `make dbt-validate` passes against it (dbt parse, the agent-ready standard, mf validate-configs),
#   - the time spine lands in semantic.time_spine,
#   - the daily order metrics equal gold.daily_sales row for row, cancellation_rate included,
#   - revenue, returns and net revenue by day equal exposed.net_sales_daily row for row,
#   - the marketing metrics by day and channel equal gold.marketing_daily, their daily ratios equal
#     exposed.channel_performance_daily, the lead-to-booking rate by day equals gold.lead_conversion_daily,
#     and over the whole fixture cost per lead and per booking are
#     total spend over the total count, not an average of the daily ratios (SL-8),
#   - the order metrics by customer country equal exposed.sales_by_country_daily, and revenue by
#     signup cohort equals a direct join of silver (the customers semantic model),
#   - the partner-outreach metrics equal gold.partner_outreach_daily, the reply rate over the fixture is
#     messages replied over messages sent, and the activation list leaves out every contact without consent,
#     opted out (an older snapshot backfilled later included) or messaged within the cooldown (SL-16),
#   - the recruitment metrics equal gold.recruitment_daily; replayed one extract at a time with a dbt build after each,
#     as recruitment_elt runs, the snapshot keeps every stage change, a backfill of an older extract moves nobody back,
#     and candidates_in_stage by candidate__stage (MetricFlow's SCD join) equals gold.candidates_in_stage_daily (SL-17),
#   - the customer-actions metrics (actions per type, engaged customers over 7 and 28 days, the site
#     funnel) equal gold.customer_actions_daily and gold.customer_engagement_daily, and an incremental
#     build merges a late action into its own day and a redelivered one once (SL-15),
#   - a public model whose SQL renames or retypes a column its contract declares fails dbt build,
#   - a metric without a description or a label, or a public column without a data_type, fails the validation,
#   - the call signals' metrics by day and topic equal gold.call_signals_daily, the current prompt's labels
#     are scored on the golden set's 15 calls, a second or `--full-refresh` build re-labels nothing, a
#     transcript without a recording waits unlabelled, seeded wrong labels fail the agreement test, and failed
#     calls past the share fail their test and are retried by the next build (SL-18),
#   - a metric over a model-derived column without "Model-derived" in its description fails the validation,
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
# The call labels are incremental and never fully refreshed: start them from an empty table each check.
psql_dev -c "drop table if exists silver.call_transcript_labels, silver.call_golden_labels cascade" 2>&1 | grep -v NOTICE || true
dbt_ build --select tag:sales tag:returns tag:finance tag:marketing tag:customer_actions tag:partner_outreach tag:recruitment tag:call_transcripts --exclude tag:tlc >"$OUT/build.log" 2>&1 ||
  { tail -30 "$OUT/build.log" >&2; fail "dbt build tag:sales tag:returns tag:finance tag:marketing tag:customer_actions tag:partner_outreach tag:recruitment tag:call_transcripts"; }
expect "time spine rows" "$(psql_dev -c "select count(*) from semantic.time_spine")" 1461
echo "ok: sales, returns, finance, marketing, customer actions, partner outreach, recruitment and call transcripts built; semantic.time_spine has 1461 days"
expect "layer hops passed" "$(grep -c " PASS hop_" "$OUT/build.log")" 61
echo "ok: the 61 layer hops (bronze -> silver -> gold -> exposed, metric -> gold) reconcile in dbt build"

make -s -C "$REPO" dbt-validate DBT_DBNAME="$DB" >"$OUT/validate.log" 2>&1 ||
  { tail -30 "$OUT/validate.log" >&2; fail "make dbt-validate against $DB"; }
grep -q "15 semantic models, 39 metrics and 7 saved queries described" "$OUT/validate.log" ||
  fail "check_standard did not report the 15 semantic models, 39 metrics and 7 saved queries"
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

# The lead-to-booking rate by the lead's creation day against gold.lead_conversion_daily (SL-9's
# conversion hop renders the same rate inside dbt build; this compares MetricFlow's own query).
mf_ query --metrics leads,lead_to_booking_rate --group-by metric_time__day --order metric_time__day \
  --csv "$OUT/lead_conversion.csv" >>"$OUT/query.log" 2>&1 || { cat "$OUT/query.log" >&2; fail "mf query of the lead-to-booking rate"; }
psql_dev -c "set client_min_messages = warning" -c "drop table if exists semantic_check.lead_conversion" \
  -c "create table semantic_check.lead_conversion (day date, leads bigint, lead_to_booking_rate numeric)"
psql_dev -c "\\copy semantic_check.lead_conversion from stdin with (format csv, header true)" <"$OUT/lead_conversion.csv"
expect "lead-to-booking rate vs gold.lead_conversion_daily (rows differing)" "$(psql_dev -c "
  with gold as (select created_date, leads, round(lead_to_booking_rate, 6) from gold.lead_conversion_daily),
       mf as (select day, leads, round(coalesce(lead_to_booking_rate, 0), 6) from semantic_check.lead_conversion)
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d")" 0
expect "the fixture's daily lead-to-booking rates" "$(psql_dev -c "
  select string_agg(created_date || ' ' || round(lead_to_booking_rate, 2), ', ' order by created_date) from gold.lead_conversion_daily")" \
  "2026-10-01 0.33, 2026-10-02 0.25"
echo "ok: the lead-to-booking rate by creation day equals gold.lead_conversion_daily (0.33, 0.25)"
# Call signals (SL-18): labels from the recorded label calls, scored on the golden set; the metrics by
# day and topic equal gold.call_signals_daily, the rates over the fixture equal gold's sums.
mf_ query --metrics calls_labelled,calls_with_objection,positive_calls --group-by metric_time__day,call__topic \
  --order metric_time__day --csv "$OUT/calls.csv" >>"$OUT/query.log" 2>&1 || { cat "$OUT/query.log" >&2; fail "mf query of the call metrics"; }
mf_ query --metrics objection_rate,positive_sentiment_share --csv "$OUT/calls_period.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the call rates"; }
psql_dev -c "set client_min_messages = warning" -c "drop table if exists semantic_check.calls" \
  -c "create table semantic_check.calls (day date, topic text, calls_labelled bigint, calls_with_objection bigint, positive_calls bigint)" \
  -c "drop table if exists semantic_check.calls_period" -c "create table semantic_check.calls_period (objection_rate numeric, positive_sentiment_share numeric)"
psql_dev -c "\\copy semantic_check.calls from stdin with (format csv, header true)" <"$OUT/calls.csv"
psql_dev -c "\\copy semantic_check.calls_period from stdin with (format csv, header true)" <"$OUT/calls_period.csv"
expect "calls labelled in silver (every fixture call has a recording)" "$(psql_dev -c "select count(*) from silver.call_signals")" 12
expect "call metrics vs gold.call_signals_daily (rows differing)" "$(psql_dev -c "
  with gold as (select call_date, topic, calls_labelled, calls_with_objection, positive_calls from gold.call_signals_daily),
       mf as (select day, topic, coalesce(calls_labelled, 0), coalesce(calls_with_objection, 0), coalesce(positive_calls, 0) from semantic_check.calls)
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d")" 0
expect "the fixture's objection rate and positive-sentiment share, mf vs gold" "$(psql_dev -c "
  select round(objection_rate, 4) || ' ' || round(positive_sentiment_share, 4) from semantic_check.calls_period")" "$(psql_dev -c "
  select round(sum(calls_with_objection)::numeric / sum(calls_labelled), 4) || ' ' || round(sum(positive_calls)::numeric / sum(calls_labelled), 4) from gold.call_signals_daily")"
expect "signals of prompt v1 scored on the golden set, each at or above its thresholds" "$(psql_dev -c "
  select count(*) || ' ' || min(calls_compared) || ' ' || bool_and(accuracy >= min_accuracy and kappa >= min_kappa)
  from silver.call_label_agreement where prompt_version = 'v1'")" "4 15 true"
echo "ok: the call metrics equal gold.call_signals_daily; v1's labels meet their thresholds on the golden set's 15 calls"

# Labelled once: a second build and a --full-refresh build send no call (labelled_at, from the recording,
# would not move anyway, so the rows' ctid shows they were not rewritten), and a call with no recording waits.
labelled() { psql_dev -c "select count(*) || ' ' || string_agg(ctid::text, ',' order by transcript_id) from silver.call_transcript_labels"; }
before=$(labelled)
psql_dev -c "insert into ds_source.synthetic_call_transcripts values ('T-UNRECORDED', 1, '2026-10-02 16:00+00', 60,
  'Agent: Thanks for calling. Customer: Nothing recorded this.', 'run-call-2c', '2026-10-02 00:00+00', '2026-10-03 00:00+00', 1,
  'fixture://call_transcripts', '2026-10-03 07:00+00')"
dbt_ build --select tag:call_transcripts,tag:silver >"$OUT/incremental.log" 2>&1 || { tail -30 "$OUT/incremental.log" >&2; fail "incremental build of the call labels"; }
dbt_ build --full-refresh --select slv_call_transcript_labels >>"$OUT/incremental.log" 2>&1 || { tail -30 "$OUT/incremental.log" >&2; fail "--full-refresh build of the call labels"; }
expect "call labels after a second and a --full-refresh build" "$(labelled)" "$before"
expect "calls in silver, and labelled" "$(psql_dev -c "select count(*) from silver.call_transcripts")|$(psql_dev -c "select count(*) from silver.call_signals")" "13|12"
psql_dev -c "delete from ds_source.synthetic_call_transcripts where transcript_id = 'T-UNRECORDED'"
echo "ok: a second and a --full-refresh build re-label nothing; a call without a recording waits unlabelled"

# Seeded wrong labels fail the agreement test: four golden calls labelled with the wrong topic.
psql_dev -c "update silver.call_golden_labels set topic = case topic when 'product' then 'delivery' else 'product' end
  where transcript_id in (select transcript_id from silver.call_golden_labels order by transcript_id limit 4)"
if dbt_ build --select slv_call_label_agreement >"$OUT/agreement.log" 2>&1; then fail "dbt build passed seeded wrong labels"; fi
grep -q "FAIL 1 call_labels_agree_with_golden_set" "$OUT/agreement.log" || { tail -30 "$OUT/agreement.log" >&2; fail "the build failed, but not on the agreement test"; }
psql_dev -c "drop table silver.call_golden_labels cascade" 2>&1 | grep -v NOTICE || true

# Failed calls past the share fail their test, and the next build retries them: two of 15 is above 0.1.
dbt_ build --select slv_call_golden_labels slv_call_label_agreement >"$OUT/agreement.log" 2>&1 || { tail -30 "$OUT/agreement.log" >&2; fail "relabel the golden set"; }
psql_dev -c "update silver.call_golden_labels set status = 'quota exceeded', topic = null, objection = null, sentiment = null, next_step = null
  where transcript_id in (select transcript_id from silver.call_golden_labels order by transcript_id limit 2)"
if dbt_ test --select slv_call_golden_labels >"$OUT/failed.log" 2>&1; then fail "dbt test passed two failed calls in 15"; fi
grep -q "FAIL 1 failed_call_share_slv_call_golden_labels_status" "$OUT/failed.log" || { tail -30 "$OUT/failed.log" >&2; fail "the test failed, but not on the failed-call share"; }
dbt_ build --select slv_call_golden_labels slv_call_label_agreement >"$OUT/failed.log" 2>&1 || { tail -30 "$OUT/failed.log" >&2; fail "retry of the failed calls"; }
expect "failed golden calls after the retry" "$(psql_dev -c "select count(*) from silver.call_golden_labels where status <> ''")" 0
echo "ok: seeded wrong labels fail the agreement test; failed calls past their share fail theirs and the next build retries them"

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

# Customer actions (SL-15): actions per type against gold.customer_actions_daily; engaged customers over
# 7 and 28 days and the site funnel by day against gold.customer_engagement_daily, on gold's days (a
# cumulative metric also has rows for the days after, which gold does not hold).
mf_ query --metrics customer_actions --group-by metric_time__day,customer_action__action_type \
  --order metric_time__day --csv "$OUT/actions.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the actions per type"; }
mf_ query --metrics engaged_customers_7d,engaged_customers_28d,site_sessions,cart_sessions,checkout_sessions,view_to_cart_rate,cart_to_checkout_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/engagement.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the engagement and funnel metrics"; }
psql_dev -c "set client_min_messages = warning" -c "drop table if exists semantic_check.actions" \
  -c "create table semantic_check.actions (day date, action_type text, customer_actions bigint)" \
  -c "drop table if exists semantic_check.engagement" \
  -c "create table semantic_check.engagement (day date, engaged_customers_7d bigint, engaged_customers_28d bigint, site_sessions bigint, cart_sessions bigint, checkout_sessions bigint, view_to_cart_rate numeric, cart_to_checkout_rate numeric)"
psql_dev -c "\\copy semantic_check.actions from stdin with (format csv, header true)" <"$OUT/actions.csv"
psql_dev -c "\\copy semantic_check.engagement from stdin with (format csv, header true)" <"$OUT/engagement.csv"
engagement_vs_gold() {
  psql_dev -c "
  with gold as (select activity_date, engaged_customers_7d, engaged_customers_28d, site_sessions, cart_sessions, checkout_sessions,
                       round(view_to_cart_rate, 6), round(cart_to_checkout_rate, 6) from gold.customer_engagement_daily),
       mf as (select day, engaged_customers_7d, engaged_customers_28d, coalesce(site_sessions, 0), coalesce(cart_sessions, 0),
                     coalesce(checkout_sessions, 0), round(view_to_cart_rate, 6), round(cart_to_checkout_rate, 6)
              from semantic_check.engagement where day in (select activity_date from gold.customer_engagement_daily))
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d"
}
expect "actions per type vs gold.customer_actions_daily (rows differing)" "$(psql_dev -c "
  with gold as (select activity_date, action_type, actions from gold.customer_actions_daily),
       mf as (select day, action_type, customer_actions from semantic_check.actions)
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d")" 0
expect "engagement and funnel vs gold.customer_engagement_daily (rows differing)" "$(engagement_vs_gold)" 0
# 2026-10-01: S-0005's cart after midnight and the late S-0006 both convert (4 of 5 page views); E-0001,
# eleven days before, is an engaged customer over 28 days and not over 7.
expect "the funnel and engaged customers on 2026-10-01 and 2026-10-03" "$(psql_dev -c "
  select string_agg(round(view_to_cart_rate, 2) || ' ' || engaged_customers_7d || ' ' || engaged_customers_28d, ', ' order by day)
  from semantic_check.engagement where day in ('2026-10-01', '2026-10-03')")" "0.80 6 7, 0.33 9 10"
echo "ok: the customer-actions metrics equal gold.customer_actions_daily and gold.customer_engagement_daily"

# Partner outreach (SL-16): the message and reply metrics by day against gold.partner_outreach_daily, the
# reply rate over the whole fixture, and the activation list the automation reads. C-0102 opted out on
# 2026-10-02 and a backfill loaded last carries their older snapshot: silver keeps the opt-out.
mf_ query --metrics messages_sent,messages_replied,replies,partners_engaged,reply_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/outreach.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the outreach metrics"; }
mf_ query --metrics messages_sent,messages_replied,reply_rate --group-by partner__partner_type \
  --order partner__partner_type --csv "$OUT/outreach_type.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the outreach metrics by partner type"; }
mf_ query --metrics reply_rate --csv "$OUT/outreach_period.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of the reply rate over the fixture"; }
psql_dev -c "set client_min_messages = warning" -c "drop table if exists semantic_check.outreach" \
  -c "create table semantic_check.outreach (day date, messages_sent bigint, messages_replied bigint, replies bigint, partners_engaged bigint, reply_rate numeric)"
psql_dev -c "\\copy semantic_check.outreach from stdin with (format csv, header true)" <"$OUT/outreach.csv"
expect "outreach metrics vs gold.partner_outreach_daily (rows differing)" "$(psql_dev -c "
  with gold as (select outreach_date, messages_sent, messages_replied, replies, partners_engaged, round(reply_rate, 6) from gold.partner_outreach_daily),
       mf as (select day, coalesce(messages_sent, 0), coalesce(messages_replied, 0), coalesce(replies, 0), coalesce(partners_engaged, 0),
                     round(reply_rate, 6) from semantic_check.outreach)
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d")" 0
# Over the fixture 4 of 7 messages got a reply: 0.57, not 0.54, the average of the daily rates.
expect "the fixture's reply rate" "$(tail -n +2 "$OUT/outreach_period.csv" | cut -c1-4)" "0.57"
expect "the average of gold's daily reply rates (what the metric is not)" "$(psql_dev -c "
  select round(avg(reply_rate), 2) from gold.partner_outreach_daily")" "0.54"
expect "messages sent and replied by partner type" "$(tail -n +2 "$OUT/outreach_type.csv" | cut -d, -f1-3 | paste -sd ' ')" "agency,2,2 clinic,3,2 reseller,2,0"
expect "the activation list" "$(psql_dev -c "select string_agg(contact_id, ' ' order by contact_id) from exposed.outreach_activation")" "C-0103 C-0301"
expect "C-0102 after a backfill of an older snapshot" "$(psql_dev -c "
  select opted_out_ts || ' ' || reachable from silver.partner_contacts where contact_id = 'C-0102'")" "2026-10-02 15:00:00+00 false"
echo "ok: the outreach metrics equal gold.partner_outreach_daily; the reply rate is 0.57 over the fixture; the activation list leaves out no-consent, opted-out and recently contacted contacts"

# Recruitment (SL-17): the source keeps only each candidate's current stage, so the stage history is the
# snapshot's. The fixture's build above snapshotted once, after every extract had landed; replay the extracts
# one at a time in load order with a build after each, as recruitment_elt would, from an empty snapshot.
psql_dev -c "set client_min_messages = warning" -c "drop table if exists semantic_check.applications" \
  -c "create table semantic_check.applications as select * from ds_source.synthetic_applications" \
  -c "truncate ds_source.synthetic_applications" -c "drop table silver.candidate_stage_snapshots cascade"
for run in run-rec-1 run-rec-2 run-rec-3 run-rec-1b run-rec-4; do
  psql_dev -c "insert into ds_source.synthetic_applications select * from semantic_check.applications where _run_id = '$run'"
  dbt_ build --select tag:recruitment >"$OUT/recruitment-$run.log" 2>&1 ||
    { tail -30 "$OUT/recruitment-$run.log" >&2; fail "dbt build tag:recruitment after $run"; }
done
expect "recruitment hops after the last extract" "$(grep -c " PASS hop_" "$OUT/recruitment-run-rec-4.log")" 7
expect "the stage history" "$(psql_dev -c "
  select string_agg(candidate_id || ':' || stage || '@' || to_char(valid_from_date, 'MM-DD'), ' ' order by candidate_id, valid_from)
  from silver.candidate_stages")" \
  "K-001:interview@09-30 K-001:offer@10-02 K-001:hired@10-03 K-002:screen@10-01 K-002:interview@10-02 K-002:rejected@10-04 K-003:applied@10-01 K-003:screen@10-02 K-003:interview@10-03 K-004:applied@10-02 K-004:screen@10-04 K-005:offer@09-30 K-005:hired@10-02 K-006:screen@10-01 K-006:rejected@10-02"
mf_ query --metrics applications,hires,time_to_hire_days --group-by metric_time__day --order metric_time__day \
  --csv "$OUT/recruitment.csv" >>"$OUT/query.log" 2>&1 || { cat "$OUT/query.log" >&2; fail "mf query of the recruitment metrics"; }
mf_ query --metrics candidates_in_stage --group-by metric_time__day,candidate__stage \
  --order metric_time__day,candidate__stage --csv "$OUT/in_stage.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of candidates_in_stage by candidate__stage"; }
mf_ query --metrics candidates_in_stage --group-by metric_time__day --where "{{ Dimension('candidate__stage') }} = 'interview'" \
  --where "{{ TimeDimension('metric_time', 'day') }} between '2026-10-01' and '2026-10-04'" --order metric_time__day \
  --csv "$OUT/in_interview.csv" >>"$OUT/query.log" 2>&1 || { cat "$OUT/query.log" >&2; fail "mf query of candidates in interview"; }
mf_ query --metrics time_to_hire_days --csv "$OUT/time_to_hire.csv" >>"$OUT/query.log" 2>&1 ||
  { cat "$OUT/query.log" >&2; fail "mf query of time to hire over the fixture"; }
psql_dev -c "set client_min_messages = warning" -c "drop table if exists semantic_check.recruitment" \
  -c "create table semantic_check.recruitment (day date, applications bigint, hires bigint, time_to_hire_days numeric)" \
  -c "drop table if exists semantic_check.in_stage" -c "create table semantic_check.in_stage (day date, stage text, candidates bigint)"
psql_dev -c "\\copy semantic_check.recruitment from stdin with (format csv, header true)" <"$OUT/recruitment.csv"
psql_dev -c "\\copy semantic_check.in_stage from stdin with (format csv, header true)" <"$OUT/in_stage.csv"
expect "recruitment metrics vs gold.recruitment_daily (rows differing)" "$(psql_dev -c "
  with gold as (select recruitment_date, applications, hires, round(time_to_hire_days, 4) from gold.recruitment_daily),
       mf as (select day, coalesce(applications, 0), coalesce(hires, 0), round(time_to_hire_days, 4) from semantic_check.recruitment)
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d")" 0
# MetricFlow joins each candidate-day to the stage valid on it (validity_params); a day before a candidate's first
# snapshot has no stage, which gold leaves out and MetricFlow groups under an empty stage.
expect "candidates_in_stage by stage vs gold.candidates_in_stage_daily (rows differing)" "$(psql_dev -c "
  with gold as (select stage_date, stage, candidates from gold.candidates_in_stage_daily),
       mf as (select day, stage, candidates from semantic_check.in_stage where stage is not null)
  select count(*) from ((select * from gold except select * from mf) union all (select * from mf except select * from gold)) d")" 0
expect "candidates in interview at the end of 1 to 4 October" "$(tail -n +2 "$OUT/in_interview.csv" | tr -d '\r' | cut -d, -f2 | paste -sd ' ')" "1 1 2 1"
expect "time to hire over the fixture (K-005 7.2083 and K-001 4.9583 days)" "$(tail -n +2 "$OUT/time_to_hire.csv" | cut -c1-4)" "6.08"
echo "ok: replayed extract by extract, the snapshot keeps every stage change and no backfill moves a candidate back; the recruitment metrics equal gold.recruitment_daily, candidates_in_stage by stage equals gold.candidates_in_stage_daily, 2 in interview on 3 October"

# Incremental silver (SL-15): a later load brings an action that happened on 2026-10-01 and redelivers
# E-0021; the build merges only that load, the late action lands on its own day, E-0021 stays one row,
# and every hop still passes. A full refresh afterwards restores the fixture's silver.
psql_dev -c "insert into ds_source.synthetic_customer_actions values
  ('E-0022', 10, 'S-0011', 'page_view', 'site', '2026-10-01 12:00+00', '2026-10-04 06:00+00', 'run-act-5', '2026-10-04 00:00+00', '2026-10-05 00:00+00', 1, 'fixture://customer_actions', '2026-10-05 00:30+00'),
  ('E-0021', 3, 'S-0010', 'page_view', 'site', '2026-10-03 18:00+00', '2026-10-03 18:00+00', 'run-act-5', '2026-10-04 00:00+00', '2026-10-05 00:00+00', 1, 'fixture://customer_actions', '2026-10-05 00:30+00')"
late_ok=0
dbt_ build --select tag:customer_actions >"$OUT/incremental.log" 2>&1 && late_ok=1
late_state=$(psql_dev -c "select count(*) || ' ' || count(distinct event_id) || ' ' ||
  (select event_date from silver.customer_actions where event_id = 'E-0022') || ' ' ||
  (select _run_id from silver.customer_actions where event_id = 'E-0021') from silver.customer_actions")
late_rate=$(psql_dev -c "select round(view_to_cart_rate, 2) from gold.customer_engagement_daily where activity_date = '2026-10-01'")
psql_dev -c "delete from ds_source.synthetic_customer_actions where _run_id = 'run-act-5'"
[ "$late_ok" = 1 ] || { grep " FAIL \| ERROR " "$OUT/incremental.log" >&2; fail "the incremental build after a late load"; }
# A merge, not a rebuild: the 72-hour lookback before silver's newest load (run-act-4) re-reads runs 2 to 4
# (20 events) and the new load adds E-0022; run-act-1's E-0001 is not read again.
grep -Eq "incremental model silver.customer_actions .*MERGE 21" "$OUT/incremental.log" ||
  { grep "silver.customer_actions" "$OUT/incremental.log" >&2; fail "silver.customer_actions did not merge the 21 events of the lookback"; }
expect "silver after the late load: rows, distinct events, E-0022's day, E-0021's run" "$late_state" "22 22 2026-10-01 run-act-5"
expect "2026-10-01's view-to-cart rate with the late page view" "$late_rate" "0.67"
expect "hops after the late load" "$(grep -c " PASS hop_" "$OUT/incremental.log")" 11
dbt_ build --select tag:customer_actions --full-refresh >"$OUT/incremental.log" 2>&1 ||
  { tail -30 "$OUT/incremental.log" >&2; fail "full refresh of the customer-actions models"; }
expect "silver after the full refresh" "$(psql_dev -c "select count(*) from silver.customer_actions")" 21
echo "ok: an incremental build merges a late action into 2026-10-01 and a redelivered one once, every hop passing"

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
echo "select 1 as stray_id, 'a@b.example' as stray_email" >"$stray_model"
cat >"$stray" <<'YAML'
version: 2
models:
  - name: zz_semantic_check_stray
    columns:
      - name: stray_id
      - name: stray_email
        config:
          meta: {pii: true}
metrics:
  - name: zz_stray_orders
    label: Stray
    type: derived
    expr: orders_total
    input_metrics: [orders_total]
  - name: zz_stray_objections
    description: Calls with an objection, said as if a system had recorded them.
    label: Stray objections
    type: derived
    expr: calls_with_objection
    input_metrics: [calls_with_objection]
YAML
if make -s -C "$REPO" dbt-validate DBT_DBNAME="$DB" >"$OUT/stray.log" 2>&1; then fail "dbt-validate passed off the standard"; fi
for problem in "metric zz_stray_orders: no description" \
  'metric zz_stray_objections: reads a model-derived column, so its description starts with "Model-derived"' \
  "model zz_semantic_check_stray: in gold, so its name starts with gld_" \
  "public model zz_semantic_check_stray: no description" \
  "public model zz_semantic_check_stray: column stray_id has no description" \
  "public model zz_semantic_check_stray: column stray_id has no data_type" \
  "model zz_semantic_check_stray: public with personal data in stray_email; make it protected"; do
  grep -qF "check_standard: $problem" "$OUT/stray.log" ||
    { tail -20 "$OUT/stray.log" >&2; fail "the validation failed, but not on: $problem"; }
done
rm -f "$stray" "$stray_model"
echo "ok: an undescribed metric, a metric over model-derived labels not saying so, and an unprefixed, undescribed, untyped gold model with personal data fail make dbt-validate"

echo "PASS: semantic check"
