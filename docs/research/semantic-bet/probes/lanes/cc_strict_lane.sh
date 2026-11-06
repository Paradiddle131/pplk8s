#!/usr/bin/env bash
# The strict Claude Code lane (#387): one model on one setup, set by set, k = 3, through probes/387_cc_strict.py.
# Needs the setup's MCP server up (semantic_agent.mcp_server on 8765 with `387_cc_strict.py clients` as
# SEMANTIC_MCP_CLIENTS, or probes/387_mcp_guard.py on 8766) and, for scoring, the Compose warehouse with the fixture.
# Usage: bash docs/research/semantic-bet/probes/lanes/cc_strict_lane.sh SETUP MODEL [JOBS] [SET...]
set -uo pipefail
setup=$1 model=$2 jobs=${3:-5}
shift $(( $# >= 3 ? 3 : $# ))
sets=("${@:-hard-v2 frozen hard}")
read -r -a sets <<<"${sets[*]}"
cd "$(dirname "$0")/../../../../../services/semantic-agent" || exit 1
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
for s in "${sets[@]}"; do
  uv run --quiet python ../../docs/research/semantic-bet/probes/387_cc_strict.py run "$setup" "$model" "$s" --runs 3 --jobs "$jobs"
  status=$?
  echo "cc_strict_lane: $setup $model $s exit $status"
  [ "$status" -ne 0 ] && exit "$status"
done
