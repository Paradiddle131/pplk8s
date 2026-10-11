#!/usr/bin/env bash
# Phase 6 drill 5 (PLAN.md §5, D28): roll the chart and the Airflow minor version, then practise the
# way back. Runs against a throwaway database, airflow_drill on the same metadata-db instance, so the
# lab's own metadata is never the only copy at risk:
#   1. install the older line: chart 1.21.0 + Airflow 3.2.2 (AIRFLOW_DRILL_IMAGE) on airflow_drill
#   2. back up airflow_drill (pg_dump), preview the upgrade with helm diff, upgrade to chart 1.22.0 +
#      Airflow 3.3.1; `airflow db migrate` moves the schema forward
#   3. roll back the wrong way (helm rollback alone): the old image meets the newer schema, and the
#      failure is detected by alerts (AirflowMigrationJobFailed, then AirflowRolloutStuck)
#   4. roll back the right way: restore the dump, redeploy the older line, canary
# The exit trap (also on SIGINT/SIGTERM) redeploys the normal release on database `airflow` and
# drops airflow_drill. Expects `make airflow-up observability-up`; takes about 10 minutes.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
source "$(dirname "$0")/lib/airflow-api.sh"
source "$(dirname "$0")/lib/prometheus.sh"
DEPLOY="$REPO/platform/helm/airflow/deploy.sh"
DRILL_DB=airflow_drill
OLD_CHART=1.21.0
OLD_AIRFLOW=3.2.2
OLD_IMAGE="${AIRFLOW_DRILL_IMAGE:?set by the Makefile}"
NEW_IMAGE="${AIRFLOW_IMAGE:?set by the Makefile}"
BACKUP="$(mktemp -d)/airflow_drill.dump"
say() { echo "[$(date +%T)] $*"; }
meta_psql() { # db sql
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T metadata-db psql -U airflow -d "$1" -v ON_ERROR_STOP=1 -Atqc "$2"
}
hm() { helm --kube-context "$CTX" -n "$NS" "$@"; }
schema() { meta_psql "$DRILL_DB" "SELECT version_num FROM alembic_version"; }
version() { api GET /api/v2/version | jq -r .version; }
deploy_old() {
  CHART_VERSION=$OLD_CHART AIRFLOW_IMAGE=$OLD_IMAGE AIRFLOW_IMAGE_BUILD=0 "$DEPLOY" \
    --set "airflowVersion=$OLD_AIRFLOW" --set "data.metadataConnection.db=$DRILL_DB"
}
deploy_new_on_drill() {
  AIRFLOW_IMAGE=$NEW_IMAGE AIRFLOW_IMAGE_BUILD=0 "$DEPLOY" --set "data.metadataConnection.db=$DRILL_DB"
}
reconnect() { # after a rollout the port-forward points at a dead pod
  start_port_forward
  refresh_token
}
# Before a deploy that moves PgBouncer to the other database (issue #11). PgBouncer rolls while the
# migration Job already runs, so `airflow db migrate` and the pods' wait-for-airflow-migrations reach
# whichever database the surviving old PgBouncer pod still serves: the 3.2.2 Job failed on the lab's
# newer `airflow` schema and crash-looped past helm's timeout, and the restore's Job migrated
# airflow_drill instead of `airflow`. With PgBouncer gone, only the new config can answer. Its preStop
# sleeps 120 s for clients, and none are left, so its pods go at once.
stop_airflow() {
  kc scale deploy --all --replicas=0 >/dev/null
  kc delete pod -l component=pgbouncer --grace-period=1 --ignore-not-found --wait=true >/dev/null
  kc wait --for=delete pod -l 'component in (scheduler,api-server,dag-processor,triggerer)' --timeout=180s >/dev/null
}
dump_migration() { # what the migration Job and a waiting pod said, before anything redeploys them
  local pod
  kc get pods --no-headers | awk '$3!="Running" && $3!="Completed"{print "    " $1, $2, $3, "restarts=" $4}'
  for pod in $(kc get pods -l job-name=airflow-run-airflow-migrations -o name); do
    echo "    --- $pod (previous attempt)"
    kc logs "$pod" --previous --tail=30 2>/dev/null | sed 's/^/    /'
    echo "    --- $pod"
    kc logs "$pod" --tail=30 2>/dev/null | sed 's/^/    /'
  done
  pod=$(kc get pods -l component=scheduler -o json |
    jq -r '[.items[] | select(any(.status.initContainerStatuses[]?; .ready | not)) | .metadata.name] | first // empty')
  [ -z "$pod" ] || {
    echo "    --- $pod wait-for-airflow-migrations"
    kc logs "$pod" -c wait-for-airflow-migrations --tail=15 2>/dev/null | sed 's/^/    /'
  }
}

