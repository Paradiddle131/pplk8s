#!/usr/bin/env bash
# Phase 1 exit check (PLAN.md): a curl-driven extraction lands files in fake-gcs
# and rows in ds_source, re-running the same run_id leaves counts unchanged, and
# the dbt image builds every stage through gold and exposed.
# Expects `make services-up build` to have run.
set -euo pipefail

ELF_IMAGE="${ELF_IMAGE:?}"
DBT_IMAGE="${DBT_IMAGE:?}"
ELF=http://localhost:8090
GCS=http://localhost:4480
PIPELINE=sales
RUN_ID=phase1__check
INTERVAL_START=2026-10-01T00:00:00Z
INTERVAL_END=2026-10-03T00:00:00Z

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
psql_wh() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d warehouse -Atc "$1"
}
fail() { echo "FAIL: $*" >&2; exit 1; }

ELF_PORT=8090 "$REPO/scripts/el-factory-local.sh" up >/dev/null || fail "EL Factory did not become healthy"
trap '"$REPO/scripts/el-factory-local.sh" down >/dev/null' EXIT
echo "ok: EL Factory healthy"

# Extract every catalog entity, following next_url until it is null.
extract_pipeline() {
  local entities source entity url body
  entities=$(curl -sf "$ELF/catalog?pipeline=$PIPELINE" | jq -c '.[]')
  [ -n "$entities" ] || fail "empty catalog for $PIPELINE"
  while read -r e; do
    source=$(jq -r .source <<<"$e"); entity=$(jq -r .entity <<<"$e")
    body=$(jq -nc --arg s "$source" --arg e "$entity" --arg r "$RUN_ID" \
      --arg a "$INTERVAL_START" --arg b "$INTERVAL_END" \
      '{source:$s, entity:$e, run_id:$r, interval_start:$a, interval_end:$b}')
    url=/extract
    while [ "$url" != null ]; do
      resp=$(curl -sf -X POST -H 'Content-Type: application/json' -d "$body" "$ELF$url") ||
        fail "extract $source/$entity at $url"
      url=$(jq -r .next_url <<<"$resp")
    done
  done <<<"$entities"
}

counts() { # objects:customers:orders for this run
  local objects
  objects=$(curl -sf "$GCS/storage/v1/b/staging/o?prefix=synthetic/" |
    jq --arg r "$RUN_ID" '[.items[]? | select(.name | contains("/" + $r + "/"))] | length')
  echo "$objects:$(psql_wh "select count(*) from ds_source.synthetic_customers where _run_id = '$RUN_ID'"):$(psql_wh "select count(*) from ds_source.synthetic_orders where _run_id = '$RUN_ID'")"
}

extract_pipeline
first=$(counts)
IFS=: read -r objects customers orders <<<"$first"
[ "$objects" -gt 0 ] && [ "$customers" -gt 0 ] && [ "$orders" -gt 0 ] ||
  fail "expected staged objects and rows, got objects=$objects customers=$customers orders=$orders"
echo "ok: first run staged $objects objects, loaded $customers customers and $orders orders"

extract_pipeline
second=$(counts)
[ "$first" = "$second" ] || fail "re-run changed counts: $first -> $second"
echo "ok: re-running $RUN_ID left counts unchanged ($second)"

# A re-run that yields fewer pages must not leave the earlier run's extra pages behind.
RUN_ID=phase1__repage
for size in 20 100; do
  PAGE_SIZE=$size ELF_PORT=8090 "$REPO/scripts/el-factory-local.sh" up >/dev/null || fail "EL Factory restart"
  extract_pipeline
done
repaged=$(psql_wh "select count(*) from ds_source.synthetic_orders where _run_id = '$RUN_ID'")
[ "$repaged" = "$orders" ] || fail "re-paginated run left $repaged orders, expected $orders"
echo "ok: re-running with fewer pages left exactly $repaged orders"

for stage in bronze silver gold exposed; do
  docker run --rm --network pplk8s "$DBT_IMAGE" build --select "$stage" >/tmp/pplk8s-dbt-$stage.log 2>&1 ||
    { tail -30 /tmp/pplk8s-dbt-$stage.log >&2; fail "dbt build --select $stage"; }
  echo "ok: dbt build --select $stage"
done

for rel in gold.daily_sales gold.customer_lifetime exposed.sales_by_country_daily; do
  n=$(psql_wh "select count(*) from $rel")
  [ "$n" -gt 0 ] || fail "$rel is empty"
  echo "ok: $rel has $n rows"
done

# A pipeline's stage rebuild must not drop another pipeline's relation (PLAN.md D20, issue #27):
# rebuild sales gold and returns silver alone; finance's exposed.net_sales_daily must survive.
dbt_select() {
  docker run --rm --network pplk8s "$DBT_IMAGE" build --select "$1" >/tmp/pplk8s-dbt-rebuild.log 2>&1 ||
    { tail -30 /tmp/pplk8s-dbt-rebuild.log >&2; fail "dbt build --select $1"; }
}
for sel in tag:sales,tag:gold tag:returns,tag:silver; do
  dbt_select "$sel"
  [ "$(psql_wh "select to_regclass('exposed.net_sales_daily') is not null")" = t ] ||
    fail "dbt build --select $sel dropped exposed.net_sales_daily"
done
echo "ok: rebuilding sales gold and returns silver alone kept exposed.net_sales_daily"
# Rebuilding sales gold drops sales' own exposed views (docs/runbook.md); sales_elt rebuilds them next.
dbt_select tag:sales,tag:exposed
