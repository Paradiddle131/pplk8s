#!/usr/bin/env bash
# The use case's demo (docs/demo.md, semantic/PLAN.md U1-U6), one step per call: `make demo STEP=<step>`
# prints what the presenter points at and fails when it differs from the script; `make demo-check`
# rehearses every step in order on a fresh lab and prints each step's time.
#   setup      the BigQuery emulator built by `make bigquery-emulator-check`, and the agents' fixture
#              in the Compose warehouse's dbt_dev (tests/e2e/agent-fixture.sh)
#   layers     U1/U6: the layers' tables on the emulator, cost per lead and per booking queried there
#   standard   U2: the documentation standard's check, and the descriptions BigQuery holds
#   agent      U4: the semantic agent answers through query_metrics, with its freshness (scripted model,
#              no quota; `make agent-web` is the live surface)
#   alerts     U3: a stopped source fails dbt source freshness and reaches SourceStale's exporter; a
#              number changed in gold fails the build's layer hops on the emulator, then is rebuilt
#   audit      U4: the agent's call in ops.agent_queries
#   migration  U5: migration.parity on the emulator, per consumer and field
# The emulator keeps its data in memory and `make bigquery-emulator-check` recreates it, so `setup`
# comes first after the emulator restarts. Never touches the `warehouse` database.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
STEPS=(layers standard agent alerts audit migration)
DB=dbt_dev
ENDPOINT=http://localhost:9050
# bigquery-run-check.sh's copy of dbt/ (MetricFlow reads <project>/target), built for the emulator.
PROJECT_DIR=${TMPDIR:-/tmp}/pplk8s-bigquery-run-check-emulator/dbt
OUT=${TMPDIR:-/tmp}/pplk8s-demo
DBT_BIGQUERY=dbt-bigquery==1.12.1 # bigquery-run-check.sh's
fail() { echo "FAIL: $*" >&2; exit 1; }
say() { printf '\n== %s\n' "$*"; }
psql_dev() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"
}
on_emulator() {
  [ -f "$PROJECT_DIR/target/manifest.json" ] || fail "no emulator build: run make demo STEP=setup"
  (cd "$PROJECT_DIR" && DBT_USE_COLORS=false DBT_TARGET=bigquery_emulator DBT_PROFILES_DIR="$PROJECT_DIR" BQ_API_ENDPOINT="$ENDPOINT" \
    uv run --quiet --no-project --with-requirements requirements.txt --with "$DBT_BIGQUERY" "$@")
}
# Aligns the columns of stdin or of the files named after the separator $1 (column(1) is not
# everywhere, e.g. the cloud sandbox).
table() {
  awk -F"$1" '{ for (i = 1; i <= NF; i++) { cell[NR, i] = $i; if (length($i) > w[i]) w[i] = length($i) } if (NF > n) n = NF }
    END { for (r = 1; r <= NR; r++) { line = ""; for (i = 1; i <= n; i++) line = line sprintf("%-" w[i] "s  ", cell[r, i]); sub(/ +$/, "", line); print line } }' "${@:2}"
}
bq() { on_emulator python -I "$REPO/tests/e2e/lib/bigquery_emulator.py" "$ENDPOINT" "$@"; }
mkdir -p "$OUT"

setup() {
  make -s -C "$REPO" bigquery-emulator-check >"$OUT/emulator.log" 2>&1 || { tail -20 "$OUT/emulator.log" >&2; fail "make bigquery-emulator-check"; }
  grep -E '^ok: dbt build|^PASS' "$OUT/emulator.log"
  DB=$DB "$REPO/tests/e2e/agent-fixture.sh" | grep -v '^$'
}

layers() {
  say "The layers on BigQuery (emulator): dataset, tables, names"
  bq tables | tee "$OUT/tables.tsv" | table $'\t'
  for layer in bronze silver gold exposed semantic; do
    grep -q "^$layer"$'\t' "$OUT/tables.tsv" || fail "no $layer dataset on the emulator"
  done
  say "One calculated field, defined once (dbt/models/semantic/semantic.yml), queried on BigQuery"
  on_emulator mf query --metrics cost_per_lead_eur,cost_per_booking_eur --group-by campaign__channel \
    --order campaign__channel --csv "$OUT/cost_by_channel.csv" >"$OUT/mf.log" 2>&1 || { tail -20 "$OUT/mf.log" >&2; fail "mf query on the emulator"; }
  table , "$OUT/cost_by_channel.csv"
  on_emulator mf query --metrics cost_per_lead_eur,cost_per_booking_eur --csv "$OUT/cost.csv" >"$OUT/mf.log" 2>&1 ||
    { tail -20 "$OUT/mf.log" >&2; fail "mf query on the emulator"; }
  table , "$OUT/cost.csv"
  [ "$(tail -1 "$OUT/cost.csv" | awk -F, '{ printf "%.2f %.2f", $1, $2 }')" = "39.00 130.00" ] ||
    fail "expected cost per lead 39.00 and per booking 130.00 over the fixture, got $(tail -1 "$OUT/cost.csv")"
}

