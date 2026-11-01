#!/usr/bin/env bash
# Catalog check (issue #101, semantic/PLAN.md SL-3, SL-4): host dbt builds every public model on the
# dev fixtures in the Compose warehouse's dbt_dev database, runs `make dbt-catalog` on it, and asserts that
#   - check_catalog.py passes: agent.json lists exactly the public models, every metric and every glossary
#     term, and the data agent's authored context uses the documented keys only,
#   - every gold and exposed relation, and every one of its columns, carries a comment (persist_docs),
#   - semantic.metrics holds one row per metric of the semantic manifest, semantic.glossary one per term,
#   - every example query (a metric's compiled SQL) runs on the warehouse and returns rows,
#   - a categorical dimension carries the values its column declares, and the agent's query_metrics answers
#     a declared value on the fixture through MetricFlow and refuses a guessed one with the declared values
#     (#157),
#   - an undocumented authored-context key, an undescribed public column, and a glossary term that names an
#     unknown metric, a dimension its metrics lack, or repeats a metric fail check_catalog.py.
# Expects `make services-up`; never touches the `warehouse` database.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_dev
OUT=${TMPDIR:-/tmp}/pplk8s-catalog-check
TARGET="$REPO/dbt/target"
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_dev() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"
}

export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_PROFILES_DIR="$REPO/dbt"
# The pins come from the image's requirements, so host and image run the same dbt and MetricFlow.
dbt_() { (cd "$REPO/dbt" && uvx --quiet --with-requirements requirements.txt --from dbt-core dbt "$@"); }
py_() { (cd "$REPO/dbt" && uv run --quiet --no-project --with-requirements requirements.txt python "$@"); }
expect() { [ "$2" = "$3" ] || fail "$1: expected [$3], got [$2]"; }

rm -rf "$OUT" && mkdir -p "$OUT"
psql_dev -c "select 1" >/dev/null 2>&1 || docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse createdb -U warehouse "$DB"
for fixture in fixture.sql tlc_fixture.sql; do
  psql_dev <"$REPO/dbt/dev/$fixture" 2>&1 | grep -v NOTICE || true
done
echo "ok: fixtures loaded into $DB"

# Rebuilt from scratch, so a comment can only come from this build's persist_docs.
psql_dev -c "set client_min_messages = warning" -c "drop schema if exists gold cascade" -c "drop schema if exists exposed cascade"
dbt_ build --select tag:sales tag:returns tag:finance tag:marketing tag:customer_actions tag:partner_outreach tag:recruitment tag:call_transcripts tag:tlc --vars '{data_month: 2024-12}' >"$OUT/build.log" 2>&1 ||
  { tail -30 "$OUT/build.log" >&2; fail "dbt build of the sales, returns, finance, marketing, customer-actions, partner-outreach, recruitment, call-transcripts and tlc models"; }
# The drop took the agents' schema grants with it; give them back, as make agent-eval does.
psql_dev -c "set client_min_messages = warning" -f /docker-entrypoint-initdb.d/01-schemas.sql
make -s -C "$REPO" agent-warehouse DBT_DBNAME="$DB" >"$OUT/agent-warehouse.log" 2>&1 ||
  { tail -30 "$OUT/agent-warehouse.log" >&2; fail "make agent-warehouse"; }
echo "ok: sales, returns, finance, marketing, customer actions, partner outreach, recruitment, call transcripts and tlc (2024-12) built; agent roles granted again"

make -s -C "$REPO" dbt-catalog DBT_DBNAME="$DB" >"$OUT/catalog.log" 2>&1 ||
  { tail -30 "$OUT/catalog.log" >&2; fail "make dbt-catalog against $DB"; }
grep -q "17 public models, 54 metrics and 12 glossary terms" "$OUT/catalog.log" ||
  { cat "$OUT/catalog.log" >&2; fail "build_catalog did not report 17 public models, 54 metrics and 12 glossary terms"; }
grep -q "check_catalog: every public model, metric, glossary term and saved query is catalogued" "$OUT/catalog.log" || fail "check_catalog did not pass"
echo "ok: make dbt-catalog wrote agent.json, system_instruction.yaml and example_queries.json; check_catalog passes"

