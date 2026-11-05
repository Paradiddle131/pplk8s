#!/usr/bin/env bash
# The free-model lane, k = 1 first (owner, 2026-11-04T20:15Z): each pass in the plan's order on the frozen set,
# then the hard set, one run a case; the judge after each pass; commit and push after each pass.
# Run from anywhere: bash docs/research/semantic-bet/probes/lanes/free_lane.sh (needs make services-up and the agents fixture).
# Stops for the day once OpenRouter's free count reaches CAP (850 of 1,000), or on an anomaly (exit 2: canary).
set -uo pipefail
REPO=$(cd "$(dirname "$0")/../../../../.." && pwd)
SA=$REPO/services/semantic-agent
S=${LANE_DIR:-${TMPDIR:-/tmp}/semantic-bet-lanes}; mkdir -p "$S"
CAP=${CAP:-850}
export DBT_DBNAME=dbt_dev DBT_HOST=localhost DBT_PORT=5433 GCP_PROJECT=pplk8s-lab-001 BET_MCP_TOKEN=proxy-injected
used() { curl -sS https://openrouter.ai/api/v1/key -H "Authorization: Bearer x" |
  python3 -c "import json,sys; print(json.load(sys.stdin)['data']['free_model_daily_requests']['used'])"; }
log() { echo "$(date -u +%FT%H:%MZ) $*"; }
push() {
  cd "$REPO" && git add -A docs/research/semantic-bet &&
    git commit -q -m "feat(semantic-bet): free model, $1 (#333)" &&
    git pull -q --rebase --autostash origin claude/semantic-bet && git push -q origin claude/semantic-bet
  log "pushed: $1 ($(git -C "$REPO" log -1 --format=%h))"
}
judge() {
  local left=$((CAP - $(used))); [ $left -gt 10 ] || return 0
  cd "$SA" && flock "$S/openrouter.lock" uv run --quiet python -m semantic_agent.bet_eval --judge --requests $((left < 40 ? left : 40)) 2>&1 | grep -v Warning | tail -2
  cd "$SA" && flock "$S/openrouter.lock" uv run --quiet python -m semantic_agent.bet_eval --set hard --judge --requests 20 2>&1 | grep -v Warning | tail -2
}
# One pass: name, budget estimate, command (run from services/semantic-agent).
pass() {
  local name=$1 est=$2; shift 2
  local u; u=$(used); local left=$((CAP - u))
  if [ $left -lt 30 ]; then log "skip $name: free count $u of $CAP"; return 1; fi
  local req=$((left < est ? left : est))
  log "start $name: free count $u, --requests $req"
  cd "$SA" && flock "$S/openrouter.lock" "$@" --requests $req 2>&1 | grep -v -i "warning\|MetricEvaluatorRegistry" | tail -4
  local rc=${PIPESTATUS[0]}
  log "end $name: exit $rc, free count $(used)"
  [ $rc -eq 2 ] && { log "ANOMALY: $name missed its canary twice; lane stopped"; push "$name stopped at its canary"; exit 2; }
  judge
  push "$name, k = 1 (exit $rc)"
  return 0
}
gcp_gate() { cd "$REPO" && make -s gcp-cost-check | tail -2 && make -s gcp-usage-check | tail -1; }

BE=(uv run --quiet python -m semantic_agent.bet_eval)
LIVE=(uv run --quiet python ../../docs/research/semantic-bet/probes/328_mcp_live.py)
log "free lane: free count $(used)"
pass "custom-hybrid frozen" 450 "${BE[@]}" --arms custom-hybrid --runs 1 --minutes 120 || exit 0
pass "custom-hybrid hard" 220 "${BE[@]}" --arms custom-hybrid --set hard --runs 1 --minutes 60 || exit 0
gcp_gate || { log "ANOMALY: GCP gate failed before native-mcp"; exit 1; }
pass "native-mcp frozen" 500 "${LIVE[@]}" --runs 1 --minutes 120 || exit 0
pass "native-mcp hard" 250 "${LIVE[@]}" --runs 1 --set hard --minutes 60 || exit 0
gcp_gate || { log "ANOMALY: GCP gate failed after native-mcp"; exit 1; }
# custom-toolbox (#330) next, in the profile's order: a local Toolbox over HTTP, pinned and checksum-checked by
# probes/330_toolbox_check.sh's download step, stopped when the lane leaves.
TB=${TOOLBOX_DIR:-$HOME/.local/toolbox}/toolbox-1.1.0
if [[ ! -x $TB ]]; then
  mkdir -p "$(dirname "$TB")" && curl -sSfo "$TB.part" https://storage.googleapis.com/genai-toolbox/v1.1.0/linux/amd64/toolbox &&
    echo "17948e7538914320c4141d155bcf283c9a8c168c6abce09ae87837057899ba29  $TB.part" | sha256sum -c - >/dev/null &&
    chmod +x "$TB.part" && mv "$TB.part" "$TB" || { log "ANOMALY: Toolbox download or checksum failed"; exit 1; }
fi
"$TB" --config "$REPO/docs/research/semantic-bet/probes/330_tools.yaml" --port 5000 >"$S/toolbox.log" 2>&1 &
TB_PID=$!; trap 'kill $TB_PID 2>/dev/null' EXIT; sleep 5
kill -0 $TB_PID 2>/dev/null || { log "ANOMALY: Toolbox did not start ($S/toolbox.log)"; exit 1; }
pass "custom-toolbox frozen" 400 "${LIVE[@]}" --agent 330_toolbox_agent.py --runs 1 --minutes 120 || exit 0
pass "custom-toolbox hard" 200 "${LIVE[@]}" --agent 330_toolbox_agent.py --runs 1 --set hard --minutes 60 || exit 0
gcp_gate || { log "ANOMALY: GCP gate failed after custom-toolbox"; exit 1; }
log "free lane: done for the day at free count $(used)"