restored=""
cleanup() {
  local rc=$?
  set +e
  if [ "$rc" != 0 ]; then
    say "failed (rc=$rc); migration state before the restore:"
    dump_migration
  fi
  if [ -z "$restored" ]; then
    say "restoring the normal release (chart 1.22.0, $NEW_IMAGE, database airflow)"
    stop_airflow
    AIRFLOW_IMAGE=$NEW_IMAGE AIRFLOW_IMAGE_BUILD=0 "$DEPLOY" >/dev/null
  fi
  meta_psql postgres "DROP DATABASE IF EXISTS $DRILL_DB WITH (FORCE)" >/dev/null
  rm -rf "$(dirname "$BACKUP")"
  stop_prometheus
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

# ---- preflight --------------------------------------------------------------------------------------
docker image inspect "$OLD_IMAGE" >/dev/null 2>&1 || {
  say "building $OLD_IMAGE"
  docker build -q -t "$OLD_IMAGE" --build-arg "AIRFLOW_VERSION=$OLD_AIRFLOW" \
    --build-arg REQUIREMENTS=requirements-drill-3.2.2.txt --build-arg DROP_CONSTRAINTS=-none- "$REPO/airflow" >/dev/null
}
docker image inspect "$NEW_IMAGE" >/dev/null 2>&1 || docker build -q -t "$NEW_IMAGE" "$REPO/airflow" >/dev/null
start_prometheus
reconnect
canary_new=$(run_hello)
say "preflight: lab on Airflow $(version), canary on $canary_new"
meta_psql postgres "DROP DATABASE IF EXISTS $DRILL_DB WITH (FORCE)" >/dev/null
meta_psql postgres "CREATE DATABASE $DRILL_DB OWNER airflow" >/dev/null

# ---- 1. the older line ------------------------------------------------------------------------------
say "1. installing chart $OLD_CHART + Airflow $OLD_AIRFLOW on database $DRILL_DB"
stop_airflow
deploy_old >/dev/null
reconnect
[ "$(version)" = "$OLD_AIRFLOW" ] || fail "api-server reports $(version), expected $OLD_AIRFLOW"
old_rev=$(hm history airflow -o json | jq 'last.revision')
old_schema=$(schema)
say "  Airflow $(version), helm revision $old_rev, schema $old_schema; canary on $(run_hello)"
echo "ok: (1) the older line runs"

# ---- 2. back up, preview, upgrade -------------------------------------------------------------------
docker compose -f "$REPO/platform/compose/compose.yaml" exec -T metadata-db \
  pg_dump -U airflow -Fc "$DRILL_DB" >"$BACKUP"
say "2. backed up $DRILL_DB ($(du -h "$BACKUP" | cut -f1)) before the upgrade"
diff_out=$(hm diff upgrade airflow apache-airflow/airflow --version 1.22.0 --reuse-values --no-color \
  --set "images.airflow.tag=${NEW_IMAGE##*:}" --set airflowVersion=3.3.1)
grep -q "${NEW_IMAGE##*:}" <<<"$diff_out" || fail "helm diff does not show the new image"
say "  helm diff: $(grep -c '^[+-] ' <<<"$diff_out") changed lines, chart $(grep -m1 -o 'airflow-1\.2[0-9]\.[0-9]' <<<"$diff_out" || echo '?') -> 1.22.0"
deploy_new_on_drill >/dev/null
reconnect
[ "$(version)" = 3.3.1 ] || fail "api-server reports $(version) after the upgrade"
new_schema=$(schema)
[ "$new_schema" != "$old_schema" ] || fail "the schema did not move ($new_schema)"
new_rev=$(hm history airflow -o json | jq 'last.revision')
say "  Airflow $(version), helm revision $new_rev, schema $old_schema -> $new_schema; canary on $(run_hello)"
echo "ok: (2) upgraded to chart 1.22.0 + Airflow 3.3.1; the migration moved the schema forward"

# ---- 3. the wrong way back --------------------------------------------------------------------------
say "3. helm rollback to revision $old_rev alone (old image, newer schema)"
kc delete job --ignore-not-found --wait=true airflow-run-airflow-migrations airflow-create-user >/dev/null
hm rollback airflow "$old_rev" --timeout 10m >/dev/null
took=$(wait_alert AirflowMigrationJobFailed firing 300)
say "  detected: AirflowMigrationJobFailed firing after ${took}s"
took=$(wait_alert AirflowRolloutStuck firing 600)
say "  detected: AirflowRolloutStuck firing after ${took}s more; still serving Airflow $(version) (the old pods stay up)"
kc get pods --no-headers | awk '$3!="Running" && $3!="Completed"{print "    " $1, $2, $3, "restarts=" $4}' | head -10
mig=$(kc logs job/airflow-run-airflow-migrations --tail=200 2>/dev/null | grep -iE 'revision|error|exception' | tail -1 | cut -c1-240 || true)
say "  migration job log: ${mig:-<no log>}"
stuck=$(kc get pods -l component=scheduler -o json |
  jq -r '[.items[] | select(any(.status.initContainerStatuses[]?; .ready | not)) | .metadata.name] | first // empty')
init=$( [ -z "$stuck" ] || kc logs "$stuck" -c wait-for-airflow-migrations --tail=50 2>/dev/null | grep -iE 'revision|error|timeout|exception' | tail -1 | cut -c1-240 || true)
say "  new scheduler pod ${stuck:-?}, wait-for-airflow-migrations: ${init:-<no log>}"
echo "ok: (3) helm rollback alone never landed (the old image cannot start on the newer schema), and an alert fired"

# ---- 4. the right way back --------------------------------------------------------------------------
say "4. restoring $DRILL_DB from the backup, then redeploying the older line"
stop_airflow # nothing may hold connections during the restore
meta_psql postgres "DROP DATABASE IF EXISTS $DRILL_DB WITH (FORCE)" >/dev/null
meta_psql postgres "CREATE DATABASE $DRILL_DB OWNER airflow" >/dev/null
docker compose -f "$REPO/platform/compose/compose.yaml" exec -T metadata-db \
  pg_restore -U airflow -d "$DRILL_DB" --no-owner <"$BACKUP"
[ "$(schema)" = "$old_schema" ] || fail "restored schema is $(schema), expected $old_schema"
deploy_old >/dev/null
reconnect
[ "$(version)" = "$OLD_AIRFLOW" ] || fail "api-server reports $(version) after the restore"
wait_alert AirflowRolloutStuck inactive 600 >/dev/null
took=$(wait_alert AirflowMigrationJobFailed inactive 600)
say "  back on Airflow $(version), schema $(schema); alerts resolved after ${took}s; canary on $(run_hello)"
echo "ok: (4) restore + redeploy brought the older line back"

# ---- back to the lab --------------------------------------------------------------------------------
say "restoring the normal release"
stop_airflow
AIRFLOW_IMAGE=$NEW_IMAGE AIRFLOW_IMAGE_BUILD=0 "$DEPLOY" >/dev/null
restored=1
reconnect
[ "$(version)" = 3.3.1 ] || fail "the lab reports $(version) after the drill"
say "lab back on Airflow $(version); canary on $(run_hello)"
echo "phase6-upgrade-drill passed"