# Every public relation built, and no relation or column of gold or exposed without a comment.
public=$(py_ -c "import json; print('\n'.join(sorted(m['relation'].split('.', 1)[1] for m in json.load(open('target/catalog/agent.json'))['models'])))")
built=$(psql_dev -c "select table_schema || '.' || table_name from information_schema.tables where table_schema in ('gold', 'exposed') order by 1")
# A gold or exposed model holding personal data is protected and stays out of the catalog (SL-16).
protected=$(py_ -c "import json; print('\n'.join(sorted(n['schema'] + '.' + n['alias'] for n in json.load(open('target/manifest.json'))['nodes'].values() if n['resource_type'] == 'model' and n['schema'] in ('gold', 'exposed') and n.get('access') != 'public')))")
expect "protected gold and exposed relations" "$protected" "exposed.outreach_activation"
expect "gold and exposed relations vs the catalog's public models" "$(grep -vxF "$protected" <<<"$built")" "$public"
expect "relations without a comment" "$(psql_dev -c "
  select string_agg(table_schema || '.' || table_name, ',') from information_schema.tables
  where table_schema in ('gold', 'exposed')
    and coalesce(obj_description((quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass), '') = ''")" ""
expect "columns without a comment" "$(psql_dev -c "
  select string_agg(table_schema || '.' || table_name || '.' || column_name, ',') from information_schema.columns
  where table_schema in ('gold', 'exposed')
    and coalesce(col_description((quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass, ordinal_position), '') = ''")" ""
echo "ok: $(echo "$built" | wc -l) gold and exposed relations, each and every column commented"

metrics=$(py_ -c "import json; print('\n'.join(sorted(m['name'] for m in json.load(open('target/semantic_manifest.json'))['metrics'])))")
expect "semantic.metrics vs the semantic manifest" "$(psql_dev -c "select metric_name from semantic.metrics order by metric_name collate \"C\"")" "$metrics"
expect "semantic.metrics rows without words" "$(psql_dev -c "select count(*) from semantic.metrics where label = '' or description = '' or pipelines = ''")" 0
echo "ok: semantic.metrics holds the $(echo "$metrics" | wc -l) metrics"

terms=$(py_ -c "import json; print('\n'.join(sorted(t['term'] for t in json.load(open('target/catalog/agent.json'))['glossary'])))")
expect "semantic.glossary vs the catalog's glossary" "$(psql_dev -c "select term from semantic.glossary order by term collate \"C\"")" "$terms"
expect "semantic.glossary rows without words or a mapping" "$(psql_dev -c "select count(*) from semantic.glossary where description = '' or metrics || dimensions = ''")" 0
expect "the data agent's glossary terms" "$(py_ -c "
import yaml
context = yaml.safe_load(open('target/catalog/data_agent/system_instruction.yaml'))
glossaries = next(item['glossaries'] for item in context if 'glossaries' in item)
print(len(glossaries))
")" "$(( $(echo "$metrics" | wc -l) + $(echo "$terms" | wc -l) ))"
echo "ok: semantic.glossary and the data agent's glossaries hold the $(echo "$terms" | wc -l) glossary terms beside the metrics"

# The verified queries are the metrics' compiled SQL: each must run and return the fixture's days.
py_ -c "
import json
for i, q in enumerate(json.load(open('target/catalog/data_agent/example_queries.json'))):
    open('$OUT/query-%d.sql' % i, 'w').write(q['sqlQuery'] + ';\n')
"
for query in "$OUT"/query-*.sql; do
  rows=$(psql_dev -c "select count(*) from ($(sed '$ s/;$//' "$query")) q")
  [ "$rows" -ge 1 ] || fail "example query $(basename "$query") returned $rows rows"
done
echo "ok: every example query runs on $DB and returns rows"

