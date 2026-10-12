#!/usr/bin/env bash
# Run `dbt build --select <stage>` as a Kubernetes Job and wait for it. Usage: dbt-job.sh bronze|silver|gold|exposed
set -euo pipefail
stage="${1:?usage: dbt-job.sh <stage>}"
case "$stage" in bronze|silver|gold|exposed) ;; *) echo "unknown stage: $stage" >&2; exit 2 ;; esac

image="${DBT_IMAGE:-$(make -s -C "$(dirname "$0")/../.." print-DBT_IMAGE)}" # Makefile default outside make
k() { kubectl --context kind-pplk8s -n workloads "$@"; }
name="dbt-${stage}-$(date +%s)"

sed -e "s/__NAME__/${name}/g" -e "s/__STAGE__/${stage}/g" -e "s|__IMAGE__|${image}|g" "$(dirname "$0")/dbt-job.template.yaml" | k apply -f - >/dev/null
echo "created job/${name}"

# Wait for either outcome: `kubectl wait` blocks on one condition only, so poll both.
deadline=$((SECONDS + ${DBT_JOB_TIMEOUT:-300}))
result=""
while [ "$SECONDS" -lt "$deadline" ]; do
  if [ "$(k get job "$name" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')" = True ]; then result=complete; break; fi
  if [ "$(k get job "$name" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')" = True ]; then result=failed; break; fi
  sleep 2
done

k logs "job/${name}" --tail=-1 || true
[ "$result" = complete ] || { echo "job/${name} did not complete (${result:-timed out})" >&2; exit 1; }
echo "job/${name} complete"
