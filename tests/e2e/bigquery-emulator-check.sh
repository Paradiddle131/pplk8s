#!/usr/bin/env bash
# BigQuery emulator check (issue #125, semantic/PLAN.md SL-7): the semantic path runs on a BigQuery
# engine, not only compiles for one. The emulator rebuilds its whole catalog on every DROP TABLE, and every
# query job leaves a result table behind, so one emulator holding every domain's build overflows its engine
# (googlesqlite: slice bounds out of range [-2147...:], #246). Each part therefore runs on a fresh emulator
# (Compose profile `bigquery`) holding the dev fixture's sources, copied from Postgres dbt_dev:
#   - recruitment, replayed: the extracts one at a time with a build after each, as semantic-check does on
#     Postgres, and the stage history the snapshot kept (SL-17); then built once over every extract, its metrics
#     and candidates_in_stage by stage (MetricFlow's SCD join) against gold,
#   - customer actions: actions per type, engaged customers over 7 and 28 days and the site funnel against
#     gold.customer_actions_daily and gold.customer_engagement_daily (SL-15),
#   - partner outreach: the outreach metrics against gold.partner_outreach_daily, and the activation list (SL-16),
#   - call transcripts: the call metrics by day and topic against gold.call_signals_daily, labelled from the
#     recorded label calls (the emulator fakes AI.CLASSIFY and lacks AI.GENERATE) and scored there on the golden
#     set (SL-18),
#   - last, the platform: sales, returns, finance, marketing, the semantic and migration models; the eight sales
#     metrics by day against gold.daily_sales and exposed.net_sales_daily, net revenue by day and customer country
#     and revenue by weekday (a date part, ISO) against SQL by hand, signups, customers to date and the
#     signup-to-first-order rate by month against SQL by hand, the marketing metrics by day and channel
#     against gold.marketing_daily, the fixture's cost per lead and per booking (39.00, 130.00), migration.parity
#     as on Postgres with the gate on each consumer's switch (SL-11), and the agent's audit table through the same
#     entry point as on Postgres (`dbt run-operation agent_warehouse`, #166), twice, with one row written and read.
# Every part runs `dbt build` with its tests on the `bigquery_emulator` target, the project unchanged; the 62
# layer hops (semantic/PLAN.md SL-9) reconcile across them.
# Expects `make services-up` (the fixture loads through the Postgres warehouse); never touches the
# `warehouse` database. The emulator stays up afterwards on localhost:9050, holding the platform's build, which
# `make demo` reads (`docker compose --profile bigquery down` in platform/compose stops it).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_dev
OUT=${TMPDIR:-/tmp}/pplk8s-bigquery-emulator-check
PROJECT_DIR="$OUT/dbt"
ENDPOINT=http://localhost:9050
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml" --profile bigquery)
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_dev() { "${COMPOSE[@]}" exec -T warehouse psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"; }

# The image's pins plus the BigQuery adapter, as in bigquery-check.sh.
DBT_BIGQUERY=dbt-bigquery==1.12.1
export DBT_TARGET=bigquery_emulator DBT_PROFILES_DIR="$PROJECT_DIR" BQ_API_ENDPOINT="$ENDPOINT"
run_() { (cd "$PROJECT_DIR" && uv run --quiet --no-project --with-requirements requirements.txt --with "$DBT_BIGQUERY" "$@"); }

# A fresh emulator holding the fixture's sources: it keeps everything in memory, so recreating it empties it.
fresh_emulator_() {
  "${COMPOSE[@]}" up -d --force-recreate --wait bigquery bigquery-api >/dev/null 2>&1 ||
    { "${COMPOSE[@]}" logs --tail 20 bigquery bigquery-api >&2; fail "the emulator did not come up"; }
  echo "ok: BigQuery emulator up on $ENDPOINT (empty)"
  run_ --with 'psycopg[binary]==3.3.6' python -I scripts/fixture_to_bigquery.py \
    "host=localhost port=5433 user=warehouse password=warehouse dbname=$DB" "$ENDPOINT" pplk8s-lab >"$OUT/fixture.log" ||
    { cat "$OUT/fixture.log" >&2; fail "copying the fixture into the emulator"; }
  echo "ok: fixture sources copied into the emulator"
}
psql_dev -c "select 1" >/dev/null 2>&1 || "${COMPOSE[@]}" exec -T warehouse createdb -U warehouse "$DB"
psql_dev <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
rm -rf "$OUT" && mkdir -p "$PROJECT_DIR"
# A copy of dbt/, because MetricFlow reads <project>/target whatever DBT_TARGET_PATH says.
(cd "$REPO/dbt" && tar --exclude=./target --exclude=./logs -cf - .) | tar -xf - -C "$PROJECT_DIR"
# One part on a fresh emulator: dbt build of the tags given, its log appended to build.log for the hop count.
build_part_() {
  local part=$1
  shift
  fresh_emulator_
  run_ dbt build --select "$@" --exclude tag:tlc >"$OUT/build-$part.log" 2>&1 ||
    { grep -E "ERROR|Error" "$OUT/build-$part.log" | tail -20 >&2; fail "dbt build of $part on the emulator"; }
  cat "$OUT/build-$part.log" >>"$OUT/build.log"
  echo "ok: $part built on the emulator: $(grep -o "PASS=[0-9]* WARN=[0-9]* ERROR=[0-9]* SKIP=[0-9]*" "$OUT/build-$part.log" | tail -1)"
}
bq_() {
  run_ python -I - "$ENDPOINT" "$@" <<'EOF'
import sys
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

client = bigquery.Client(project="pplk8s-lab", credentials=AnonymousCredentials(),
                         client_options=ClientOptions(api_endpoint=sys.argv[1]))
for sql in sys.argv[2:]:
    for row in client.query(sql).result():
        print(" ".join("" if v is None else str(v) for v in row))
EOF
}

# Parity on the emulator itself: each metric by day against the hand-written aggregate, both ways, for the part
# the emulator holds (platform, customer_actions, partner_outreach or call_transcripts).
parity_() {
  run_ python -I - "$ENDPOINT" "$OUT" "$1" <<'EOF' || fail "$1: metrics differ from their gold and exposed oracles on the emulator"
import csv, decimal, sys
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

endpoint, out, part = sys.argv[1:4]
client = bigquery.Client(project="pplk8s-lab", credentials=AnonymousCredentials(),
                         client_options=ClientOptions(api_endpoint=endpoint))

def num(v):
    return None if v is None or v == "" else round(decimal.Decimal(str(v)), 6)

def rows(sql):
    return {str(r[0]): tuple(num(v) for v in r[1:]) for r in client.query(sql).result()}

def metrics(name, columns, keys=("metric_time__day",)):
    with open(f"{out}/{name}.csv") as f:
        return {"|".join(r[k][:10] if k.startswith("metric_time") else r[k] for k in keys): tuple(num(r[c] or 0) for c in columns)
                for r in csv.DictReader(f)}

def keyed(sql):
    return {k.replace(" ", "|"): v for k, v in rows(sql).items()}

bad, compared, said = [], [], ""
if part == "platform":
    sales = ["orders_total", "orders_cancelled", "revenue_eur", "customers_distinct", "cancellation_rate"]
    net = ["revenue_eur", "returns_eur", "returns_count", "net_revenue_eur"]
    gold = rows("select order_date, orders_total, orders_cancelled, revenue_eur, customers_distinct,"
                " orders_cancelled / orders_total from `pplk8s-lab.gold.daily_sales`")
    exposed = rows("select order_date, revenue_eur, returns_eur, returns_count, net_revenue_eur"
                   " from `pplk8s-lab.exposed.net_sales_daily`")
    marketing = ["ad_spend_eur", "ad_clicks", "leads", "bookings", "booking_value_eur"]
    gold_marketing = keyed("select concat(cast(activity_date as string), ' ', channel), ad_spend_eur, ad_clicks, leads,"
                           " bookings, booking_value_eur from `pplk8s-lab.gold.marketing_daily`")
    with open(f"{out}/marketing_period.csv") as f:
        period = next(csv.DictReader(f))
    got = (round(decimal.Decimal(period["cost_per_lead_eur"]), 2), round(decimal.Decimal(period["cost_per_booking_eur"]), 2))
    if got != (decimal.Decimal("39.00"), decimal.Decimal("130.00")):
        bad.append(f"cost per lead and per booking over the fixture: {got} != (39.00, 130.00)")
    # Net revenue by customer country (returns reach the customer through their order), against SQL by hand.
    by_country = keyed("""
        with sold as (select o.order_date as day, c.country, sum(o.amount) as revenue
                      from `pplk8s-lab.silver.orders` o join `pplk8s-lab.silver.customers` c on c.customer_id = o.customer_id
                      where o.status <> 'cancelled' group by 1, 2),
             returned as (select r.return_date as day, c.country, sum(r.amount) as returned
                          from `pplk8s-lab.silver.returns` r join `pplk8s-lab.silver.orders` o on o.order_id = r.order_id
                          join `pplk8s-lab.silver.customers` c on c.customer_id = o.customer_id group by 1, 2),
             days as (select day, country from sold union distinct select day, country from returned)
        select concat(cast(d.day as string), ' ', d.country), coalesce(s.revenue, 0), coalesce(r.returned, 0),
               coalesce(s.revenue, 0) - coalesce(r.returned, 0)
        from days d left join sold s on s.day = d.day and s.country = d.country
        left join returned r on r.day = d.day and r.country = d.country""")
    # Revenue by weekday as query_metrics groups by it (a date part, ISO: 1 Monday); BigQuery's own DAYOFWEEK
    # starts on Sunday, so SQL by hand shifts it.
    weekday = rows("select cast(mod(extract(dayofweek from order_date) + 5, 7) + 1 as string), sum(revenue_eur)"
                   " from `pplk8s-lab.gold.daily_sales` group by 1")
    with open(f"{out}/dow.csv") as f:
        by_weekday = {str(int(float(r["metric_time__extract_dow"]))): (num(r["revenue_eur"]),) for r in csv.DictReader(f)}
    # Customers' own metrics by month over the base fixture's 2024 signups (none orders within 30 days).
    customers = rows("""
        select cast(month as string), countif(date_trunc(c.signup_date, month) = month),
               countif(c.signup_date < date_add(month, interval 1 month)), 0
        from unnest(generate_date_array(date '2024-01-01', date '2024-12-01', interval 1 month)) as month
        cross join `pplk8s-lab.silver.customers` c group by month""")
    compared = [("gold.daily_sales", gold, metrics("sales", sales)),
                ("customers by month (SQL by hand)", customers,
                 metrics("customers", ["signups", "customers_to_date", "signup_to_first_order_rate"], ("metric_time__month",))),
                ("revenue by weekday (ISO)", weekday, by_weekday),
                ("exposed.net_sales_daily", exposed, metrics("net", net)),
                ("net revenue by customer country (SQL by hand)", by_country,
                 metrics("net_country", ["revenue_eur", "returns_eur", "net_revenue_eur"], ("metric_time__day", "customer__country"))),
                ("gold.marketing_daily", gold_marketing,
                 metrics("marketing", marketing, ("metric_time__day", "campaign__channel")))]
    # The migration rehearsal's report, as tests/e2e/migration-check.sh asserts it on Postgres.
    parity = "; ".join(" ".join(str(v) for v in r) for r in client.query(
        "select consumer, field, keys_compared, keys_differing, status from `pplk8s-lab.migration.parity`"
        " order by consumer, field").result())
    expected = ("finance_dashboard gross_revenue 2 0 match; finance_dashboard net_revenue 2 0 match; "
                "finance_dashboard returns_amount 2 0 match; finance_dashboard row_count 2 0 match; "
                "marketing_automation bookings 6 0 match; marketing_automation cost_per_booking 6 0 match; "
                "marketing_automation cost_per_lead 6 0 match; marketing_automation leads 6 0 match; "
                "marketing_automation row_count 6 0 match; marketing_automation spend 6 0 match; "
                "sales_agent orders 12 0 match; sales_agent revenue 12 4 differs; sales_agent row_count 12 0 match")
    if parity != expected:
        bad.append(f"migration.parity on the emulator: {parity}")
    said = (f"the sales metrics equal gold.daily_sales and exposed.net_sales_daily on {len(gold)} days, net revenue"
            f" by customer country SQL by hand on {len(by_country)} day-countries, revenue by weekday on"
            f" {len(weekday)} weekdays, the customers' metrics on {len(customers)} months, the marketing"
            f" metrics gold.marketing_daily on {len(gold_marketing)} day-channels, and migration.parity reports as on Postgres")
elif part == "customer_actions":
    actions = keyed("select concat(cast(activity_date as string), ' ', action_type), actions"
                    " from `pplk8s-lab.gold.customer_actions_daily`")
    engagement_columns = ["engaged_customers_7d", "engaged_customers_28d", "site_sessions", "cart_sessions",
                          "checkout_sessions", "view_to_cart_rate", "cart_to_checkout_rate"]
    gold_engagement = rows("select activity_date, " + ", ".join(engagement_columns)
                           + " from `pplk8s-lab.gold.customer_engagement_daily`")
    # A cumulative metric also has rows for the days after the data; compare on gold's days. A count is
    # NULL in MetricFlow where gold says 0; a rate is NULL on both sides without its base step.
    with open(f"{out}/engagement.csv") as f:
        mf_engagement = {r["metric_time__day"][:10]: tuple(
            num(r[c] or (None if c.endswith("_rate") else 0)) for c in engagement_columns) for r in csv.DictReader(f)}
    mf_engagement = {day: v for day, v in mf_engagement.items() if day in gold_engagement}
    compared = [("gold.customer_actions_daily", actions,
                 metrics("actions", ["customer_actions"], ("metric_time__day", "customer_action__action_type"))),
                ("gold.customer_engagement_daily", gold_engagement, mf_engagement)]
    said = f"the customer-actions metrics equal the customer-actions gold on {len(gold_engagement)} days"
elif part == "partner_outreach":
    outreach_columns = ["messages_sent", "messages_replied", "replies", "partners_engaged", "reply_rate"]
    gold_outreach = rows("select outreach_date, " + ", ".join(outreach_columns)
                         + " from `pplk8s-lab.gold.partner_outreach_daily`")
    # The reply rate is NULL on both sides on a day without messages; a count is NULL in MetricFlow where gold says 0.
    with open(f"{out}/outreach.csv") as f:
        mf_outreach = {r["metric_time__day"][:10]: tuple(
            num(r[c] or (None if c == "reply_rate" else 0)) for c in outreach_columns) for r in csv.DictReader(f)}
    activation = [r[0] for r in client.query(
        "select contact_id from `pplk8s-lab.exposed.outreach_activation` order by contact_id").result()]
    if activation != ["C-0103", "C-0301"]:
        bad.append(f"exposed.outreach_activation on the emulator: {activation} != ['C-0103', 'C-0301']")
    compared = [("gold.partner_outreach_daily", gold_outreach, mf_outreach)]
    said = f"the outreach metrics equal gold.partner_outreach_daily on {len(gold_outreach)} days, with the activation list"
elif part == "call_transcripts":
    calls = ["calls_labelled", "calls_with_objection", "positive_calls"]
    gold_calls = keyed("select concat(cast(call_date as string), ' ', topic), calls_labelled, calls_with_objection,"
                       " positive_calls from `pplk8s-lab.gold.call_signals_daily`")
    labelled = list(client.query("select count(*) from `pplk8s-lab.silver.call_signals`").result())[0][0]
    if labelled != 52:
        bad.append(f"silver.call_signals on the emulator holds {labelled} calls, not the fixture's 52")
    compared = [("gold.call_signals_daily", gold_calls, metrics("calls", calls, ("metric_time__day", "call__topic")))]
    said = f"the call metrics equal gold.call_signals_daily on {len(gold_calls)} day-topics"
else:
    sys.exit(f"unknown part {part}")
for label, oracle, got in compared:
    if len(oracle) < 2:
        bad.append(f"{label} has {len(oracle)} days; the fixture gives at least 2")
    bad += [f"{label} {day}: metrics {got.get(day)} != {oracle.get(day)}"
            for day in sorted(set(oracle) | set(got)) if got.get(day) != oracle.get(day)]
print("\n".join(bad) or f"ok: {said}, on the emulator")
sys.exit(1 if bad else 0)
EOF
}

# Recruitment, replayed: the extracts land one at a time in load order with a build of the recruitment path after
# each, so the snapshot's MERGE and its staging table's DROP run on the emulator. The extracts wait in a file and
# go back in through the streaming insert.
fresh_emulator_
load_run_() {
  run_ python -I - "$ENDPOINT" "$OUT/applications.json" "$1" <<'EOF' || fail "loading $1 into the emulator"
import json
import sys
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

client = bigquery.Client(project="pplk8s-lab", credentials=AnonymousCredentials(),
                         client_options=ClientOptions(api_endpoint=sys.argv[1]))
table = "pplk8s-lab.ds_source.synthetic_applications"
if sys.argv[3] == "run-rec-1":
    rows = [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}
            for row in client.query(f"select * from `{table}`").result()]
    assert len(rows) == 28, len(rows)
    json.dump(rows, open(sys.argv[2], "w"))
    client.query(f"delete from `{table}` where true").result()
rows = [row for row in json.load(open(sys.argv[2])) if row["_run_id"] == sys.argv[3]]
assert rows and not client.insert_rows_json(table, rows)
EOF
}
for run in run-rec-1 run-rec-2 run-rec-3 run-rec-1b run-rec-4; do
  load_run_ "$run"
  run_ dbt build --select tag:recruitment >"$OUT/recruitment-$run.log" 2>&1 ||
    { grep -E "ERROR|Error" "$OUT/recruitment-$run.log" | tail -20 >&2; fail "dbt build tag:recruitment after $run on the emulator"; }
