#!/usr/bin/env bash
# BigQuery emulator check (issue #125, semantic/PLAN.md SL-7): the semantic path runs on a BigQuery
# engine, not only compiles for one. On an empty emulator (Compose profile `bigquery`) it
#   - copies the dev fixture's sources from Postgres dbt_dev into the emulator,
#   - runs `dbt build` of the sales, returns, finance, marketing, call-transcripts and semantic models,
#     tests included, on the `bigquery_emulator` target, with the project unchanged; the 61 layer hops
#     (semantic/PLAN.md SL-9) among them reconcile there,
#   - queries the metrics through MetricFlow on the emulator, and asserts they equal the
#     hand-written aggregates the same build wrote there: the eight sales metrics by day against
#     gold.daily_sales and exposed.net_sales_daily, the marketing metrics by day and channel against
#     gold.marketing_daily, and the fixture's cost per lead and per booking (39.00, 130.00); the
#     customer-actions metrics (actions per type, engaged customers over 7 and 28 days, the site funnel)
#     against gold.customer_actions_daily and gold.customer_engagement_daily (SL-15); the outreach
#     metrics against gold.partner_outreach_daily and the activation list (SL-16); the call metrics by
#     day and topic against gold.call_signals_daily, labelled from the recorded label calls (the
#     emulator fakes AI.CLASSIFY and lacks AI.GENERATE) and scored there on the golden set (SL-18).
#   - asserts the recruitment metrics and candidates_in_stage by stage (MetricFlow's SCD join) against gold, after
#     one snapshot of every extract; then, on a recreated emulator, replays the extracts one at a time with a build
#     after each, as semantic-check does on Postgres, and asserts the stage history the snapshot kept (SL-17),
#   - builds the migration rehearsal there too (semantic/PLAN.md SL-11): migration.parity holds the
#     same report as on Postgres, and the gate on each consumer's switch passes the lab's state.
#   - creates the semantic agent's audit table there with the same entry point as on Postgres
#     (`dbt run-operation agent_warehouse`, #166), twice, and writes and reads back one row.
# Expects `make services-up` (the fixture loads through the Postgres warehouse); never touches the
# `warehouse` database. The emulator stays up afterwards on localhost:9050 (`docker compose
# --profile bigquery down` in platform/compose stops it).
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

# A fresh emulator holding the fixture's sources: recreating the container empties its database file.
fresh_emulator_() {
  "${COMPOSE[@]}" up -d --force-recreate --wait bigquery bigquery-api >/dev/null 2>&1 ||
    { "${COMPOSE[@]}" logs --tail 20 bigquery bigquery-api >&2; fail "the emulator did not come up"; }
  echo "ok: BigQuery emulator up on $ENDPOINT (empty)"
  run_ --with 'psycopg[binary]==3.3.6' python -I scripts/fixture_to_bigquery.py \
    "host=localhost port=5433 user=warehouse password=warehouse dbname=$DB" "$ENDPOINT" pplk8s-lab >"$OUT/fixture.log" ||
    { cat "$OUT/fixture.log" >&2; fail "copying the fixture into the emulator"; }
  echo "ok: fixture sources copied into the emulator"
}
# The emulator's memory grows with every statement, and past about 5 GiB a DROP TABLE panics inside its engine
# (googlesqlite: slice bounds out of range [-2147...:], #246). It keeps its data in a file in its own container
# (compose.yaml), so a restart frees the memory and keeps the tables; a recreate empties it.
# The shim stays healthy across the restart, so wait for the emulator itself to answer through it.
restart_emulator_() {
  "${COMPOSE[@]}" restart bigquery >/dev/null 2>&1 || fail "restarting the emulator"
  for _ in $(seq 60); do
    curl -sf "$ENDPOINT/bigquery/v2/projects/pplk8s-lab/datasets" >/dev/null && return 0
    sleep 1
  done
  "${COMPOSE[@]}" logs --tail 20 bigquery bigquery-api >&2
  fail "the emulator did not answer within 60 s of a restart"
}

psql_dev -c "select 1" >/dev/null 2>&1 || "${COMPOSE[@]}" exec -T warehouse createdb -U warehouse "$DB"
psql_dev <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
rm -rf "$OUT" && mkdir -p "$PROJECT_DIR"
# A copy of dbt/, because MetricFlow reads <project>/target whatever DBT_TARGET_PATH says.
(cd "$REPO/dbt" && tar --exclude=./target --exclude=./logs -cf - .) | tar -xf - -C "$PROJECT_DIR"
fresh_emulator_

