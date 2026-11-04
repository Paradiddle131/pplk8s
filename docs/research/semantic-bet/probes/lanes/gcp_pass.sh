#!/usr/bin/env bash
# gcp_pass.sh <THINKING|FAST> <frozen|hard>: native-context-bare on the data agent in that Gemini mode, k = 3, resuming from its log;
# the cost and usage checks after. Needs make services-up and the agents fixture (tests/e2e/agent-fixture.sh, DB=dbt_dev).
set -uo pipefail
mode=$1 set=$2
REPO=$(cd "$(dirname "$0")/../../../../.." && pwd)
cd "$REPO/services/semantic-agent"
setarg=(); [ "$set" = hard ] && setarg=(--set hard)
echo "start $(date -u +%FT%H:%MZ) $mode $set"
BET_DATA_AGENT_THINKING=$mode GCP_PROJECT=pplk8s-lab-001 DBT_DBNAME=dbt_dev DBT_HOST=localhost DBT_PORT=5433 \
  uv run --quiet python ../../docs/research/semantic-bet/probes/328_mcp_live.py \
  --agent 354_data_agent.py --arm native-context-bare "${setarg[@]}" --runs 3 --requests 700 --minutes 110
rc=$?
echo "pass exit=$rc $(date -u +%FT%H:%MZ)"
cd "$REPO" && make -s gcp-cost-check | tail -3; echo "cost exit=${PIPESTATUS[0]}"
make -s gcp-usage-check | tail -1; echo "usage exit=${PIPESTATUS[0]}"
exit $rc