done
hops=$(grep -c " PASS hop_" "$OUT/recruitment-run-rec-4.log" || true)
[ "$hops" -eq 7 ] || fail "expected the 7 recruitment hops to pass after the last extract on the emulator, got $hops"
history=$(bq_ "select string_agg(concat(candidate_id, ':', stage, '@', format_date('%m-%d', valid_from_date)), ' '
  order by candidate_id, valid_from) from silver.candidate_stages")
[ "$history" = "K-001:interview@09-30 K-001:offer@10-02 K-001:hired@10-03 K-002:screen@10-01 K-002:interview@10-02 K-002:rejected@10-04 K-003:applied@10-01 K-003:screen@10-02 K-003:interview@10-03 K-004:applied@10-02 K-004:screen@10-04 K-005:offer@09-30 K-005:hired@10-02 K-006:screen@10-01 K-006:rejected@10-02" ] ||
  fail "the stage history replayed on the emulator: $history"
in_interview=$(bq_ "select candidates from gold.candidates_in_stage_daily where stage = 'interview' and stage_date = date '2026-10-03'")
[ "$in_interview" = 2 ] || fail "candidates in interview on 3 October after the replay on the emulator: $in_interview, expected 2"
echo "ok: replayed extract by extract on a recreated emulator, the snapshot keeps every stage change and no backfill moves a candidate back; 2 in interview on 3 October"