# The build in two halves with a restart between, as one build of every domain outgrows the emulator's memory:
# the platform's pipelines and the semantic and migration models, then the newer domains, which read only
# their own sources and the time spine.
run_ dbt build --select tag:sales tag:returns tag:finance tag:marketing tag:semantic tag:migration --exclude tag:tlc >"$OUT/build.log" 2>&1 ||
  { grep -E "ERROR|Error" "$OUT/build.log" | tail -20 >&2; fail "dbt build of sales, returns, finance, marketing, semantic and migration on the emulator"; }
summary=$(grep -o "PASS=[0-9]* WARN=[0-9]* ERROR=[0-9]* SKIP=[0-9]*" "$OUT/build.log" | tail -1)
restart_emulator_
run_ dbt build --select tag:customer_actions tag:partner_outreach tag:recruitment tag:call_transcripts --exclude tag:tlc >"$OUT/build-domains.log" 2>&1 ||
  { grep -E "ERROR|Error" "$OUT/build-domains.log" | tail -20 >&2; fail "dbt build of customer actions, partner outreach, recruitment and call transcripts on the emulator"; }
summary="$summary, then $(grep -o "PASS=[0-9]* WARN=[0-9]* ERROR=[0-9]* SKIP=[0-9]*" "$OUT/build-domains.log" | tail -1)"
cat "$OUT/build-domains.log" >>"$OUT/build.log"
restart_emulator_
echo "ok: dbt build on the emulator, in two halves with a restart between: $summary"
hops=$(grep -c " PASS hop_" "$OUT/build.log" || true)
[ "$hops" -eq 61 ] || fail "expected the 61 layer hops to pass on the emulator, got $hops"
echo "ok: the 61 layer hops reconcile on the emulator (semantic/PLAN.md SL-9)"
grep -q " PASS consumers_switch_on_parity " "$OUT/build.log" || fail "the migration gate did not pass on the emulator"
grep -q " PASS call_labels_agree_with_golden_set " "$OUT/build.log" || fail "the call labels' agreement test did not pass on the emulator"

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
  --group-by metric_time__day --order metric_time__day --csv "$OUT/sales.csv" >"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the order metrics on the emulator"; }
run_ mf query --metrics revenue_eur,returns_eur,returns_count,net_revenue_eur \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/net.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the net revenue metrics on the emulator"; }
run_ mf query --metrics ad_spend_eur,ad_clicks,leads,bookings,booking_value_eur \
  --group-by metric_time__day,campaign__channel --order metric_time__day --csv "$OUT/marketing.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the marketing metrics on the emulator"; }
run_ mf query --metrics cost_per_lead_eur,cost_per_booking_eur --csv "$OUT/marketing_period.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the marketing ratios on the emulator"; }
run_ mf query --metrics customer_actions --group-by metric_time__day,customer_action__action_type \
  --order metric_time__day --csv "$OUT/actions.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the actions per type on the emulator"; }
run_ mf query --metrics engaged_customers_7d,engaged_customers_28d,site_sessions,cart_sessions,checkout_sessions,view_to_cart_rate,cart_to_checkout_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/engagement.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the engagement and funnel metrics on the emulator"; }
run_ mf query --metrics messages_sent,messages_replied,replies,partners_engaged,reply_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/outreach.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the outreach metrics on the emulator"; }
run_ mf query --metrics calls_labelled,calls_with_objection,positive_calls \
  --group-by metric_time__day,call__topic --order metric_time__day --csv "$OUT/calls.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the call metrics on the emulator"; }

# Parity on the emulator itself: each metric by day against the hand-written aggregate, both ways.
run_ python -I - "$ENDPOINT" "$OUT" <<'EOF' || fail "metrics differ from gold and exposed on the emulator"
import csv, decimal, sys
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

endpoint, out = sys.argv[1:3]
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

sales = ["orders_total", "orders_cancelled", "revenue_eur", "customers_distinct", "cancellation_rate"]
net = ["revenue_eur", "returns_eur", "returns_count", "net_revenue_eur"]
gold = rows("select order_date, orders_total, orders_cancelled, revenue_eur, customers_distinct,"
            " orders_cancelled / orders_total from `pplk8s-lab.gold.daily_sales`")