standard() {
  say "The agent-ready standard (docs/agent-ready-warehouse.md), checked on the BigQuery build's manifest"
  (cd "$PROJECT_DIR" && python3 scripts/check_standard.py target) || fail "the standard's check"
  say "What BigQuery holds for an agent to read: gold.daily_sales"
  bq columns gold.daily_sales | tee "$OUT/columns.tsv" | table $'\t'
  grep -q $'^revenue_eur\tNUMERIC\tSum of amount for non-cancelled orders.$' "$OUT/columns.tsv" ||
    fail "gold.daily_sales.revenue_eur has no description on the emulator"
  ! cut -f3 "$OUT/columns.tsv" | grep -qx '' || fail "a column of gold.daily_sales has no description on the emulator"
}

agent() {
  say "The semantic agent: one turn, a scripted model, the real tools as agent_metrics on $DB"
  (cd "$REPO/services/semantic-agent" && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" \
    DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics SEMANTIC_CATALOG="$REPO/dbt/target/catalog/agent.json" \
    uv run --quiet python - "$OUT/turn.json") <<'EOF' || fail "the agent's turn"
import json, sys
from semantic_agent.agent import build_agent
from tests.conftest import ScriptedLlm, final_text, run_turn

model = ScriptedLlm(steps=[
    ("query_metrics", {"metrics": ["net_revenue_eur"], "start_date": "2026-10-01", "end_date": "2026-10-01"}),
    "Net revenue was 964.19 EUR on 1 October 2026.",
])
events = run_turn(build_agent(model), "What was net revenue on 1 October 2026, after partner returns?")
(result,) = model.tool_results()
json.dump({"answer": final_text(events), "invocation": events[-1].invocation_id, "response": result["response"]},
          open(sys.argv[1], "w"), default=str)
EOF
  rows=$(jq -c '.response.rows' "$OUT/turn.json")
  statement=$(jq -r '.response.freshness.statement' "$OUT/turn.json")
  echo "question: What was net revenue on 1 October 2026, after partner returns?"
  echo "query_metrics: $rows"
  echo "freshness: $statement"
  [ "$(jq -r '.response.error // empty' "$OUT/turn.json")" = "" ] || fail "query_metrics answered an error: $(jq -r .response.error "$OUT/turn.json")"
  [ "$rows" = '[{"net_revenue_eur":964.19}]' ] || fail "expected net revenue 964.19, got $rows"
  [[ "$statement" == *"Late: sales.silver"* ]] || fail "expected the answer to say sales.silver is late, got: $statement"
  jq -r .invocation "$OUT/turn.json" >"$OUT/invocation"
  echo "live: make agent-web AGENT_DBNAME=$DB, then http://localhost:8000 (docs/demo.md)"
}

alerts() {
  say "A source stops flowing: dbt source freshness, its verdict exported for SourceStale"
  make -s -C "$REPO" source-freshness-check >"$OUT/freshness.log" 2>&1 || { tail -20 "$OUT/freshness.log" >&2; fail "make source-freshness-check"; }
  grep -E '^ok: ' "$OUT/freshness.log"
  # promtool exits non-zero when any rule test fails, SourceStale's among them.
  make -s -C "$REPO" rules-test >"$OUT/rules.log" 2>&1 || { tail -20 "$OUT/rules.log" >&2; fail "make rules-test"; }
  echo "ok: make rules-test: SourceStale fires on the exported verdict (tests/monitoring/source-freshness.test.yaml)"

  say "A number changes in gold (a hand edit, a broken job): the next build's layer hops fail on BigQuery"
  # Gold's own hops fail; exposed is a view over gold, so gold to exposed agrees and passes.
  local failing="hop_silver_to_gold_marketing_daily hop_metric_ad_spend_eur_to_gld_marketing_daily"
  local hops="$failing hop_gold_to_exposed_channel_performance_daily"
  bq sql "update \`pplk8s-lab.gold.marketing_daily\` set ad_spend_eur = ad_spend_eur + 10
    where activity_date = '2026-10-01' and channel = 'search'" >/dev/null || fail "changing gold.marketing_daily on the emulator"
  # shellcheck disable=SC2086 # one test name per word
  if on_emulator dbt test --select $hops >"$OUT/hops.log" 2>&1; then fail "the hops passed a changed gold.marketing_daily"; fi
  grep -E ' (FAIL|PASS) [0-9]+ hop_| (FAIL|PASS) hop_' "$OUT/hops.log" | sed -E 's/^[0-9:]+ +//'
  for hop in $failing; do
    grep -qE " FAIL [0-9]+ $hop " "$OUT/hops.log" || { tail -20 "$OUT/hops.log" >&2; fail "$hop did not fail"; }
  done
  grep -qE " PASS hop_gold_to_exposed_channel_performance_daily " "$OUT/hops.log" ||
    { tail -20 "$OUT/hops.log" >&2; fail "hop_gold_to_exposed_channel_performance_daily did not pass"; }
  local compiled
  compiled=$(find "$PROJECT_DIR/target/compiled" -name hop_silver_to_gold_marketing_daily.sql | head -1)
  echo "the mismatching key, as the hop returns it:"
  bq sql "$(cat "$compiled")" | table $'\t'
  on_emulator dbt build --select gld_marketing_daily+ --exclude tag:tlc >"$OUT/rebuild.log" 2>&1 ||
    { tail -20 "$OUT/rebuild.log" >&2; fail "rebuilding gold.marketing_daily on the emulator"; }
  # shellcheck disable=SC2086
  on_emulator dbt test --select $hops >"$OUT/hops.log" 2>&1 || { tail -20 "$OUT/hops.log" >&2; fail "the hops after the rebuild"; }
  echo "ok: rebuilt from silver, the three hops pass again"
}

audit() {
  say "Every agent call leaves a row: ops.agent_queries on $DB, newest first"
  psql_dev -F' | ' -c "select called_at::timestamp(0), agent, tool, metrics, rows_returned, freshness
    from ops.agent_queries order by called_at desc limit 3"
  [ -f "$OUT/invocation" ] || fail "no agent turn to look for: run make demo STEP=agent"
  [ "$(psql_dev -c "select count(*) from ops.agent_queries where invocation_id = '$(cat "$OUT/invocation")'
    and agent = 'semantic_agent' and tool = 'query_metrics' and metrics = array['net_revenue_eur']")" = 1 ] ||
    fail "the agent's turn left no audit row"
  echo "ok: the agent's turn is in the audit log; the same table builds on BigQuery (make bigquery-emulator-check)"
}

migration() {
  say "Migration: each consumer's old table against its new model, on BigQuery (docs/migration-rehearsal.md)"
  bq sql "select consumer, field, keys_compared, keys_differing, status from \`pplk8s-lab.migration.parity\`
    order by consumer, field" | tee "$OUT/parity.tsv" | table $'\t'
  grep -q $'^sales_agent\trevenue\t12\t4\tdiffers$' "$OUT/parity.tsv" || fail "expected sales_agent revenue to differ on 4 of 12 keys"
  [ "$(grep -c $'\tmatch$' "$OUT/parity.tsv")" = 12 ] || fail "expected the other 12 fields to match"
  echo "ok: finance_dashboard switched; sales_agent waits for its owner to accept 4 revenue differences; marketing_automation waits for the agent"
}

check() {
  local step start took timings="" total=0
  for step in setup "${STEPS[@]}"; do
    start=$(date +%s)
    "$step"
    took=$(($(date +%s) - start))
    total=$((total + took))
    timings+="$step"$'\t'"${took}s"$'\n'
  done
  # The live agent (`make agent-web`, step 3) reads dbt/target after every other step has run, so ask again:
  # a step that reparses dbt/target against another database fails here, not in front of the audience.
  start=$(date +%s)
  agent >/dev/null
  echo "ok: the agent answers again after every step, from the dbt/target make agent-web reads"
  took=$(($(date +%s) - start))
  total=$((total + took))
  timings+="agent again"$'\t'"${took}s"$'\n'
  say "Rehearsal timings"
  printf '%s' "$timings" | table $'\t'
  echo "total ${total}s"
  echo "PASS: demo check"
}

case "${1:-}" in
  setup | layers | standard | agent | alerts | audit | migration | check) "$1" ;;
  *) fail "usage: $0 setup|$(IFS='|'; echo "${STEPS[*]}")|check" ;;
esac
