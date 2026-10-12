#!/usr/bin/env bash
# Point Airflow's run_dbt at a dbt image: set the dbt_image Variable, which the seam reads at task run
# time (D16), so the next dbt pod runs it with no Airflow restart. Usage: dbt-image-variable.sh <image>
# Called by workloads-up.sh and deploy.sh, whichever runs last; a no-op while Airflow is not deployed.
set -euo pipefail
image="${1:?usage: dbt-image-variable.sh <image>}"
KUBECTL=(kubectl --context kind-pplk8s -n airflow)

if ! "${KUBECTL[@]}" get deploy/airflow-scheduler >/dev/null 2>&1; then
  echo "airflow not deployed; its deploy sets dbt_image"
  exit 0
fi
"${KUBECTL[@]}" exec deploy/airflow-scheduler -c scheduler -- airflow variables set dbt_image "$image" >/dev/null
echo "airflow variable dbt_image=$image"