# Recruitment built once over every extract: the history holds each candidate's newest stage; the metrics against
# their gold oracles.
build_part_ recruitment tag:recruitment
run_ mf query --metrics candidates_in_stage --group-by metric_time__day,candidate__stage \
  --order metric_time__day,candidate__stage --csv "$OUT/in_stage.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of candidates_in_stage by stage on the emulator"; }
run_ mf query --metrics applications,hires,time_to_hire_days --group-by metric_time__day --order metric_time__day \
  --csv "$OUT/recruitment.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the recruitment metrics on the emulator"; }
# A day before a candidate's first snapshot has no stage: gold leaves it out, MetricFlow groups it under none.
mf_in_stage=$(tail -n +2 "$OUT/in_stage.csv" | tr -d '\r' | awk -F, '$2 != "" {print substr($1, 1, 10) "," $2 "," $3}' | sort | paste -sd ' ')
gold_in_stage=$(bq_ "select string_agg(concat(cast(stage_date as string), ',', stage, ',', cast(candidates as string)), ' '
  order by cast(stage_date as string), stage) from gold.candidates_in_stage_daily")
[ -n "$gold_in_stage" ] && [ "$mf_in_stage" = "$gold_in_stage" ] ||
  fail "candidates_in_stage by stage on the emulator [$mf_in_stage] != gold.candidates_in_stage_daily [$gold_in_stage]"