exposed = rows("select order_date, revenue_eur, returns_eur, returns_count, net_revenue_eur"
               " from `pplk8s-lab.exposed.net_sales_daily`")
marketing = ["ad_spend_eur", "ad_clicks", "leads", "bookings", "booking_value_eur"]
gold_marketing = {k.replace(" ", "|"): v for k, v in rows(
    "select concat(cast(activity_date as string), ' ', channel), ad_spend_eur, ad_clicks, leads, bookings,"
    " booking_value_eur from `pplk8s-lab.gold.marketing_daily`").items()}
actions = {k.replace(" ", "|"): v for k, v in rows(
    "select concat(cast(activity_date as string), ' ', action_type), actions"
    " from `pplk8s-lab.gold.customer_actions_daily`").items()}
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
    bad_activation = [f"exposed.outreach_activation on the emulator: {activation} != ['C-0103', 'C-0301']"]
else:
    bad_activation = []
bad = bad_activation
calls = ["calls_labelled", "calls_with_objection", "positive_calls"]
gold_calls = {k.replace(" ", "|"): v for k, v in rows(
    "select concat(cast(call_date as string), ' ', topic), calls_labelled, calls_with_objection, positive_calls"
    " from `pplk8s-lab.gold.call_signals_daily`").items()}
labelled = list(client.query("select count(*) from `pplk8s-lab.silver.call_signals`").result())[0][0]
if labelled != 12:
    bad.append(f"silver.call_signals on the emulator holds {labelled} calls, not the fixture's 12")
with open(f"{out}/marketing_period.csv") as f:
    period = next(csv.DictReader(f))
got = (round(decimal.Decimal(period["cost_per_lead_eur"]), 2), round(decimal.Decimal(period["cost_per_booking_eur"]), 2))
if got != (decimal.Decimal("39.00"), decimal.Decimal("130.00")):
    bad.append(f"cost per lead and per booking over the fixture: {got} != (39.00, 130.00)")
for label, oracle, got in (("gold.daily_sales", gold, metrics("sales", sales)),
                           ("exposed.net_sales_daily", exposed, metrics("net", net)),
                           ("gold.marketing_daily", gold_marketing,
                            metrics("marketing", marketing, ("metric_time__day", "campaign__channel"))),
                           ("gold.customer_actions_daily", actions,
                            metrics("actions", ["customer_actions"], ("metric_time__day", "customer_action__action_type"))),
                           ("gold.customer_engagement_daily", gold_engagement, mf_engagement),
                           ("gold.partner_outreach_daily", gold_outreach, mf_outreach),
                           ("gold.call_signals_daily", gold_calls,
                            metrics("calls", calls, ("metric_time__day", "call__topic")))):
    if len(oracle) < 2:
        bad.append(f"{label} has {len(oracle)} days; the fixture gives at least 2")
    bad += [f"{label} {day}: metrics {got.get(day)} != {oracle.get(day)}"
            for day in sorted(set(oracle) | set(got)) if got.get(day) != oracle.get(day)]
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
print("\n".join(bad) or f"ok: the sales metrics equal gold.daily_sales and exposed.net_sales_daily on {len(gold)} days,"
      f" the marketing metrics gold.marketing_daily on {len(gold_marketing)} day-channels, the customer-actions"
      f" metrics the customer-actions gold on {len(gold_engagement)} days, the outreach metrics"
      f" gold.partner_outreach_daily on {len(gold_outreach)} days with the activation list, the call metrics"
      f" gold.call_signals_daily on {len(gold_calls)} day-topics, and migration.parity"
      " reports as on Postgres, on the emulator")
sys.exit(1 if bad else 0)
EOF

# Recruitment (SL-17): the build above snapshotted every extract at once, so the history holds each candidate's newest
# stage; the metrics against their gold oracles. The replay extract by extract comes after, on a recreated emulator.
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

# The replay, as semantic-check runs it on Postgres: the extracts land one at a time in load order with a build of the
# recruitment path after each, so the snapshot's MERGE and its staging table's DROP run on the emulator. It needs an
# emulator of its own: the emulator's memory grows with every statement (about 5 GiB after the build above), and past
# that a DROP TABLE panics inside the engine (googlesqlite: slice bounds out of range [-2147...:]) and the client
# retries it until the run is killed. The extracts wait in a file and go back in through the streaming insert.
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

echo "PASS: BigQuery emulator check"
