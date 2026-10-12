#!/usr/bin/env bash
# Metadata DB retention check (PLAN.md D30): one run of the chart's `airflow db clean` CronJob removes
# rows older than its retention, including the `running` job row a crashed component leaves behind
# (runbook drill 9), and keeps every live component's job row.
# Seeds a crashed TriggererJob row whose last heartbeat is 61 days old, runs the CronJob once as a
# Job, and asserts the row is gone. Expects `make airflow-up`. Re-runnable; leaves no seeded row.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/airflow-api.sh
source "$(dirname "$0")/lib/airflow-api.sh"
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml")
psql_meta() { "${COMPOSE[@]}" exec -T metadata-db psql -U airflow -d airflow -Atc "$1"; }
SEED_HOST=db-cleanup-check
job="db-cleanup-check-$(date +%s)"
cleanup() {
  local rc=$?
  set +e
  psql_meta "DELETE FROM job WHERE hostname = '$SEED_HOST'" >/dev/null
  kc delete job "$job" --ignore-not-found >/dev/null
  exit $rc
}
trap cleanup EXIT

kc get cronjob airflow-database-cleanup >/dev/null || fail "CronJob airflow-database-cleanup is missing (databaseCleanup.enabled)"
seed=$(psql_meta "INSERT INTO job (state, job_type, start_date, latest_heartbeat, hostname, unixname)
                  VALUES ('running', 'TriggererJob', now() - interval '61 days', now() - interval '61 days',
                          '$SEED_HOST', 'airflow') RETURNING id" | head -1)
live() { psql_meta "SELECT string_agg(job_type || ':' || id, ' ' ORDER BY id) FROM job
                    WHERE state = 'running' AND latest_heartbeat > now() - interval '1 minute'"; }
before=$(live)
echo "seeded crashed job $seed (heartbeat 61 days old); live jobs: $before"

kc create job "$job" --from=cronjob/airflow-database-cleanup >/dev/null
kc wait --for=condition=complete "job/$job" --timeout=300s >/dev/null || {
  kc logs "job/$job" --tail=40 >&2
  fail "the cleanup Job did not complete"
}
kc logs "job/$job" | grep -E '^Cleaning up|job' | head -5

[ -z "$(psql_meta "SELECT id FROM job WHERE id = $seed")" ] || fail "the crashed job row $seed survived the cleanup"
after=$(live)
for j in $before; do
  case " $after " in *" $j "*) ;; *) fail "live job $j disappeared (after: $after)" ;; esac
done
stale=$(psql_meta "SELECT count(*) FROM job WHERE latest_heartbeat < now() - interval '60 days'")
[ "$stale" = 0 ] || fail "$stale job rows older than the 60-day retention remain"
# db clean moves rows into _airflow_deleted__* tables first; with --skip-archive it drops them after.
archives=$(psql_meta "SELECT string_agg(tablename, ' ') FROM pg_tables WHERE tablename LIKE '\_airflow\_deleted\_\_%'")
[ -z "$archives" ] || fail "archive tables left behind: $archives"
echo "ok: db clean removed the 61-day-old crashed job $seed and kept the live jobs ($after)"