mf_recruitment=$(tail -n +2 "$OUT/recruitment.csv" | tr -d '\r' |
  awk -F, '{printf "%s,%d,%d,%s\n", substr($1, 1, 10), $2, $3, ($4 == "" ? "" : sprintf("%.4f", $4))}' | sort | paste -sd ' ')
gold_recruitment=$(bq_ "select string_agg(concat(cast(recruitment_date as string), ',', cast(applications as string), ',',
  cast(hires as string), ',', coalesce(format('%.4f', cast(time_to_hire_days as float64)), '')), ' ' order by recruitment_date)
  from gold.recruitment_daily")
[ "$mf_recruitment" = "$gold_recruitment" ] ||
  fail "the recruitment metrics on the emulator [$mf_recruitment] != gold.recruitment_daily [$gold_recruitment]"
echo "ok: the snapshot builds on the emulator; candidates_in_stage by stage equals gold.candidates_in_stage_daily and the recruitment metrics gold.recruitment_daily"

# The time spine is tagged sales; the cumulative metrics need it.
build_part_ customer_actions tag:customer_actions metricflow_time_spine
run_ mf query --metrics customer_actions --group-by metric_time__day,customer_action__action_type \
  --order metric_time__day --csv "$OUT/actions.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the actions per type on the emulator"; }
