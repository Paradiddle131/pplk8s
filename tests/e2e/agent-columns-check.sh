#!/usr/bin/env bash
# Personal data by column (semantic/PLAN.md SL-22): the columns marked meta.pii (the partner contacts' name,
# email and phone) are refused to every agent role and read by the outreach automation, whichever of
# `make agent-warehouse` and `dbt build` runs first and however often. On a new, empty database of the Compose
# Postgres it
#   - runs `make agent-warehouse` before any model exists, builds the partner-outreach models on
#     dbt/dev/fixture.sql (their post-hook sets the column grants), and asserts the grants;
#   - runs `make agent-warehouse` again (its schema-wide grants re-grant every table) and asserts again;
#   - rebuilds the models (a new relation, default privileges again) and asserts again.
# The assertions log in as each role: agent_metrics reads silver.partner_contacts but not its personal columns
# (`select *` included), agent_sql reads exposed.outreach_activation but not its personal columns, and
# outreach_automation reads the activation list's emails.
# Expects `make services-up`; drops and recreates only the database agent_columns.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/dbt-deps.sh
source "$REPO/tests/e2e/lib/dbt-deps.sh"
dbt_deps "$REPO/dbt"
DB=agent_columns
OUT=${TMPDIR:-/tmp}/pplk8s-agent-columns
fail() { echo "FAIL: $*" >&2; exit 1; }
compose() { docker compose -f "$REPO/platform/compose/compose.yaml" "$@"; }
psql_db() { compose exec -T warehouse psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt; }
# A query as a lab role, logged in with its password over TCP, as the agents connect.
as_role() {
  compose exec -T -e PGPASSWORD="$1" warehouse \
    psql -h 127.0.0.1 -U "$1" -d "$DB" -v ON_ERROR_STOP=1 -qAt -c "$2" 2>&1
}
expect() { [ "$2" = "$3" ] || fail "$1: got '$2', expected '$3'"; }
refused() {
  local got
  if got=$(as_role "$1" "$2"); then fail "$1 read personal data: $2 returned '$got'"; fi
  case "$got" in *"permission denied"*) ;; *) fail "$1: $2 failed, but not on a permission: $got" ;; esac
}
build() {
  (cd "$REPO/dbt" && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_PROFILES_DIR="$REPO/dbt" \
    uvx --quiet --with-requirements requirements-postgres.txt --from dbt-core dbt build --select tag:partner_outreach) \
    >"$OUT/build-$1.log" 2>&1 || { tail -30 "$OUT/build-$1.log" >&2; fail "dbt build tag:partner_outreach ($1)"; }
}
agent_warehouse() {
  make -s -C "$REPO" agent-warehouse DBT_DBNAME="$DB" >"$OUT/agent-warehouse-$1.log" 2>&1 ||
    { tail -20 "$OUT/agent-warehouse-$1.log" >&2; fail "make agent-warehouse ($1)"; }
}
assert_grants() {
  expect "agent_metrics: reachable contacts in silver.partner_contacts ($1)" \
    "$(as_role agent_metrics "select count(*) from silver.partner_contacts where reachable")" 5
  refused agent_metrics "select email from silver.partner_contacts"
  refused agent_metrics "select contact_name from silver.partner_contacts"
  refused agent_metrics "select * from silver.partner_contacts"
  expect "agent_sql: contacts on exposed.outreach_activation ($1)" \
    "$(as_role agent_sql "select string_agg(contact_id, ' ' order by contact_id) from exposed.outreach_activation")" "C-0103 C-0301"
  refused agent_sql "select phone from exposed.outreach_activation"
  refused agent_sql "select * from exposed.outreach_activation"
  expect "outreach_automation: emails on exposed.outreach_activation ($1)" \
    "$(as_role outreach_automation "select string_agg(email, ' ' order by contact_id) from exposed.outreach_activation")" \
    "chen.smith@partner1.example finn.dubois@partner3.example"
  refused outreach_automation "select email from silver.partner_contacts"
  echo "ok: $1: agent_metrics and agent_sql are refused the contacts' name, email and phone; outreach_automation reads the activation list"
}
mkdir -p "$OUT"

compose exec -T warehouse sh -c "dropdb -U warehouse --if-exists $DB && createdb -U warehouse $DB" >/dev/null 2>&1 ||
  fail "could not recreate $DB"
psql_db <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
agent_warehouse first
build first
assert_grants "agent-warehouse, then dbt build"
agent_warehouse again
assert_grants "agent-warehouse again"
build again
assert_grants "dbt build again"
echo "PASS: agent columns check"
