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

psql_wh() { docker exec pplk8s-warehouse-1 psql -U warehouse -d warehouse -Atc "$1"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

docker rm -f pplk8s-el-factory >/dev/null 2>&1 || true
docker run -d --name pplk8s-el-factory --network pplk8s -p 127.0.0.1:8090:8080 \
  -e WAREHOUSE_DSN=postgresql://warehouse:warehouse@warehouse:5432/warehouse \
  -e STORAGE_EMULATOR_HOST=http://gcs:4443 \
  "$ELF_IMAGE" >/dev/null
trap 'docker rm -f pplk8s-el-factory >/dev/null 2>&1 || true' EXIT
for _ in $(seq 30); do curl -sf "$ELF/healthz" >/dev/null && break; sleep 1; done
curl -sf "$ELF/healthz" >/dev/null || fail "EL Factory did not become healthy"
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