run_ mf query --metrics engaged_customers_7d,engaged_customers_28d,site_sessions,cart_sessions,checkout_sessions,view_to_cart_rate,cart_to_checkout_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/engagement.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the engagement and funnel metrics on the emulator"; }
parity_ customer_actions

build_part_ partner_outreach tag:partner_outreach
run_ mf query --metrics messages_sent,messages_replied,replies,partners_engaged,reply_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/outreach.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the outreach metrics on the emulator"; }
parity_ partner_outreach

build_part_ call_transcripts tag:call_transcripts
grep -q " PASS call_labels_agree_with_golden_set " "$OUT/build-call_transcripts.log" || fail "the call labels' agreement test did not pass on the emulator"
run_ mf query --metrics calls_labelled,calls_with_objection,positive_calls \
  --group-by metric_time__day,call__topic --order metric_time__day --csv "$OUT/calls.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the call metrics on the emulator"; }

parity_ call_transcripts

# The platform last, so the emulator left running holds what `make demo` reads.
build_part_ platform tag:sales tag:returns tag:finance tag:marketing tag:semantic tag:migration
grep -q " PASS consumers_switch_on_parity " "$OUT/build-platform.log" || fail "the migration gate did not pass on the emulator"
# The agent's warehouse objects through the same macro as on Postgres; a second run changes nothing.
for _ in 1 2; do
  run_ dbt run-operation agent_warehouse >"$OUT/agent-warehouse.log" 2>&1 ||
    { tail -20 "$OUT/agent-warehouse.log" >&2; fail "dbt run-operation agent_warehouse on the emulator"; }
