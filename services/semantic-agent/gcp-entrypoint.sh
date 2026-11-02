#!/bin/sh
# The agent's GCP image (Dockerfile stage `bigquery`, semantic/PLAN.md SL-19): what the kind Deployment's catalog
# initContainer does locally (platform/k8s/workloads/semantic-agent-deployment.yaml), at container start, since
# MetricFlow's compiled SQL names the project the agent reads (SL-3): `dbt parse` on DBT_TARGET (`gcp`, the
# project in GCP_PROJECT; `bigquery_emulator` in `make gcp-image-check`) and the agent catalog, then the command.
set -eu
: "${GCP_PROJECT:?GCP_PROJECT is unset: the agent reads the BigQuery project it names}"
cd /app/dbt
dbt parse --quiet
python scripts/build_catalog.py target
cd /app
exec "$@"
