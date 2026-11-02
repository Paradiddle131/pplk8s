#!/usr/bin/env bash
# GCP image check (#206, #209, semantic/PLAN.md SL-19): the GCP builds of the dbt image and the semantic agent run
# on a BigQuery engine, not only build.
# The dbt image's GCP build runs the semantic path, not only parses it. It builds the image with WAREHOUSE=bigquery (the BigQuery adapter alone, from a lock that leaves
# out Vertex AI, pandas and pyarrow, dbt/requirements-bigquery.exclude), then, on a fresh BigQuery emulator
# holding the dev fixture's sources, runs the image's own `dbt build` of the platform part with its tests (the
# hops include every metric against its gold table) and one MetricFlow query, as Cloud Run would run it.
# The emulator gets dbt/dev/fixture.sql's sources alone (31 orders), whatever ran before: the script loads that
# file into a Postgres database of its own, gcp_image_check, recreated each run, and copies that one, never
# dbt_dev, which agent-fixture.sh extends by six weeks (fixture_weeks.sql) that time out the emulator's hops.
# Then the agent's GCP build (#209): it serves on that emulator as Cloud Run would run it (its entrypoint builds
# the catalog for the project it reads, AGENT_WAREHOUSE=bigquery, in-memory sessions) and answers one question
# through a scripted OpenRouter on localhost (lib/fake_openrouter.py, no model quota): query_metrics through
# MetricFlow on the emulator, its freshness read from ops and its audit row written there by DML. The check prints
# the container's peak memory and each image's compressed size as a registry stores it (pushed to a throwaway
# local registry, one manifest per image, as `make gcp-images` pushes them), and fails above the free path:
# 512 MiB for the agent's instance, 0.45 GiB for both images (Artifact Registry's 0.5 GiB keeps two versions, #230).
# Expects `make services-up` (the fixture loads through the Postgres warehouse).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE=${GCP_DBT_IMAGE:-pplk8s-dbt-gcp:check}
AGENT_IMAGE=${GCP_AGENT_IMAGE:-pplk8s-semantic-agent-gcp:check}
OUT=${TMPDIR:-/tmp}/pplk8s-gcp-image-check
MEMORY_LIMIT_MIB=512
IMAGES_LIMIT_BYTES=483183821 # 0.45 GiB
AGENT=pplk8s-gcp-image-check-agent
REGISTRY=pplk8s-gcp-image-check-registry
AGENT_PORT=18080 MODEL_PORT=18081 REGISTRY_PORT=5055
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml" --profile bigquery)
fail() { echo "FAIL: $*" >&2; exit 1; }
DB=gcp_image_check
psql_db() { "${COMPOSE[@]}" exec -T warehouse psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"; }
rm -rf "$OUT" && mkdir -p "$OUT"

model_pid=
cleanup() {
  docker rm -fv "$AGENT" "$REGISTRY" >/dev/null 2>&1 || true
  [ -z "$model_pid" ] || kill "$model_pid" 2>/dev/null || true
}
trap cleanup EXIT

# The Makefile's gcp-images flags: one manifest per push, no attestation.
build=(docker build --build-arg WAREHOUSE=bigquery --provenance=false --sbom=false)
# Behind a TLS-intercepting proxy (cloud sessions), the Makefile's BUILD_CA path: the proxy's CA as a secret.
if [ -n "${BUILD_CA:-}" ] && [ -f "$BUILD_CA" ]; then
  build+=(--network host --build-arg HTTPS_PROXY --build-arg HTTP_PROXY --build-arg NO_PROXY --secret "id=build_ca,src=$BUILD_CA")
fi
"${build[@]}" -t "$IMAGE" "$REPO/dbt" >"$OUT/build.log" 2>&1 || { tail -30 "$OUT/build.log" >&2; fail "docker build of the GCP dbt image"; }
echo "ok: $IMAGE built (WAREHOUSE=bigquery): its in-image checks found no Postgres package and no TLC path, and it parses"
"${build[@]}" -t "$AGENT_IMAGE" --build-context dbt="$REPO/dbt" "$REPO/services/semantic-agent" >"$OUT/build-agent.log" 2>&1 ||
  { tail -30 "$OUT/build-agent.log" >&2; fail "docker build of the agent's GCP image"; }
echo "ok: $AGENT_IMAGE built (WAREHOUSE=bigquery): no Postgres package or TLC path, it parses and builds its catalog"

{ "${COMPOSE[@]}" exec -T warehouse dropdb -U warehouse --if-exists "$DB" &&
  "${COMPOSE[@]}" exec -T warehouse createdb -U warehouse "$DB"; } || fail "recreating the Postgres database $DB"
psql_db <"$REPO/dbt/dev/fixture.sql" >"$OUT/fixture-sql.log" 2>&1 || { tail -20 "$OUT/fixture-sql.log" >&2; fail "loading dbt/dev/fixture.sql into $DB"; }
orders=$(psql_db -c "select count(*) from ds_source.synthetic_orders")
echo "ok: $DB recreated with dbt/dev/fixture.sql alone ($orders orders)"
"${COMPOSE[@]}" up -d --force-recreate --wait bigquery bigquery-api >/dev/null 2>&1 ||
  { "${COMPOSE[@]}" logs --tail 20 bigquery bigquery-api >&2; fail "the emulator did not come up"; }
(cd "$REPO/dbt" && BQ_API_ENDPOINT=http://localhost:9050 uv run --quiet --no-project \
  --with-requirements requirements-postgres.txt --with dbt-bigquery==1.12.1 --with 'psycopg[binary]==3.3.6' \
  python -I "$REPO/tests/e2e/lib/fixture_to_bigquery.py" "host=localhost port=5433 user=warehouse password=warehouse dbname=$DB") \
  >"$OUT/fixture.log" || { cat "$OUT/fixture.log" >&2; fail "copying the fixture into the emulator"; }
echo "ok: a fresh emulator holds the fixture's sources"

run_image() { docker run --rm --network host -e DBT_TARGET=bigquery_emulator -e BQ_API_ENDPOINT=http://localhost:9050 --entrypoint sh "$IMAGE" -c "$1"; }
run_image 'dbt build --select tag:sales tag:returns tag:finance tag:marketing tag:semantic tag:migration' >"$OUT/dbt.log" 2>&1 ||
  { grep -E "ERROR|Error" "$OUT/dbt.log" | tail -20 >&2; fail "the image's dbt build on the emulator"; }
hops=$(grep -c " PASS hop_" "$OUT/dbt.log" || true)
[ "$hops" -eq 31 ] || fail "expected the platform's 31 hops to pass in the image, got $hops"
echo "ok: the image's dbt build: $(grep -o "PASS=[0-9]* WARN=[0-9]* ERROR=[0-9]* SKIP=[0-9]*" "$OUT/dbt.log" | tail -1), the 31 hops of the platform part pass"
# The image ships no target/ (its build discards the parse), so the step parses first, as a job would.
run_image 'dbt parse --quiet >&2 && mf query --metrics revenue_eur,net_revenue_eur --group-by metric_time__day --order metric_time__day --csv /tmp/q.csv >&2 && cat /tmp/q.csv' \
  >"$OUT/query.csv" 2>"$OUT/query.log" || { tail -20 "$OUT/query.log" >&2; fail "the image's mf query on the emulator"; }
[ "$(tail -n +2 "$OUT/query.csv" | wc -l)" -ge 2 ] || fail "the image's mf query returned $(cat "$OUT/query.csv")"
echo "ok: the image's MetricFlow answers on the emulator ($(tail -n +2 "$OUT/query.csv" | wc -l) days)"

# The agent's GCP image. Its ops objects first, through the dbt image as a Job would create them.
run_image 'dbt run-operation agent_warehouse' >"$OUT/agent-warehouse.log" 2>&1 ||
  { tail -20 "$OUT/agent-warehouse.log" >&2; fail "dbt run-operation agent_warehouse on the emulator"; }
# ADK's FirestoreSessionService behind SESSION_SERVICE_URI=firestore://, as the image's ADK loads services.py;
# built only (an emulator host nothing listens on): Firestore itself is the live slice's.
docker run --rm -e GCP_PROJECT=pplk8s-lab -e FIRESTORE_EMULATOR_HOST=127.0.0.1:9 --entrypoint python "$AGENT_IMAGE" -c '
from google.adk.cli.service_registry import load_services_module
from google.adk.cli.utils.service_factory import create_session_service_from_options
load_services_module("/app/agents")
s = create_session_service_from_options(base_dir="/app/agents", session_service_uri="firestore://")
assert type(s).__name__ == "FirestoreSessionService", type(s)
print(type(s).__name__, s.client.project)' >"$OUT/firestore.log" 2>&1 || { cat "$OUT/firestore.log" >&2; fail "firestore:// in the agent's image"; }
echo "ok: the agent's image builds $(cat "$OUT/firestore.log") for firestore://"

question="What was net revenue on 2 October 2026?"
answer="Net revenue was 861.4 EUR on 2 October 2026."
python3 -I "$REPO/tests/e2e/lib/fake_openrouter.py" "$MODEL_PORT" "$OUT" query_metrics \
  '{"metrics": ["net_revenue_eur"], "start_date": "2026-10-02", "end_date": "2026-10-02"}' "$answer" &
model_pid=$!
docker rm -fv "$AGENT" >/dev/null 2>&1 || true
docker run -d --name "$AGENT" --network host -e PORT="$AGENT_PORT" -e GCP_PROJECT=pplk8s-lab \
  -e DBT_TARGET=bigquery_emulator -e BQ_API_ENDPOINT=http://localhost:9050 -e SESSION_SERVICE_URI=memory:// \
  -e OPENROUTER_API_BASE="http://127.0.0.1:$MODEL_PORT/api/v1" -e OPENROUTER_API_KEY=scripted -e MODEL_RETRIES=0 \
  "$AGENT_IMAGE" >/dev/null || fail "docker run of the agent's image"
url="http://127.0.0.1:$AGENT_PORT"
for _ in $(seq 90); do
  curl -sf "$url/list-apps" >"$OUT/apps.json" 2>/dev/null && break
  [ "$(docker inspect -f '{{.State.Running}}' "$AGENT")" = true ] || break
  sleep 2
done
docker logs "$AGENT" >"$OUT/agent.log" 2>&1
[ "$(jq -c . "$OUT/apps.json" 2>/dev/null)" = '["semantic_agent"]' ] || { tail -30 "$OUT/agent.log" >&2; fail "the agent did not serve semantic_agent alone"; }
grep -q '^build_catalog: ' "$OUT/agent.log" || fail "the entrypoint built no catalog"
[ "$(docker exec "$AGENT" printenv AGENT_WAREHOUSE)" = bigquery ] || fail "AGENT_WAREHOUSE is not bigquery in the image"
echo "ok: the agent serves on the emulator: its entrypoint built the catalog ($(grep '^build_catalog: ' "$OUT/agent.log" | grep -o '[0-9]* metrics')) at start, AGENT_WAREHOUSE=bigquery"

session=gcp-image-check
curl -sf -X POST -H 'Content-Type: application/json' -d '{}' "$url/apps/semantic_agent/users/check/sessions/$session" >/dev/null ||
  fail "creating a session"
jq -n --arg s "$session" --arg q "$question" \
  '{app_name: "semantic_agent", user_id: "check", session_id: $s, new_message: {role: "user", parts: [{text: $q}]}}' |
  curl -sf -X POST -H 'Content-Type: application/json' -d @- "$url/run" >"$OUT/run.json" ||
  { docker logs --tail 30 "$AGENT" >&2; fail "the agent's /run"; }
response=$(jq -c '[.[].content.parts[]? | .functionResponse? | select(.) | .response][0]' "$OUT/run.json")
rows=$(jq -c '.rows' <<<"$response")
statement=$(jq -r '.freshness.statement // empty' <<<"$response")
final=$(jq -r '[.[].content.parts[]? | .text? | select(.)] | last' "$OUT/run.json")
echo "rows: $rows"
echo "freshness: $statement"
[ "$(jq -r '.error // empty' <<<"$response")" = "" ] || fail "query_metrics answered an error: $(jq -r .error <<<"$response")"
[ "$rows" = '[{"net_revenue_eur":861.4}]' ] || fail "expected net revenue 861.4, got $rows"
# Read from ops: the ledger has no ready interval and sales's deadline comes from ops.product_deadlines; an
# unreadable ledger would say "could not be read" instead.
[[ "$statement" == *"sales.silver has never been ready (deadline 36 h)"* && "$statement" != *"could not be read"* ]] ||
  fail "expected the freshness read from ops (sales.silver never ready, its 36 h deadline), got: $statement"
[ "$final" = "$answer" ] || fail "expected the scripted answer, got: $final"
grep -q '861.4' "$OUT/tool-results.jsonl" || fail "the scripted model was not shown the tool's result"
query="select count(*) from \`pplk8s-lab.ops.agent_queries\` where session_id = '$session' and agent = 'semantic_agent'
  and tool = 'query_metrics' and rows_returned = 1 and freshness is not null"
audited=$(jq -n --arg q "$query" '{useLegacySql: false, query: $q}' |
  curl -sf -X POST -H 'Content-Type: application/json' -d @- http://localhost:9050/bigquery/v2/projects/pplk8s-lab/queries |
  jq -r '.rows[0].f[0].v')
[ "$audited" = 1 ] || fail "expected one audit row for session $session in ops.agent_queries, got $audited"
echo "ok: one question through the served agent: 861.4 through query_metrics on the emulator, its freshness from ops, its audit row by DML"

peak=$(docker exec "$AGENT" sh -c 'cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes')
peak_mib=$((peak / 1048576))
echo "agent peak memory: $peak_mib MiB (limit $MEMORY_LIMIT_MIB MiB, Cloud Run's instance)"
[ "$peak_mib" -le "$MEMORY_LIMIT_MIB" ] || fail "the agent peaked at $peak_mib MiB, above $MEMORY_LIMIT_MIB MiB"
docker rm -fv "$AGENT" >/dev/null

# Compressed sizes as a registry stores them: both images pushed to a throwaway registry, their manifests read back.
docker run -d --name "$REGISTRY" -p "127.0.0.1:$REGISTRY_PORT:5000" registry:2 >/dev/null || fail "starting a local registry"
for _ in $(seq 30); do curl -sf "http://127.0.0.1:$REGISTRY_PORT/v2/" >/dev/null && break; sleep 1; done
total=0
for image in "$IMAGE" "$AGENT_IMAGE"; do
  name=${image%%:*}
  ref="127.0.0.1:$REGISTRY_PORT/$name:check"
  docker tag "$image" "$ref" || fail "tagging $image"
  docker push --quiet "$ref" >/dev/null || fail "pushing $image to the local registry"
  docker image rm "$ref" >/dev/null
  manifest=$(curl -sf -H 'Accept: application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.index.v1+json' \
    "http://127.0.0.1:$REGISTRY_PORT/v2/$name/manifests/check")
  [ "$(jq -r '.layers | length > 0' <<<"$manifest")" = true ] || fail "$image pushed an index, not one image manifest: $(jq -c .mediaType <<<"$manifest")"
  bytes=$(jq '[.config.size, .layers[].size] | add' <<<"$manifest")
  total=$((total + bytes))
  echo "$image: $((bytes / 1048576)) MiB compressed, one manifest"
done
echo "both images: $((total / 1048576)) MiB compressed (limit $((IMAGES_LIMIT_BYTES / 1048576)) MiB, 0.45 GiB)"
[ "$total" -le "$IMAGES_LIMIT_BYTES" ] || fail "the GCP images are $total bytes compressed, above 0.45 GiB"
echo "PASS: GCP image check"
