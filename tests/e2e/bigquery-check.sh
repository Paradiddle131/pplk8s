#!/usr/bin/env bash
# BigQuery path check (issue #104, semantic/PLAN.md R7): the dbt project, unchanged, on the
# compile-only `bigquery` target of dbt/profiles.yml, with no GCP account and no warehouse:
#   - `dbt parse` and MetricFlow's `mf validate-configs --skip-dw` pass;
#   - `dbt compile` of the semantic path (sales, returns, finance, semantic; tlc introspects its
#     source and needs a live connection) passes, and every compiled model parses as BigQuery SQL
#     with none of the Postgres-only constructs the dialect macros replace (macros/dialect.sql);
#   - the call labels compile to BigQuery's AI.GENERATE with an output schema and a named endpoint,
#     never to the lab's recordings (semantic/PLAN.md SL-18; compiled, never run);
#   - build_catalog.py writes the agent catalog and the data agent's authored context for BigQuery:
#     relations are `project.dataset.table` and every verified query reads backticked BigQuery
#     tables; check_catalog.py passes.
# It runs in a copy of dbt/, because MetricFlow reads <project>/target whatever DBT_TARGET_PATH
# says, and leaves the artefacts in dbt/target/bigquery/ for docs/semantic-layer-on-bigquery.md.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/dbt-deps.sh
source "$REPO/tests/e2e/lib/dbt-deps.sh"
OUT=${TMPDIR:-/tmp}/pplk8s-bigquery-check
PROJECT="$OUT/dbt"
fail() { echo "FAIL: $*" >&2; exit 1; }

# The image's pins plus the BigQuery adapter (the image itself carries no BigQuery adapter).
DBT_BIGQUERY=dbt-bigquery==1.12.1
SQLGLOT=sqlglot==27.28.1
export DBT_TARGET=bigquery DBT_PROFILES_DIR="$PROJECT"
run_() { (cd "$PROJECT" && uv run --quiet --no-project --with-requirements requirements-postgres.txt --with "$DBT_BIGQUERY" "$@"); }

rm -rf "$OUT" && mkdir -p "$PROJECT"
(cd "$REPO/dbt" && tar --exclude=./target --exclude=./logs --exclude=./dbt_packages -cf - .) | tar -xf - -C "$PROJECT"
dbt_deps "$PROJECT"

run_ dbt parse --quiet || fail "dbt parse on the bigquery target"
run_ mf validate-configs --skip-dw >"$OUT/validate.log" 2>&1 || { tail -20 "$OUT/validate.log" >&2; fail "mf validate-configs --skip-dw"; }
echo "ok: dbt parse and mf validate-configs --skip-dw pass on the bigquery target"

run_ dbt compile --quiet --no-introspect --no-populate-cache \
  --select tag:sales tag:returns tag:finance tag:marketing tag:customer_actions tag:partner_outreach tag:recruitment tag:call_transcripts tag:semantic --exclude tag:tlc >"$OUT/compile.log" 2>&1 ||
  { tail -20 "$OUT/compile.log" >&2; fail "dbt compile of the semantic path on the bigquery target"; }
uvx --quiet --with "$SQLGLOT" python -I - "$PROJECT/target/compiled/pplk8s/models" <<'EOF' || fail "compiled SQL is not BigQuery"
import pathlib, re, sys
import sqlglot

# Postgres spellings the dialect macros replace; sqlglot alone reads some of them leniently.
POSTGRES_ONLY = re.compile(r"at time zone|generate_series\(|timestamptz|::| as text\)", re.IGNORECASE)
models = [f for f in sorted(pathlib.Path(sys.argv[1]).rglob("*.sql")) if ".yml" not in str(f)]
bad = []
for f in models:
    sql = "\n".join(line for line in f.read_text().splitlines() if not line.lstrip().startswith("--"))
    try:
        sqlglot.parse(sql, read="bigquery", error_level=sqlglot.ErrorLevel.RAISE)
    except sqlglot.errors.ParseError as e:
        bad.append(f"{f.name}: {str(e).splitlines()[0][:120]}")
    if found := POSTGRES_ONLY.search(sql):
        bad.append(f"{f.name}: Postgres-only {found[0]!r}")
print("\n".join(bad) or f"{len(models)} compiled models parse as BigQuery")
sys.exit(1 if bad or not models else 0)
EOF
echo "ok: the semantic path compiles to BigQuery SQL"
for model in slv_call_transcript_labels slv_call_golden_labels; do
  compiled="$PROJECT/target/compiled/pplk8s/models/silver/$model.sql"
  for expected in "AI.GENERATE(" "endpoint => 'gemini-3.5-flash'" "output_schema => 'topic STRING, objection STRING, sentiment STRING, next_step STRING'"; do
    grep -qF "$expected" "$compiled" || fail "$model does not compile to: $expected"
  done
  ! grep -v "^-- depends_on:" "$compiled" | grep -q "call_label_recordings" || fail "$model reads the lab's recordings on the bigquery target"
done
echo "ok: the call labels compile to AI.GENERATE with an output schema on the bigquery target, not to the recordings"

run_ python scripts/build_catalog.py target >/dev/null || fail "build_catalog.py on the bigquery target"
run_ python scripts/check_catalog.py target >/dev/null || fail "check_catalog.py on the bigquery target"
run_ python - <<'EOF' || fail "the catalog does not name BigQuery tables"
import json, re
catalog = json.load(open("target/catalog/agent.json"))
queries = json.load(open("target/catalog/data_agent/example_queries.json"))
relations = [m["relation"] for m in catalog["models"]]
assert all(r.count(".") == 2 and not r.startswith(("dbt_dev.", "warehouse.")) for r in relations), relations
tables = {t for q in queries for t in re.findall(r"FROM (`[^`]+`\.`[^`]+`\.`[^`]+`)", q["sqlQuery"])}
assert tables and all(q["sqlQuery"].count("`") >= 6 for q in queries), tables
print(f"{len(relations)} relations like {relations[0]}; verified queries read {sorted(tables)}")
EOF
rm -rf "$REPO/dbt/target/bigquery" && mkdir -p "$REPO/dbt/target/bigquery"
cp -r "$PROJECT/target/catalog" "$REPO/dbt/target/bigquery/"
echo "ok: build_catalog and check_catalog pass on the bigquery target; artefacts in dbt/target/bigquery/catalog"
