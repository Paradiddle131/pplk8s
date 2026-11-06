#!/usr/bin/env bash
# gcp_pass.sh <THINKING|FAST|DEFAULT> <frozen|hard|hard-v2> [arm] [runs]: one data-agent arm (default native-context-bare)
# in that Gemini mode (DEFAULT: the service's own, as the arms' first passes ran), k = runs (default 3), resuming from its
# log; the cost and usage checks before and after (a failed check before the pass stops it, exit 4).
# Needs make services-up and the agents fixture (tests/e2e/agent-fixture.sh, DB=dbt_dev).
set -uo pipefail
mode=$1 set=$2 arm=${3:-native-context-bare} runs=${4:-3}
REPO=$(cd "$(dirname "$0")/../../../../.." && pwd)
gates() {
  local rc
  cd "$REPO" || return 1
  make -s gcp-cost-check | tail -3; rc=${PIPESTATUS[0]}; echo "cost exit=$rc"; [ "$rc" -eq 0 ] || return 1
  make -s gcp-usage-check | tail -1; rc=${PIPESTATUS[0]}; echo "usage exit=$rc"; [ "$rc" -eq 0 ]
}
gates || { echo "gates failed before $arm $set: no chat asked"; exit 4; }
cd "$REPO/services/semantic-agent" || exit 1
setarg=(); [ "$set" != frozen ] && setarg=(--set "$set")
thinking=$mode; [ "$mode" = DEFAULT ] && thinking=
echo "start $(date -u +%FT%H:%MZ) $arm $mode $set k=$runs"
BET_DATA_AGENT_THINKING=$thinking GCP_PROJECT=pplk8s-lab-001 DBT_DBNAME=dbt_dev DBT_HOST=localhost DBT_PORT=5433 \
  uv run --quiet python ../../docs/research/semantic-bet/probes/328_mcp_live.py \
  --agent 354_data_agent.py --arm "$arm" "${setarg[@]}" --runs "$runs" --requests 700 --minutes 110
rc=$?
echo "pass exit=$rc $(date -u +%FT%H:%MZ)"
gates
exit $rc
