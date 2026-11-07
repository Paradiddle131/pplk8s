#!/usr/bin/env bash
# Load probes/330_tools.yaml into a pinned MCP Toolbox with no network and list what an MCP client sees (offline).
#
# What it measures: whether Toolbox 1.1.0 accepts the generated tools file, starts without any credential
# (the source uses `useClientOAuth`, so the caller's token is the only credential), and which tools, input
# schemas and descriptions it serves over MCP (stdio: initialize, then tools/list, then one tools/call with no
# token, which must be refused before any query).
# Run from the repo root:  bash docs/research/semantic-bet/probes/330_toolbox_check.sh
# Env: TOOLBOX_DIR (default ~/.local/toolbox), where toolbox-1.1.0 is kept; the script downloads it there
# once from Toolbox's release bucket and checks its SHA-256.
# Live: no. Toolbox runs in a container with `--network none`, so nothing can reach BigQuery or the lab project.
set -euo pipefail

VERSION=1.1.0
SHA256=17948e7538914320c4141d155bcf283c9a8c168c6abce09ae87837057899ba29
DIR=${TOOLBOX_DIR:-$HOME/.local/toolbox}
BIN=$DIR/toolbox-$VERSION
PROBES=$(cd "$(dirname "$0")" && pwd)

mkdir -p "$DIR"
if [[ ! -x $BIN ]]; then
  curl -sSfo "$BIN.part" "https://storage.googleapis.com/genai-toolbox/v$VERSION/linux/amd64/toolbox"
  echo "$SHA256  $BIN.part" | sha256sum -c - >/dev/null
  chmod +x "$BIN.part" && mv "$BIN.part" "$BIN"
fi
echo "$SHA256  $BIN" | sha256sum -c - >/dev/null
python3 "$PROBES/330_toolbox_tools.py" --check

requests=$(
  cat <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"bet-probe","version":"0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"daily_sales","arguments":{"start_date":"2026-10-01","end_date":"2026-10-02"}}}
EOF
)

# Keep stdin open briefly after the last request so the server answers before it sees EOF.
{ echo "$requests"; sleep 5; } | docker run --rm -i --network none \
  -v "$BIN:/toolbox:ro" -v "$PROBES/330_tools.yaml:/tools.yaml:ro" \
  debian:bookworm-slim /toolbox --config /tools.yaml --stdio --log-level WARN |
  python3 -c '
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line.startswith("{"):
        print("log:", line)
        continue
    msg = json.loads(line)
    if msg.get("id") == 1:
        info = msg["result"]["serverInfo"]
        print("initialize:", info["name"], info["version"], "protocol", msg["result"]["protocolVersion"])
    elif msg.get("id") == 2:
        tools = msg["result"]["tools"]
        print("tools/list:", len(tools), "tools")
        for tool in tools:
            schema = tool["inputSchema"]
            params = {k: v.get("type") for k, v in schema.get("properties", {}).items()}
            name, required, chars = tool["name"], schema.get("required"), len(tool["description"])
            print(f"  {name}: params {params}, required {required}, description {chars} chars")
    elif msg.get("id") == 3:
        print("tools/call without a token:", json.dumps(msg.get("error") or msg.get("result"))[:400])
'
