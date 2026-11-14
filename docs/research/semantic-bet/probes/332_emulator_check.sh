#!/usr/bin/env bash
# What it measures: which of probes/332_bet_rls.sql's statements the lab's BigQuery emulator
# (ghcr.io/goccy/bigquery-emulator:0.8.1) accepts, and what the four reads return there: a check of the
# SQL's syntax and of whether the offline lab can stand in for row policies at all, not of BigQuery.
# How to run (from the repo root): bash docs/research/semantic-bet/probes/332_emulator_check.sh
# Offline: a throwaway emulator container on 127.0.0.1:9052, removed at the end.
set -euo pipefail

SQL="$(dirname "$0")/332_bet_rls.sql"
PORT=9052
docker rm -f bet-rls-emu >/dev/null 2>&1 || true
docker run -d --rm --name bet-rls-emu -p 127.0.0.1:$PORT:9050 ghcr.io/goccy/bigquery-emulator:0.8.1 \
  --project=pplk8s-lab --port=9050 --grpc-port=9060 >/dev/null
trap 'docker rm -f bet-rls-emu >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 30); do curl -s -o /dev/null "localhost:$PORT/bigquery/v2/projects/pplk8s-lab/datasets" && break; sleep 1; done

# One statement through the jobs.query API; prints its rows or its error.
q() {
  python3 -I -c 'import json, sys; print(json.dumps({"query": sys.stdin.read(), "useLegacySql": False}))' |
    curl -s -X POST "localhost:$PORT/bigquery/v2/projects/pplk8s-lab/queries" -H 'content-type: application/json' -d @- |
    python3 -I -c 'import json, sys
r = json.load(sys.stdin)
names = [f["name"] for f in r.get("schema", {}).get("fields", [])]
if r.get("error"): print("  error:", r["error"]["message"][:200])
else: print("  ok")
for row in r.get("rows", []): print("  ", dict(zip(names, [c["v"] for c in row["f"]])))'
}

# The emulator has no CREATE SCHEMA ... OPTIONS path worth testing; plain CREATE SCHEMA stands in.
python3 -I - "$SQL" <<'PY' | while IFS= read -r stmt; do
import re
import sys

text = re.sub(r"(?m)^--.*\n", "", open(sys.argv[1]).read())
for stmt in text.split("\n;\n"):
    stmt = stmt.strip().replace("'@ME@'", "'serviceAccount:probe@example.iam.gserviceaccount.com'")
    stmt = re.sub(r" OPTIONS \(location = 'US'\)", "", stmt).replace("IF NOT EXISTS ", "")
    if stmt.strip(";"):
        print(stmt.replace("\\", "\\\\").replace("\n", "\\n"))
PY
  printf '== %s\n' "$(printf '%b' "$stmt" | head -1)"
  printf '%b' "$stmt" | q
done
