#!/usr/bin/env bash
# `make gcp-guardrails-check` (#205): read the lab project's stops back from the project itself, read-only.
# Fails (exit 1) when
#   - BigQuery's daily query quota, for the project or per user, is above free-path.yaml's cap or unlimited;
#   - an enabled API is neither on the free path nor one GCP turns on by itself (free-path.yaml `implicit`),
#     the sign of a billable service beyond the free path;
#   - Firestore holds more than its one free database, or a database with point-in-time recovery on;
#   - this machine's `bq` default byte cap (~/.bigqueryrc) is above the per-job cap.
# Cloud Run and the Agent Platform have no cap to read yet: Cloud Run's API is off until #209 sets its
# instance limits, and the Agent Platform's API is on the paid list, so `make gcp-validate` refuses it.
set -euo pipefail
: "${GCP_PROJECT:?GCP_PROJECT is unset: the gcp- targets act on the lab project and need its id (platform/gcp/README.md)}"
here=$(cd "$(dirname "$0")" && pwd)
token=${GOOGLE_OAUTH_ACCESS_TOKEN:-$(gcloud auth print-access-token 2>/dev/null || true)}
get() { curl -fsS -H "Authorization: Bearer $token" "$1"; }

quotas=$(get "https://cloudquotas.googleapis.com/v1/projects/$GCP_PROJECT/locations/global/services/bigquery.googleapis.com/quotaInfos?pageSize=200")
enabled=$(gcloud services list --enabled --project="$GCP_PROJECT" --format='value(config.name)')
databases=$(get "https://firestore.googleapis.com/v1/projects/$GCP_PROJECT/databases" 2>/dev/null || echo '{}')
bqrc=$(cat "$HOME/.bigqueryrc" 2>/dev/null || true)

QUOTAS=$quotas ENABLED=$enabled DATABASES=$databases BQRC=$bqrc \
  uv run --no-project --quiet --with pyyaml==6.0.2 python - "$here/free-path.yaml" "$GCP_PROJECT" <<'PY'
import json, os, re, sys
import yaml

spec = yaml.safe_load(open(sys.argv[1]))
project = sys.argv[2]
caps = spec["caps"]
bad, ok = [], []

infos = {q["quotaId"]: q for q in json.loads(os.environ["QUOTAS"]).get("quotaInfos", [])}
for quota in ("QueryUsagePerDay", "QueryUsagePerUserPerDay"):
    values = [int(d["details"]["value"]) for d in infos.get(quota, {}).get("dimensionsInfos", [])]
    if not values:
        bad.append(f"{quota}: not readable")
    elif any(v < 0 or v > caps["bigquery_query_mib_per_day"] for v in values):
        bad.append(f"{quota}: {values} MiB a day, above the cap of {caps['bigquery_query_mib_per_day']} (or unlimited)")
    else:
        ok.append(f"{quota}: {max(values)} MiB a day")

allowed = {name for name, api in spec["apis"].items() if api.get("enable")} | set(spec.get("implicit") or {})
extra = sorted(set(os.environ["ENABLED"].split()) - allowed)
if extra:
    bad.append("enabled APIs off the free path: " + ", ".join(extra))
else:
    ok.append(f"{len(os.environ['ENABLED'].split())} enabled APIs, all on the free path")

dbs = json.loads(os.environ["DATABASES"] or "{}").get("databases", [])
if len(dbs) > 1:
    bad.append(f"Firestore: {len(dbs)} databases, one is free: {[d['name'] for d in dbs]}")
pitr = [d["name"] for d in dbs if d.get("pointInTimeRecoveryEnablement") == "POINT_IN_TIME_RECOVERY_ENABLED"]
if pitr:
    bad.append(f"Firestore: point-in-time recovery is billed, on for {pitr}")
if not (len(dbs) > 1 or pitr):
    ok.append(f"Firestore: {len(dbs)} database(s), no point-in-time recovery")

m = re.search(r"maximum_bytes_billed\s*=\s*(\d+)", os.environ["BQRC"])
if m and int(m.group(1)) > caps["bigquery_maximum_bytes_billed"]:
    bad.append(f"~/.bigqueryrc: maximum_bytes_billed {m.group(1)} is above {caps['bigquery_maximum_bytes_billed']}")
elif m:
    ok.append(f"~/.bigqueryrc: {int(m.group(1)) // 2**20} MiB a query")
else:
    ok.append("~/.bigqueryrc: no default byte cap on this machine (pass --maximum_bytes_billed to every bq query)")

for line in ok:
    print(f"gcp-guardrails-check: ok: {line}")
for line in bad:
    print(f"gcp-guardrails-check: FAIL: {line}", file=sys.stderr)
print(f"gcp-guardrails-check: {'FAIL' if bad else 'ok'}: {project}")
sys.exit(1 if bad else 0)
PY
