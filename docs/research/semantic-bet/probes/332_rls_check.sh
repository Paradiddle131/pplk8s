#!/usr/bin/env bash
# What it measures (Q7, live): whether a row access policy on bet_rls.orders filters rows read through a
# view, a table function and an authorized table function, for the identity the policy names (the caller).
# How to run (from the repo root, GCP_PROJECT set): bash docs/research/semantic-bet/probes/332_rls_check.sh
#   --print    prints each statement as it would run, with no call at all (offline);
#   --cleanup  drops the policy, both datasets and their contents.
# Live: make gcp-cost-check and make gcp-usage-check first (any non-zero exit stops it), a dry run before
# every statement, maximum_bytes_billed on every job, writes only in bet_rls and bet_rls_api (US).
# Reads probes/332_bet_rls.sql; the policy's grantee is SESSION_USER(), so one identity is enough.
set -euo pipefail

HERE="$(dirname "$0")"
SQL="$HERE/332_bet_rls.sql"
MODE="${1:-run}"
P="${GCP_PROJECT:-pplk8s-lab-001}"
CAP=10485760 # 10 MiB; the probe's tables hold six rows
BQ=(bq --project_id="$P" --location=US)
API="https://bigquery.googleapis.com/bigquery/v2/projects/$P"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

statements() { # one statement per line, newlines escaped, @ME@ replaced by $1
  python3 -I - "$SQL" "$1" <<'PY'
import re
import sys

text = re.sub(r"(?m)^--.*\n", "", open(sys.argv[1]).read())
for stmt in text.split("\n;\n"):
    stmt = stmt.strip().replace("@ME@", sys.argv[2])
    if stmt.strip(";"):
        print(stmt.replace("\\", "\\\\").replace("\n", "\\n"))
PY
}

if [ "$MODE" = --print ]; then
  statements 'serviceAccount:<SESSION_USER()>' | while IFS= read -r s; do printf '%b\n;\n' "$s"; done
  exit 0
fi

make gcp-cost-check
make gcp-usage-check

run() { # dry run, then the job with its cap
  "${BQ[@]}" query --use_legacy_sql=false --dry_run "$1" >/dev/null
  "${BQ[@]}" query --use_legacy_sql=false --maximum_bytes_billed="$CAP" --format=prettyjson "$1"
}

if [ "$MODE" = --cleanup ]; then
  run 'DROP ALL ROW ACCESS POLICIES ON bet_rls.orders' || true
  "${BQ[@]}" rm -r -f -d "$P:bet_rls_api"
  "${BQ[@]}" rm -r -f -d "$P:bet_rls"
  exit 0
fi

ME="$(run 'SELECT SESSION_USER() AS me' | python3 -I -c 'import json, sys; print(json.load(sys.stdin)[0]["me"])')"
case "$ME" in *.gserviceaccount.com) GRANTEE="serviceAccount:$ME" ;; *) GRANTEE="user:$ME" ;; esac
echo "caller: $ME"

statements "$GRANTEE" | while IFS= read -r stmt; do
  stmt="$(printf '%b' "$stmt")"
  echo "== $(head -1 <<<"$stmt")"
  case "$stmt" in
    "CREATE OR REPLACE ROW ACCESS POLICY"*)
      # Authorize the routine on bet_rls first (an access entry, which the dataset's creator may add).
      "${BQ[@]}" show --format=prettyjson "$P:bet_rls" | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
entry = {"routine": {"projectId": sys.argv[1], "datasetId": "bet_rls_api", "routineId": "orders_auth_tf"}}
d["access"] = [a for a in d.get("access", []) if a != entry] + [entry]
json.dump({"access": d["access"]}, open(sys.argv[2], "w"))' "$P" "$TMP"/bet_rls_access.json
      "${BQ[@]}" update --source "$TMP"/bet_rls_access.json "$P:bet_rls"
      # Check the permission, never attempt it blind (cloud rules): a missing one is a needs-user packet.
      curl -sS -X POST -H 'content-type: application/json' \
        -H "authorization: Bearer $(gcloud auth print-access-token 2>/dev/null || echo proxy-injected)" \
        -d '{"permissions": ["bigquery.rowAccessPolicies.create"]}' \
        "$API/datasets/bet_rls/tables/orders:testIamPermissions" | tee "$TMP"/bet_rls_perm.json
      grep -q 'bigquery.rowAccessPolicies.create' "$TMP"/bet_rls_perm.json || {
        echo 'bigquery.rowAccessPolicies.create not held on bet_rls.orders: stop, a needs-user packet' >&2
        exit 4
      }
      ;;
  esac
  run "$stmt"
done

make gcp-cost-check
make gcp-usage-check
