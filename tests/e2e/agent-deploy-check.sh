#!/usr/bin/env bash
# The semantic agent as a Cloud Run stand-in (issue #111, semantic/PLAN.md SL-2): builds the agents'
# fixture in dbt_dev, deploys the workloads namespace with the agent reading dbt_dev, then asks it one
# metric question through a port-forwarded Service and asserts the answer, the tools it took, and its
# session in the metadata DB's agent_sessions database.
# Live: spends one model turn of the free tier (the key from OPENROUTER_API_KEY or the cloud network secret).
# Behind a TLS-intercepting HTTPS proxy on the host's loopback (the cloud sandbox), the agent's model
# calls go through platform/kind/egress-up.sh's relay, which workloads-up.sh finds by itself.
# Expects `make cluster-up`; `make agent-deploy-check` runs the key check, services-up and push first.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
K=(kubectl --context kind-pplk8s -n workloads)
OUT=${TMPDIR:-/tmp}/pplk8s-agent-deploy-check
LOCAL_PORT=18080
QUESTION="What was net revenue on 2 October 2026?"
EXPECTED=861.4 # exposed.net_sales_daily on dbt/dev/fixture.sql
fail() { echo "FAIL: $*" >&2; exit 1; }

pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
mkdir -p "$OUT"

# A key OpenRouter refuses fails only after the deploy and a model turn (issue #158): check it first.
"$REPO/tests/e2e/openrouter-key-check.sh"
DB=dbt_dev "$REPO/tests/e2e/agent-fixture.sh"

"$REPO/platform/kind/egress-up.sh" # behind the cloud's loopback proxy, pods reach it through the relay

AGENT_DBNAME=dbt_dev "$REPO/platform/k8s/workloads-up.sh" >"$OUT/workloads.log" 2>&1 ||
  { tail -30 "$OUT/workloads.log" >&2; fail "workloads-up.sh"; }
"${K[@]}" logs deploy/semantic-agent -c catalog | grep -q "17 public models, 54 metrics and 12 glossary terms" ||
  fail "the catalog initContainer did not write 17 public models, 54 metrics and 12 glossary terms"
echo "ok: workloads up; the agent's initContainer wrote its catalog for dbt_dev"

"${K[@]}" port-forward svc/semantic-agent "$LOCAL_PORT:80" >"$OUT/port-forward.log" 2>&1 &
pids+=($!)
url="http://127.0.0.1:$LOCAL_PORT"
for _ in $(seq 30); do curl -sf "$url/list-apps" >/dev/null 2>&1 && break; sleep 1; done
apps=$(curl -sf "$url/list-apps" | jq -c 'sort') || fail "no answer from the port-forwarded Service"
# One deployed agent: the text-to-SQL baseline is the eval's control, never served (semantic/PLAN.md SL-5).
[ "$apps" = '["semantic_agent"]' ] || fail "apps: expected semantic_agent only, got $apps"
echo "ok: the Service serves $apps"

session="deploy-check-$(date -u +%Y%m%dT%H%M%S)"
curl -sf -X POST "$url/apps/semantic_agent/users/check/sessions/$session" -H 'content-type: application/json' -d '{}' >/dev/null ||
  fail "could not create a session"
jq -n --arg s "$session" --arg q "$QUESTION" \
  '{app_name: "semantic_agent", user_id: "check", session_id: $s, new_message: {role: "user", parts: [{text: $q}]}}' |
  curl -sf -X POST "$url/run" -H 'content-type: application/json' -d @- >"$OUT/run.json" || fail "/run failed"
tools=$(jq -r '[.[] | .content.parts[]? | .functionCall.name // empty] | join(",")' "$OUT/run.json")
answer=$(jq -r '[.[] | .content.parts[]? | select(.thought != true) | .text // empty] | last' "$OUT/run.json")
echo "tools: $tools"
echo "answer: $answer"
[[ ",$tools," == *",query_metrics,"* ]] || fail "the agent never called query_metrics"
[[ "$answer" == *"$EXPECTED"* ]] || fail "the answer does not carry $EXPECTED"
echo "ok: the agent answered $EXPECTED through query_metrics"

events=$(docker compose -f "$REPO/platform/compose/compose.yaml" exec -T metadata-db \
  psql -U agent_sessions -d agent_sessions -qAt -c "select count(*) from events where session_id = '$session'")
[ "${events:-0}" -gt 0 ] || fail "session $session has no events in agent_sessions"
echo "ok: session $session and its $events events are in agent_sessions"

audited=$(docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
  psql -U warehouse -d dbt_dev -qAt -c "select count(*) from ops.agent_queries
    where session_id = '$session' and agent = 'semantic_agent' and tool = 'query_metrics' and rows_returned > 0")
[ "${audited:-0}" -gt 0 ] || fail "session $session has no query_metrics row in ops.agent_queries"
echo "ok: $audited query_metrics call(s) of session $session are audited in ops.agent_queries"
echo "PASS: agent deploy check"
