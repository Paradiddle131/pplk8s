#!/usr/bin/env bash
# BigQuery emulator check (issue #125, semantic/PLAN.md SL-7): the semantic path runs on a BigQuery
# engine, not only compiles for one. On an empty emulator (Compose profile `bigquery`) it
#   - copies the dev fixture's sources from Postgres dbt_dev into the emulator,
#   - runs `dbt build` of the sales, returns, finance, marketing and semantic models, tests
#     included, on the `bigquery_emulator` target, with the project unchanged; the 51 layer hops
#     (semantic/PLAN.md SL-9) among them reconcile there,
#   - queries the metrics through MetricFlow on the emulator, and asserts they equal the
#     hand-written aggregates the same build wrote there: the eight sales metrics by day against
#     gold.daily_sales and exposed.net_sales_daily, the marketing metrics by day and channel against
#     gold.marketing_daily, and the fixture's cost per lead and per booking (39.00, 130.00); the
#     customer-actions metrics (actions per type, engaged customers over 7 and 28 days, the site funnel)
#     against gold.customer_actions_daily and gold.customer_engagement_daily (SL-15); the outreach
#     metrics against gold.partner_outreach_daily and the activation list (SL-16).
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

# A fresh emulator: it keeps everything in memory, so recreating it empties it.
"${COMPOSE[@]}" up -d --force-recreate --wait bigquery bigquery-api >/dev/null 2>&1 ||
  { "${COMPOSE[@]}" logs --tail 20 bigquery bigquery-api >&2; fail "the emulator did not come up"; }
echo "ok: BigQuery emulator up on $ENDPOINT (empty)"

psql_dev -c "select 1" >/dev/null 2>&1 || "${COMPOSE[@]}" exec -T warehouse createdb -U warehouse "$DB"
psql_dev <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
rm -rf "$OUT" && mkdir -p "$PROJECT_DIR"
# A copy of dbt/, because MetricFlow reads <project>/target whatever DBT_TARGET_PATH says.
(cd "$REPO/dbt" && tar --exclude=./target --exclude=./logs -cf - .) | tar -xf - -C "$PROJECT_DIR"
run_ --with 'psycopg[binary]==3.3.6' python -I scripts/fixture_to_bigquery.py \
  "host=localhost port=5433 user=warehouse password=warehouse dbname=$DB" "$ENDPOINT" pplk8s-lab ||
  fail "copying the fixture into the emulator"
echo "ok: fixture sources copied into the emulator"

run_ dbt build --select tag:sales tag:returns tag:finance tag:marketing tag:customer_actions tag:partner_outreach tag:recruitment tag:semantic tag:migration --exclude tag:tlc >"$OUT/build.log" 2>&1 ||
  { grep -E "ERROR|Error" "$OUT/build.log" | tail -20 >&2; fail "dbt build on the emulator"; }
summary=$(grep -o "PASS=[0-9]* WARN=[0-9]* ERROR=[0-9]* SKIP=[0-9]*" "$OUT/build.log" | tail -1)
echo "ok: dbt build on the emulator: $summary"
hops=$(grep -c " PASS hop_" "$OUT/build.log" || true)
[ "$hops" -eq 51 ] || fail "expected the 51 layer hops to pass on the emulator, got $hops"
echo "ok: the 51 layer hops reconcile on the emulator (semantic/PLAN.md SL-9)"
grep -q " PASS consumers_switch_on_parity " "$OUT/build.log" || fail "the migration gate did not pass on the emulator"

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
                           ("gold.partner_outreach_daily", gold_outreach, mf_outreach)):
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
      f" gold.partner_outreach_daily on {len(gold_outreach)} days with the activation list, and migration.parity"
      " reports as on Postgres, on the emulator")
sys.exit(1 if bad else 0)
EOF

echo "PASS: BigQuery emulator check"
