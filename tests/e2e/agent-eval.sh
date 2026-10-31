#!/usr/bin/env bash
# The scored agent eval (issue #102, semantic/PLAN.md SL-5): builds the sales, returns and finance
# models on dbt/dev/fixture.sql in the Compose warehouse's dbt_dev database, writes the catalog
# (make dbt-catalog), gives the agents' read-only roles their grants there, then runs every question
# of services/semantic-agent/evals/questions.yaml through the semantic agent and the text-to-SQL
# baseline on the same model, and writes both scores to docs/research/semantic-agent-eval.md.
# Live: spends about 2 x 15 model turns of the free tier (MODEL_BACKEND, MODEL_ID; the key from
# OPENROUTER_API_KEY or the cloud network secret). Pass question ids to run only those (no report).
# Expects `make services-up`; never touches the `warehouse` database.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_dev
fail() { echo "FAIL: $*" >&2; exit 1; }

# A key OpenRouter refuses fails every question (issue #116): check it before the build.
[ "${MODEL_BACKEND:-openrouter}" != openrouter ] || "$REPO/tests/e2e/openrouter-key-check.sh"
DB="$DB" "$REPO/tests/e2e/agent-fixture.sh"

cd "$REPO/services/semantic-agent"
export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics
export MODEL_RETRIES=${MODEL_RETRIES:-4}
uv run --quiet python -m semantic_agent.evaluation "$@"
