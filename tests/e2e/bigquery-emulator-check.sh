#!/usr/bin/env bash
# BigQuery emulator check (issue #125, semantic/PLAN.md SL-7): the semantic path runs on a BigQuery
# engine, not only compiles for one. On an empty emulator (Compose profile `bigquery`) it
#   - copies the dev fixture's sources from Postgres dbt_dev into the emulator,
#   - runs `dbt build` of the sales, returns, finance and semantic models, tests included, on the
#     `bigquery_emulator` target, with the project unchanged,
#   - queries the eight metrics by day through MetricFlow on the emulator, and asserts they equal
#     the hand-written gold.daily_sales and exposed.net_sales_daily the same build wrote there.
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

run_ dbt build --select tag:sales tag:returns tag:finance tag:semantic --exclude tag:tlc >"$OUT/build.log" 2>&1 ||
  { grep -E "ERROR|Error" "$OUT/build.log" | tail -20 >&2; fail "dbt build on the emulator"; }
summary=$(grep -o "PASS=[0-9]* WARN=[0-9]* ERROR=[0-9]* SKIP=[0-9]*" "$OUT/build.log" | tail -1)
echo "ok: dbt build on the emulator: $summary"

run_ mf query --metrics orders_total,orders_cancelled,revenue_eur,customers_distinct,cancellation_rate \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/sales.csv" >"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the order metrics on the emulator"; }
run_ mf query --metrics revenue_eur,returns_eur,returns_count,net_revenue_eur \
  --group-by metric_time__day --order metric_time__day --csv "$OUT/net.csv" >>"$OUT/query.log" 2>&1 ||
  { tail -20 "$OUT/query.log" >&2; fail "mf query of the net revenue metrics on the emulator"; }

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
    return round(decimal.Decimal(str(v)), 6)

def rows(sql):
    return {str(r[0]): tuple(num(v) for v in r[1:]) for r in client.query(sql).result()}

def metrics(name, columns):
    with open(f"{out}/{name}.csv") as f:
        return {r["metric_time__day"][:10]: tuple(num(r[c]) for c in columns) for r in csv.DictReader(f)}

sales = ["orders_total", "orders_cancelled", "revenue_eur", "customers_distinct", "cancellation_rate"]
net = ["revenue_eur", "returns_eur", "returns_count", "net_revenue_eur"]
gold = rows("select order_date, orders_total, orders_cancelled, revenue_eur, customers_distinct,"
            " orders_cancelled / orders_total from `pplk8s-lab.gold.daily_sales`")
exposed = rows("select order_date, revenue_eur, returns_eur, returns_count, net_revenue_eur"
               " from `pplk8s-lab.exposed.net_sales_daily`")
bad = []
for label, oracle, got in (("gold.daily_sales", gold, metrics("sales", sales)),
                           ("exposed.net_sales_daily", exposed, metrics("net", net))):
    if len(oracle) < 2:
        bad.append(f"{label} has {len(oracle)} days; the fixture gives at least 2")
    bad += [f"{label} {day}: metrics {got.get(day)} != {oracle.get(day)}"
            for day in sorted(set(oracle) | set(got)) if got.get(day) != oracle.get(day)]
print("\n".join(bad) or f"ok: the eight metrics equal gold.daily_sales and exposed.net_sales_daily on {len(gold)} days, on the emulator")
sys.exit(1 if bad else 0)
EOF

echo "PASS: BigQuery emulator check"
