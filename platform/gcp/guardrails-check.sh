#!/usr/bin/env bash
# `make gcp-guardrails-check` (#205): read the lab project's stops back from the project itself, read-only.
# Fails (exit 1) when
#   - BigQuery's daily query quota, for the project or per user, is above free-path.yaml's cap or unlimited;
#   - an enabled API is neither on the free path nor one GCP turns on by itself (free-path.yaml `implicit`),
#     the sign of a billable service beyond the free path;
#   - Firestore holds more than its one free database, or a database with point-in-time recovery on;
#   - this machine's `bq` default byte cap (~/.bigqueryrc) is above the per-job cap;
#   - a Cloud Run service (us-central1) keeps an instance warm, may scale past `caps.cloud_run_max_instances`,
#     bills CPU outside requests, turns invoker IAM off or grants a public member; a Job runs more than one
#     task or attempt per run (#209);
#   - the project holds more Cloud Scheduler jobs than `caps.cloud_scheduler_jobs` (the billing account's free 3);
#   - a Cloud Run regional quota in us-central1, found by its metric, is above `caps.cloud_run_regional_quotas`,
#     unlimited or not readable (#209).
# Cloud Run and Cloud Scheduler are skipped, with a note, while their API is not enabled.
# The Agent Platform has no cap to read: its API is on the paid list, so `make gcp-validate` refuses it.
set -euo pipefail
: "${GCP_PROJECT:?GCP_PROJECT is unset: the gcp- targets act on the lab project and need its id (platform/gcp/README.md)}"
here=$(cd "$(dirname "$0")" && pwd)
token=${GOOGLE_OAUTH_ACCESS_TOKEN:-$(gcloud auth print-access-token 2>/dev/null || true)}
get() { curl -fsS -H "Authorization: Bearer $token" "$1"; }

quotas=$(get "https://cloudquotas.googleapis.com/v1/projects/$GCP_PROJECT/locations/global/services/bigquery.googleapis.com/quotaInfos?pageSize=200")
enabled=$(gcloud services list --enabled --project="$GCP_PROJECT" --format='value(config.name)')
databases=$(get "https://firestore.googleapis.com/v1/projects/$GCP_PROJECT/databases" 2>/dev/null || echo '{}')
bqrc=$(cat "$HOME/.bigqueryrc" 2>/dev/null || true)

# A product's REST read as JSON, `{"disabled": true}` while its API is off; anything else fails the check.
read_api() {
  local body code
  body=$(curl -sS -w '\n%{http_code}' -H "Authorization: Bearer $token" "$1")
  code=${body##*$'\n'}
  body=${body%$'\n'*}
  case "$code" in
    200) printf '%s' "$body" ;;
    403) if grep -q SERVICE_DISABLED <<<"$body"; then echo '{"disabled": true}'; else echo "$1: $body" >&2; return 1; fi ;;
    *) echo "$1: HTTP $code: $body" >&2; return 1 ;;
  esac
}
run=https://run.googleapis.com/v2/projects/$GCP_PROJECT/locations/us-central1
services=$(read_api "$run/services")
jobs=$(read_api "$run/jobs")
# Each service's IAM policy, one JSON object per line.
policies=$(python3 -c 'import json, sys
for s in json.loads(sys.argv[1]).get("services", []):
    print(s["name"])' "$services" | while read -r name; do
  policy=$(read_api "https://run.googleapis.com/v2/$name:getIamPolicy") || exit 1
  printf '{"service": "%s", "policy": %s}\n' "$name" "$policy"
done)
schedules=$(read_api "https://cloudscheduler.googleapis.com/v1/projects/$GCP_PROJECT/locations/us-central1/jobs")
run_quotas=$(read_api "https://cloudquotas.googleapis.com/v1/projects/$GCP_PROJECT/locations/global/services/run.googleapis.com/quotaInfos?pageSize=200")

QUOTAS=$quotas ENABLED=$enabled DATABASES=$databases BQRC=$bqrc \
  SERVICES=$services JOBS=$jobs POLICIES=$policies SCHEDULES=$schedules RUN_QUOTAS=$run_quotas \
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

# Cloud Run (#209): request-billed services between 0 and the cap, private; Jobs one task, one attempt.
services = json.loads(os.environ["SERVICES"])
if services.get("disabled"):
    ok.append("Cloud Run: API not enabled, nothing to read")
