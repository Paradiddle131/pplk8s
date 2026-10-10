#!/usr/bin/env bash
# Smoke check: the hello DAG runs on a Celery worker pod. The first half of the CI integration test
# (PLAN.md D26); expects `make airflow-up` to have run.
set -euo pipefail

source "$(dirname "$0")/lib/airflow-api.sh"
pod=$(run_hello)
echo "ok: hello succeeded on $pod"
echo "smoke-check passed"
