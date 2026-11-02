#!/usr/bin/env bash
# The scored agent eval (issue #102, semantic/PLAN.md SL-5): builds the sales, returns and finance
# models on dbt/dev/fixture.sql and fixture_weeks.sql in the Compose warehouse's dbt_dev database, writes the catalog
# (make dbt-catalog), gives the agents' read-only roles their grants there, then runs every question
# of services/semantic-agent/evals/questions.yaml through the semantic agent and the text-to-SQL
# baseline on the same model, and writes both scores to docs/research/semantic-agent-eval.md.
# Live: spends about 2 x 62 model turns of the free tier (MODEL_BACKEND, MODEL_ID; the key from
# OPENROUTER_API_KEY or the cloud network secret). Pass question ids to run only those (no report).
# Expects `make services-up`; never touches the `warehouse` database.
#
# ARM=data_agent (#207): the semantic agent over the lab project's native data agent instead
# (AGENT_TOOLSET=data_agent; `make gcp-data-agent` publishes it), on the fixture `make bigquery-live-check`
# loaded there, with the expected numbers from dbt_dev as always; no baseline; writes
# docs/research/data-agent-eval.md. Refuses without GCP_PROJECT and runs the cost check before and after,
# as every live step does (platform/gcp/README.md). Its chat calls count against the API's 30 a minute.
# The lab project must hold dbt_dev's rows: `make bigquery-live-load` first.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_dev
fail() { echo "FAIL: $*" >&2; exit 1; }

case "${ARM:-metricflow}" in
  metricflow) ;;
  data_agent)
    : "${GCP_PROJECT:?GCP_PROJECT is unset: the data-agent arm asks the data agent of the lab project (platform/gcp/README.md)}"
    export AGENT_TOOLSET=data_agent
    # The credential, as tests/e2e/bigquery-run-check.sh picks it: GCP_ACCESS_TOKEN already set; a cloud
    # session's proxy-injected token; a short-lived token of the signed-in gcloud account (an hour: run a
    # subset of question ids when the free model is slow); else application default credentials.
    if [ -z "${GCP_ACCESS_TOKEN:-}" ]; then
      if [ -n "${CLOUDSDK_AUTH_ACCESS_TOKEN:-}" ]; then
        export GCP_ACCESS_TOKEN=$CLOUDSDK_AUTH_ACCESS_TOKEN
      elif command -v gcloud >/dev/null; then
        account=${GCP_ACCOUNT:-$(gcloud config get-value account 2>/dev/null)}
        if [ -n "$account" ]; then
          GCP_ACCESS_TOKEN=$(gcloud auth print-access-token --account="$account") ||
            fail "gcloud auth print-access-token --account=$account"
          export GCP_ACCESS_TOKEN
          echo "ok: asking $GCP_PROJECT's data agent as $account (GCP_ACCOUNT=<account> picks another)"
        fi
      fi
    fi
    "$REPO/platform/gcp/cost-check.sh" || [ "${GCP_COST_UNPROVEN_OK:-}" = 1 ] ||
      fail "the cost check did not prove \$0.00 (GCP_COST_UNPROVEN_OK=1 proceeds on the owner's say-so)"
    trap '"$REPO/platform/gcp/cost-check.sh" || true' EXIT ;;
  *) fail "ARM=$ARM is not one of metricflow, data_agent" ;;
esac

# A key OpenRouter refuses fails every question (issue #116): check it before the build.
[ "${MODEL_BACKEND:-openrouter}" != openrouter ] || "$REPO/tests/e2e/openrouter-key-check.sh"
DB="$DB" "$REPO/tests/e2e/agent-fixture.sh"

cd "$REPO/services/semantic-agent"
export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics
export MODEL_RETRIES=${MODEL_RETRIES:-4}
uv run --quiet python -m semantic_agent.evaluation "$@"