else:
    cap = caps["cloud_run_max_instances"]
    for s in services.get("services", []):
        name = s["name"].rsplit("/", 1)[1]
        scaling = s["template"].get("scaling", {})
        low, high = scaling.get("minInstanceCount", 0), scaling.get("maxInstanceCount")
        idle = [c.get("resources", {}).get("cpuIdle", False) for c in s["template"]["containers"]]
        if low:
            bad.append(f"Cloud Run {name}: {low} minimum instances bill while idle")
        if high is None or high > cap:
            bad.append(f"Cloud Run {name}: at most {high or 'the default 100'} instances, above the cap of {cap}")
        if not all(idle):
            bad.append(f"Cloud Run {name}: CPU billed outside requests (cpuIdle off)")
        if s.get("invokerIamDisabled"):
            bad.append(f"Cloud Run {name}: invoker IAM is off, so anyone may call it")
        if not (low or high is None or high > cap or not all(idle) or s.get("invokerIamDisabled")):
            ok.append(f"Cloud Run {name}: {low} to {high} instances, CPU only during requests, invoker IAM on")
    for line in filter(None, os.environ["POLICIES"].splitlines()):
        entry = json.loads(line)
        members = {m for b in entry["policy"].get("bindings", []) for m in b.get("members", [])}
        public = sorted(members & {"allUsers", "allAuthenticatedUsers"})
        name = entry["service"].rsplit("/", 1)[1]
        if public:
            bad.append(f"Cloud Run {name}: public members {public}")
        else:
            ok.append(f"Cloud Run {name}: {len(members)} IAM member(s), none public")
    for j in json.loads(os.environ["JOBS"]).get("jobs", []):
        name, t = j["name"].rsplit("/", 1)[1], j["template"]
        shape = (t.get("taskCount", 1), t.get("parallelism", 1), t["template"].get("maxRetries", 3))
        if shape != (1, 1, 0) and shape != (1, 0, 0):
            bad.append(f"Cloud Run Job {name}: tasks, parallelism, retries {shape}; the free-tier budget counts one instance per run")
        else:
            ok.append(f"Cloud Run Job {name}: one task, no retry, timeout {t['template'].get('timeout')}")

schedules = json.loads(os.environ["SCHEDULES"])
if schedules.get("disabled"):
    ok.append("Cloud Scheduler: API not enabled, nothing to read")
else:
    count = len(schedules.get("jobs", []))
    if count > caps["cloud_scheduler_jobs"]:
        bad.append(f"Cloud Scheduler: {count} jobs, above the cap of {caps['cloud_scheduler_jobs']} free per billing account")
    else:
        ok.append(f"Cloud Scheduler: {count} of {caps['cloud_scheduler_jobs']} free jobs (us-central1)")

# Cloud Run's regional quotas (#209), by metric: the us-central1 value, else the default that applies there.
run_quotas = json.loads(os.environ["RUN_QUOTAS"])
if services.get("disabled") or run_quotas.get("disabled"):
    ok.append("Cloud Run quotas: API not enabled, nothing to read")
else:
    infos = run_quotas.get("quotaInfos", [])
    for metric, cap in caps["cloud_run_regional_quotas"].items():
        values = []
        for q in infos:
            if q.get("metric") != metric or (cap.get("quota_id") and q.get("quotaId") != cap["quota_id"]):
                continue
            dims = q.get("dimensionsInfos", [])
            here = [d for d in dims if d.get("dimensions", {}).get("region") == "us-central1"]
            here = here or [d for d in dims if not d.get("dimensions", {}).get("region")
                            and "us-central1" in d.get("applicableLocations", ["us-central1"])]
            values += [(q["quotaId"], int(d["details"]["value"])) for d in here]
        if not values:
            bad.append(f"Cloud Run quota {metric}: not readable in us-central1")
        elif any(v < 0 or v > cap["value"] for _, v in values):
            bad.append(f"Cloud Run quota {metric}: {values} {cap['unit']}, above the cap of {cap['value']} (or unlimited)")
        else:
            ok.append(f"Cloud Run quota {metric}: {values} {cap['unit']}, cap {cap['value']}")

for line in ok:
    print(f"gcp-guardrails-check: ok: {line}")
for line in bad:
    print(f"gcp-guardrails-check: FAIL: {line}", file=sys.stderr)
print(f"gcp-guardrails-check: {'FAIL' if bad else 'ok'}: {project}")
sys.exit(1 if bad else 0)
PY