done
run_ python -I - "$ENDPOINT" <<'EOF' || fail "ops.agent_queries on the emulator"
import sys
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

client = bigquery.Client(project="pplk8s-lab", credentials=AnonymousCredentials(),
                         client_options=ClientOptions(api_endpoint=sys.argv[1]))
table = "`pplk8s-lab.ops.agent_queries`"
client.query(f"insert into {table} (called_at, agent, tool, metrics, arguments, rows_returned)"
             " values (current_timestamp(), 'semantic_agent', 'query_metrics', ['orders_total'], json '{}', 1)").result()
rows = [(r[0], list(r[1]), r[2]) for r in client.query(f"select agent, metrics, called_at is not null from {table}").result()]
assert rows == [("semantic_agent", ["orders_total"], True)], rows
EOF
echo "ok: the agent_warehouse macro created ops.agent_queries on the emulator; a row writes and reads back"

run_ mf query --metrics orders_total,orders_cancelled,revenue_eur,customers_distinct,cancellation_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/sales.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the order metrics on the emulator"; }
run_ mf query --metrics revenue_eur,returns_eur,returns_count,net_revenue_eur \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/net.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the net revenue metrics on the emulator"; }
run_ mf query --metrics revenue_eur,returns_eur,net_revenue_eur --group-by metric_time__day,customer__country \
  --csv "$OUT/net_country.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of net revenue by customer country on the emulator"; }
run_ mf query --metrics signups,customers_to_date,signup_to_first_order_rate --group-by metric_time__month \
  --start-time 2024-01-01 --end-time 2024-12-31 --csv "$OUT/customers.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the customers' metrics on the emulator"; }
run_ python -I "$REPO/tests/e2e/lib/mf_date_part.py" revenue_eur dow 2026-09-28 2026-10-04 "$OUT/dow.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "MetricFlow query of revenue by weekday on the emulator"; }
run_ mf query --metrics ad_spend_eur,ad_clicks,leads,bookings,booking_value_eur \
  --group-by metric_time__day,campaign__channel --order metric_time__day --csv "$OUT/marketing.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the marketing metrics on the emulator"; }
run_ mf query --metrics cost_per_lead_eur,cost_per_booking_eur --csv "$OUT/marketing_period.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the marketing ratios on the emulator"; }
parity_ platform

# The recruitment replay's builds are not counted: the build over every extract holds the same hops.
hops=$(grep -c " PASS hop_" "$OUT/build.log" || true)
[ "$hops" -eq 62 ] || fail "expected the 62 layer hops to pass on the emulator, got $hops"
echo "ok: the 62 layer hops reconcile on the emulator (semantic/PLAN.md SL-9)"

echo "PASS: BigQuery emulator check"