# Negative cases on a copy of the target: an undocumented key, then an undescribed public column.
stray="$OUT/target"
mkdir -p "$stray" && cp -r "$TARGET/manifest.json" "$TARGET/semantic_manifest.json" "$TARGET/catalog" "$stray/"
echo "- verified_answers: [made up]" >>"$stray/catalog/data_agent/system_instruction.yaml"
if py_ scripts/check_catalog.py "$stray" >"$OUT/stray.log" 2>&1; then fail "check_catalog passed with an undocumented key"; fi
grep -q "undocumented key 'verified_answers'" "$OUT/stray.log" || { cat "$OUT/stray.log" >&2; fail "check_catalog failed, but not on the undocumented key"; }
cp "$TARGET/catalog/data_agent/system_instruction.yaml" "$stray/catalog/data_agent/"
py_ -c "
import json
path = '$stray/manifest.json'
manifest = json.load(open(path))
manifest['nodes']['model.pplk8s.gld_daily_sales']['columns']['revenue_eur']['description'] = ''
json.dump(manifest, open(path, 'w'))
"
if py_ scripts/check_catalog.py "$stray" >"$OUT/stray.log" 2>&1; then fail "check_catalog passed with an undescribed gold column"; fi
grep -q "public model gld_daily_sales: column revenue_eur has no description" "$OUT/stray.log" ||
  { cat "$OUT/stray.log" >&2; fail "check_catalog failed, but not on the undescribed column"; }

# A glossary term that names an unknown metric, a dimension none of its metrics has, or a metric's own label.
py_ -c "
import json
path = '$stray/manifest.json'
manifest = json.load(open(path))
manifest['nodes']['model.pplk8s.gld_daily_sales']['columns']['revenue_eur']['description'] = 'restored'
glossary = manifest['nodes']['model.pplk8s.slv_orders']['config']['meta']['glossary']
glossary += [
    {'term': 'Gross margin', 'description': 'Made up.', 'metrics': ['gross_margin_eur']},
    {'term': 'Ad market', 'description': 'Made up.', 'metrics': ['revenue_eur'], 'dimensions': ['campaign__market']},
    {'term': 'Revenue (EUR)', 'description': 'A second definition.', 'metrics': ['revenue_eur']},
]
json.dump(manifest, open(path, 'w'))
"
if py_ scripts/check_catalog.py "$stray" >"$OUT/stray.log" 2>&1; then fail "check_catalog passed with stray glossary terms"; fi
for problem in "glossary term 'Gross margin' on slv_orders: unknown metric gross_margin_eur" \
  "glossary term 'Ad market' on slv_orders: dimension campaign__market is not a dimension of its metrics" \
  "glossary term 'Revenue (EUR)' on slv_orders: repeats metric revenue_eur"; do
  grep -qF "$problem" "$OUT/stray.log" || { cat "$OUT/stray.log" >&2; fail "check_catalog did not report: $problem"; }
done
echo "ok: an undocumented authored-context key, an undescribed public column and stray glossary terms fail check_catalog"

# The declared values reach the agent's tools (#157): on the fixture, as agent_metrics, through MetricFlow.
expect "return__reason's values in agent.json" "$(py_ -c "
import json
metric = next(m for m in json.load(open('target/catalog/agent.json'))['metrics'] if m['name'] == 'returns_eur')
print(next(d for d in metric['dimensions'] if d['name'] == 'return__reason').get('values'))
")" "['damaged', 'wrong size', 'late delivery']"
agent_py() {
  (cd "$REPO/services/semantic-agent" && DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics \
    SEMANTIC_CATALOG="$TARGET/catalog/agent.json" uv run --quiet python -c "$1")
}
answer=$(agent_py "
from semantic_agent.tools import query_metrics
for value in ('damaged', 'damaged goods'):
    result = query_metrics(['returns_eur'], filters=[{'dimension': 'return__reason', 'operator': '=', 'values': [value]}])
    print(result.get('error') or result['rows'])
")
expect "query_metrics on return__reason = damaged, then = damaged goods" "$answer" \
  "[{'returns_eur': 12.5}]
'return__reason' has no value 'damaged goods'; its values are ['damaged', 'wrong size', 'late delivery']"
echo "ok: return__reason carries its declared values; query_metrics answers damaged (12.5) and refuses damaged goods"

echo "PASS: catalog check"
