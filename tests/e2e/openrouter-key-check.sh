#!/usr/bin/env bash
# Fails fast when OpenRouter would refuse the agents' key (issues #116, #158): asks the endpoint that
# describes the key, which spends no model request, so a live check stops here instead of after a
# build, a deploy and a model turn. The cloud proxy adds the key itself, so an unset
# OPENROUTER_API_KEY passes there; OPENROUTER_API_BASE points the check at a stand-in.
# Run first by agent-eval.sh and agent-deploy-check.sh (`make agent-key-check`).
set -euo pipefail

base=${OPENROUTER_API_BASE:-https://openrouter.ai/api/v1}
auth=()
[ -z "${OPENROUTER_API_KEY:-}" ] || auth=(-H "Authorization: Bearer $OPENROUTER_API_KEY")
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${auth[@]}" "$base/key") || true
case $code in
  200) echo "ok: OpenRouter accepts the key ($base/key)" ;;
  401 | 403)
    echo "FAIL: OpenRouter refused the key (HTTP $code from $base/key): set OPENROUTER_API_KEY" >&2
    exit 1
    ;;
  *)
    echo "FAIL: OpenRouter's key check answered HTTP ${code:-none} ($base/key; 000: unreachable)" >&2
    exit 1
    ;;
esac
