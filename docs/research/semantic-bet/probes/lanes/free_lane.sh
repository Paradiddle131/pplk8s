#!/usr/bin/env bash
# The free-model lane (owner, 2026-11-04T20:15Z: k = 1 first, then k = 3; 2026-11-05: spend the whole daily quota).
# Every pass the plan names, in order: each arm's frozen set, then its hard set, at k = 1; then the same at k = 3.
# A pass resumes from its log and skips itself (no canary, no request) once its log holds every run, so the lane
# can start every day from the top and spends the day's quota where the work is; the judge and a push after each.
# Run from anywhere: bash docs/research/semantic-bet/probes/lanes/free_lane.sh (needs make services-up and the agents fixture).
# Stops for the day once OpenRouter's free count reaches CAP (default 990 of 1,000: a pass checks its share before
# each case, so the last case may overrun it by its own calls), or on an anomaly (exit 1: a gate; exit 2: canary).
set -uo pipefail
REPO=$(cd "$(dirname "$0")/../../../../.." && pwd)
SA=$REPO/services/semantic-agent
S=${LANE_DIR:-${TMPDIR:-/tmp}/semantic-bet-lanes}; mkdir -p "$S"
CAP=${CAP:-990}
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
  local req=$left
  log "start $name: free count $u, --requests $req (about $est for a whole pass)"
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

# The Toolbox for custom-toolbox (#330): pinned and checksum-checked as probes/330_toolbox_check.sh does,
# started once, stopped when the lane leaves.
toolbox() {
  [[ -n ${TB_PID:-} ]] && return 0
  TB=${TOOLBOX_DIR:-$HOME/.local/toolbox}/toolbox-1.1.0
  if [[ ! -x $TB ]]; then
    mkdir -p "$(dirname "$TB")" && curl -sSfo "$TB.part" https://storage.googleapis.com/genai-toolbox/v1.1.0/linux/amd64/toolbox &&
      echo "17948e7538914320c4141d155bcf283c9a8c168c6abce09ae87837057899ba29  $TB.part" | sha256sum -c - >/dev/null &&
      chmod +x "$TB.part" && mv "$TB.part" "$TB" || { log "ANOMALY: Toolbox download or checksum failed"; exit 1; }
  fi
  "$TB" --config "$REPO/docs/research/semantic-bet/probes/330_tools.yaml" --port 5000 >"$S/toolbox.log" 2>&1 &
  TB_PID=$!; trap 'kill $TB_PID 2>/dev/null' EXIT; sleep 5
  kill -0 $TB_PID 2>/dev/null || { log "ANOMALY: Toolbox did not start ($S/toolbox.log)"; exit 1; }
}
# Lightdash for custom-lightdash (#363): the 15 GB image, so it comes last in each round and is skipped,
# not an anomaly, when it cannot start (disk, pull); LIGHTDASH=0 skips it.
lightdash() {
  [[ ${LIGHTDASH:-1} = 0 ]] && return 1
  curl -sf -o /dev/null "${LIGHTDASH_URL:-http://localhost:8080}/api/v1/health" && return 0
  cd "$REPO" && bash docs/research/semantic-bet/probes/334_lightdash.sh >"$S/lightdash-build.log" 2>&1 &&
    DBT_DBNAME=dbt_dev LIGHTDASH_WAREHOUSE_CATALOG=1 bash docs/research/semantic-bet/probes/334_lightdash_server.sh "" --keep \
      >"$S/lightdash.log" 2>&1 || { log "skip custom-lightdash: Lightdash did not start ($S/lightdash.log)"; return 1; }
}

# One round at k: each pass on the frozen set, then the hard set. The order is the plan's (profile § The
# completion plan): the arms the free model lacks first, the 15 GB Lightdash last.
round() {
  local k=$1
  pass "custom-hybrid frozen k=$k" 300 "${BE[@]}" --arms custom-hybrid --runs $k || exit 0
  pass "custom-hybrid hard k=$k" 150 "${BE[@]}" --arms custom-hybrid --set hard --runs $k || exit 0
  gcp_gate || { log "ANOMALY: GCP gate failed before native-mcp"; exit 1; }
  pass "native-mcp frozen k=$k" 530 "${LIVE[@]}" --runs $k || exit 0
  pass "native-mcp hard k=$k" 240 "${LIVE[@]}" --runs $k --set hard || exit 0
  gcp_gate || { log "ANOMALY: GCP gate failed after native-mcp"; exit 1; }
  toolbox
  pass "custom-toolbox frozen k=$k" 300 "${LIVE[@]}" --agent 330_toolbox_agent.py --runs $k || exit 0
  pass "custom-toolbox hard k=$k" 140 "${LIVE[@]}" --agent 330_toolbox_agent.py --runs $k --set hard || exit 0
  gcp_gate || { log "ANOMALY: GCP gate failed after custom-toolbox"; exit 1; }
  pass "baseline frozen k=$k" 450 "${BE[@]}" --arms baseline --runs $k || exit 0
  pass "baseline hard k=$k" 200 "${BE[@]}" --arms baseline --set hard --runs $k || exit 0
  [[ $k = 3 ]] && { pass "custom-metricflow frozen k=3" 400 "${BE[@]}" --arms custom-metricflow --runs 3 || exit 0; }
  if lightdash; then
    pass "custom-lightdash frozen k=$k" 400 "${LIVE[@]}" --agent 363_lightdash_agent.py --runs $k || exit 0
    pass "custom-lightdash hard k=$k" 180 "${LIVE[@]}" --agent 363_lightdash_agent.py --runs $k --set hard || exit 0
  fi
}
round 1
round 3
log "free lane: every pass is done at k = 3; free count $(used)"
