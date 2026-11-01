#!/usr/bin/env bash
# Migration rehearsal check (semantic/PLAN.md SL-11): host dbt builds the legacy tables, the new
# layers they are replaced by and migration.parity on dbt/dev/fixture.sql in dbt_dev, and asserts that
#   - the parity report matches every field of the finance dashboard and the marketing automation, and
#     finds the sales agent's revenue different (legacy counts cancelled orders),
#   - the gate (test consumers_switch_on_parity) passes the lab's state: the dashboard switched,
#     the agent and the automation still on legacy,
#   - switching the agent fails the build on its revenue, and passes once its owner accepts the
#     difference; switching the automation before the agent fails on the order,
#   - rolling the dashboard back to legacy passes.
# The switches are made in a copy of dbt/, so the tree is never edited.
# Expects `make services-up`; never touches the `warehouse` database.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/dbt-deps.sh
source "$REPO/tests/e2e/lib/dbt-deps.sh"
dbt_deps "$REPO/dbt"
DB=dbt_dev
OUT=${TMPDIR:-/tmp}/pplk8s-migration-check
COPY="$OUT/dbt"
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_dev() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"
}
export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB"
dbt_in() { local dir=$1; shift; (cd "$dir" && DBT_PROFILES_DIR="$dir" uvx --quiet --with-requirements requirements-postgres.txt --from dbt-core dbt "$@"); }
expect() { [ "$2" = "$3" ] || fail "$1: expected [$3], got [$2]"; }

rm -rf "$OUT" && mkdir -p "$OUT"
psql_dev -c "select 1" >/dev/null 2>&1 || docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse createdb -U warehouse "$DB"
psql_dev <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
echo "ok: fixture loaded into $DB"

dbt_in "$REPO/dbt" build --select +tag:migration --exclude tag:tlc >"$OUT/build.log" 2>&1 ||
  { tail -30 "$OUT/build.log" >&2; fail "dbt build +tag:migration"; }
grep -q " PASS consumers_switch_on_parity " "$OUT/build.log" || fail "the gate did not pass the lab's state"
echo "ok: legacy tables, new layers and migration.parity built; the gate passes the lab's state"

expect "parity report" "$(psql_dev -c "
  select string_agg(consumer || ' ' || field || ' ' || keys_compared || ' ' || keys_differing || ' ' || status, '; '
                    order by consumer, field) from migration.parity")" \
  "finance_dashboard gross_revenue 2 0 match; finance_dashboard net_revenue 2 0 match; finance_dashboard returns_amount 2 0 match; finance_dashboard row_count 2 0 match; marketing_automation bookings 6 0 match; marketing_automation cost_per_booking 6 0 match; marketing_automation cost_per_lead 6 0 match; marketing_automation leads 6 0 match; marketing_automation row_count 6 0 match; marketing_automation spend 6 0 match; sales_agent orders 12 0 match; sales_agent revenue 12 4 differs; sales_agent row_count 12 0 match"
# The four keys are exactly the country-days with a cancelled order: legacy's revenue counts them.
expect "the sales agent's differing keys" "$(psql_dev -c "
  select count(distinct (o.order_date, c.country)) from silver.orders o join silver.customers c using (customer_id)
  where o.status = 'cancelled'")" 4
echo "ok: migration.parity matches the dashboard and the automation; the agent's revenue differs on the 4 country-days with a cancellation"

# Each case edits the consumers in a fresh copy of dbt/ and runs the gate alone; failing rows are stored.
(cd "$REPO/dbt" && tar --exclude=./target --exclude=./logs --exclude=./dbt_packages -cf - .) | tar -xf - -C "$(mkdir -p "$COPY" && echo "$COPY")"
dbt_deps "$COPY"
gate() { # <case name> <python statement over `s`, the text of consumers.yml>
  local name=$1 edit=$2
  cp "$REPO/dbt/models/migration/consumers.yml" "$COPY/models/migration/consumers.yml"
  python3 -I - "$COPY/models/migration/consumers.yml" "$edit" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(); before = s
exec(sys.argv[2])
assert s != before, "the edit changed nothing"
p.write_text(s)
PY
  dbt_in "$COPY" test --select consumers_switch_on_parity --store-failures >"$OUT/$name.log" 2>&1
}
problems() { psql_dev -c "select string_agg(consumer || ': ' || problem, '; ' order by consumer, problem) from dbt_test__audit.consumers_switch_on_parity"; }
switch_agent="s = s.replace(\"depends_on: [ref('lgc_country_sales')]\", \"depends_on: [ref('exp_sales_by_country_daily')]\")"

gate agent_switched "$switch_agent" && fail "the gate passed the agent switched with its revenue differing"
expect "problems with the agent switched" "$(problems)" "sales_agent: revenue differs on 4 keys, not accepted"
echo "ok: switching the agent fails the gate on its revenue"

accept="s = s.replace('new: exp_sales_by_country_daily}', 'new: exp_sales_by_country_daily, accepted: {revenue: legacy counted cancelled orders}}')"
gate agent_accepted "$switch_agent; $accept" || { tail -20 "$OUT/agent_accepted.log" >&2; fail "the gate refused the agent with its difference accepted"; }
echo "ok: with the difference accepted on its exposure, the agent's switch passes"

gate automation_first "s = s.replace(\"depends_on: [ref('lgc_channel_daily')]\", \"depends_on: [ref('exp_channel_performance_daily')]\")" &&
  fail "the gate passed the automation switched before the agent"
expect "problems with the automation first" "$(problems)" "marketing_automation: switched before agent sales_agent"
echo "ok: switching the automation before the agent fails the gate on the order"

gate dashboard_rolled_back "s = s.replace(\"depends_on: [ref('exp_net_sales_daily')]\", \"depends_on: [ref('lgc_daily_net_sales')]\")" ||
  { tail -20 "$OUT/dashboard_rolled_back.log" >&2; fail "the gate refused rolling the dashboard back"; }
echo "ok: rolling the dashboard back to legacy passes"

echo "PASS: migration check"
