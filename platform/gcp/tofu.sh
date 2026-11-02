#!/usr/bin/env bash
# OpenTofu on the lab project's root (platform/gcp/infra), for `make gcp-plan|gcp-up|gcp-down`.
# Usage: platform/gcp/tofu.sh plan|apply|destroy; IMAGES='{"semantic-agent": "<ref>", "dbt": "<ref>"}' names the
# Cloud Run workloads' images (below), else the deployed ones are kept; ALERT_EMAIL=<address> picks where the
# freshness alert goes, else the signed-in gcloud account's.
# Refuses without GCP_PROJECT. Credentials, as GOOGLE_OAUTH_ACCESS_TOKEN (read by the provider and the gcs
# backend), first that holds: one already set; a cloud session's proxy-injected token
# (CLOUDSDK_AUTH_ACCESS_TOKEN); a short-lived token of a signed-in gcloud account ($GCP_ACCOUNT, default the
# active one: a laptop terminal or Cloud Shell, no application-default login needed); else application
# default credentials. State: gs://<project>-tfstate, created once by the owner (platform/gcp/README.md).
# A cloud session's credential can plan but not apply (it holds no IAM or API-enabling role, by design);
# the owner applies from their own signed-in shell.
set -euo pipefail
cmd=${1:?usage: tofu.sh plan|apply|destroy}
case "$cmd" in plan | apply | destroy) ;; *) echo "tofu.sh: plan, apply or destroy, not $cmd" >&2; exit 2 ;; esac
: "${GCP_PROJECT:?GCP_PROJECT is unset: the gcp- targets act on the lab project and need its id (platform/gcp/README.md)}"
infra=$(cd "$(dirname "$0")/infra" && pwd)

if [ -z "${GOOGLE_OAUTH_ACCESS_TOKEN:-}" ]; then
  if [ -n "${CLOUDSDK_AUTH_ACCESS_TOKEN:-}" ]; then
    export GOOGLE_OAUTH_ACCESS_TOKEN=$CLOUDSDK_AUTH_ACCESS_TOKEN
  elif command -v gcloud >/dev/null; then
    account=${GCP_ACCOUNT:-$(gcloud config get-value account 2>/dev/null)}
    if [ -n "$account" ]; then
      GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token --account="$account")
      export GOOGLE_OAUTH_ACCESS_TOKEN
      echo "tofu.sh: acting on $GCP_PROJECT as $account (GCP_ACCOUNT=<account> picks another)"
    fi
  fi
fi
vars=(-var "project=$GCP_PROJECT")
# Quota preferences cannot be deleted: pass the ones already on the project (the console's, #226, or an earlier
# gcp-up's) as `<service>/<quota id>` => name, global or in us-central1, so infra/bigquery.tf (BigQuery's) and
# infra/run.tf (Cloud Run's) import them instead of creating a second one.
token=${GOOGLE_OAUTH_ACCESS_TOKEN:-$(gcloud auth print-access-token 2>/dev/null || true)}
existing=$(curl -fsS -H "Authorization: Bearer $token" \
  "https://cloudquotas.googleapis.com/v1/projects/$GCP_PROJECT/locations/global/quotaPreferences" |
  python3 -c 'import json, sys
prefs = json.load(sys.stdin).get("quotaPreferences", [])
print(json.dumps({p["service"] + "/" + p["quotaId"]: p["name"].rsplit("/", 1)[1] for p in prefs
                  if p.get("dimensions", {}).get("region", "us-central1") == "us-central1"}))') ||
  { echo "tofu.sh: could not list the project's quota preferences" >&2; exit 1; }
vars+=(-var "existing_quota_preferences=$existing")

# A product's REST read: the body on 200, `$2` (a default) on 404 or while its API is off (403 SERVICE_DISABLED),
# and a failure on anything else, since guessing the default there would plan a removal.
read_or() {
  local body code
  body=$(curl -sS -w '\n%{http_code}' -H "Authorization: Bearer $token" "$1") || return 1
  code=${body##*$'\n'}
  body=${body%$'\n'*}
  case "$code" in
    200) printf '%s' "$body" ;;
    404) printf '%s' "$2" ;;
    403) if grep -q SERVICE_DISABLED <<<"$body"; then printf '%s' "$2"; else echo "tofu.sh: $1: $body" >&2; return 1; fi ;;
    *) echo "tofu.sh: $1: HTTP $code: $body" >&2; return 1 ;;
  esac
}

# The `ops` tables that exist now (dbt's run-operations create them): access.yaml's table grants apply to these.
ops=$(read_or "https://bigquery.googleapis.com/bigquery/v2/projects/$GCP_PROJECT/datasets/ops/tables?maxResults=1000" '{}') ||
  { echo "tofu.sh: could not list the ops dataset's tables" >&2; exit 1; }
ops_tables=$(python3 -c 'import json, sys
print(json.dumps(sorted(t["tableReference"]["tableId"] for t in json.load(sys.stdin).get("tables", []))))' <<<"$ops")
vars+=(-var "existing_ops_tables=$ops_tables")

# The freshness alert's address (infra/monitoring.tf), never committed: ALERT_EMAIL, else the signed-in gcloud
# account (a person, not a service account), else the address of the channel deployed now, so a cloud session's
# plan (no gcloud account) keeps it; with none, a plan has no channel and warns.
alert_email=${ALERT_EMAIL:-}
if [ -z "$alert_email" ] && command -v gcloud >/dev/null; then
  alert_email=${GCP_ACCOUNT:-$(gcloud config get-value account 2>/dev/null || true)}
  case "$alert_email" in *.gserviceaccount.com) alert_email= ;; esac
fi
if [ -z "$alert_email" ]; then
  channels=$(read_or "https://monitoring.googleapis.com/v3/projects/$GCP_PROJECT/notificationChannels?filter=type%3D%22email%22" '{}') ||
    { echo "tofu.sh: could not read the alert's notification channel" >&2; exit 1; }
  alert_email=$(python3 -c 'import json, sys
print(next((c["labels"]["email_address"] for c in json.load(sys.stdin).get("notificationChannels", [])
            if c.get("displayName") == "pplk8s lab owner"), ""))' <<<"$channels")
fi
[ -n "$alert_email" ] && vars+=(-var "alert_email=$alert_email")
[ -n "${KILL_SWITCH_USD:-}" ] && vars+=(-var "kill_switch_usd=$KILL_SWITCH_USD")

# The Cloud Run workloads exist only while `images` names their images (infra/run.tf). IMAGES (a JSON map,
# `make gcp-workloads-up`) sets them; otherwise the images running now are read back from the Run Admin API,
# so a plain plan, apply or destroy keeps (or, for destroy, removes) what is deployed and never diffs it.
# Read live rather than from state: the API is the truth after a console change, and an absent workload
# (404) or a Run API not enabled yet (403 SERVICE_DISABLED) means no image; any other answer stops here,
# because guessing "none" would plan the workloads' removal.
if [ -z "${IMAGES:-}" ]; then
  deployed() { # $1: services|jobs, $2: name, $3: the images key; prints `"key": "image"` or nothing
    local body
    body=$(read_or "https://run.googleapis.com/v2/projects/$GCP_PROJECT/locations/us-central1/$1/$2" '') || return 1
    [ -z "$body" ] || python3 -c 'import json, sys
t = json.load(sys.stdin)["template"]
print(json.dumps(sys.argv[1]) + ": " + json.dumps(t.get("template", t)["containers"][0]["image"]))' "$3" <<<"$body"
  }
  if ! agent=$(deployed services semantic-agent semantic-agent) || ! dbt=$(deployed jobs dbt-build dbt); then
    echo "tofu.sh: could not read the deployed Cloud Run images; set IMAGES to name them" >&2
    exit 1
  fi
  IMAGES="{$agent${agent:+${dbt:+, }}$dbt}"
  echo "tofu.sh: images deployed now: $IMAGES"
fi
vars+=(-var "images=$IMAGES")

tofu -chdir="$infra" init -input=false -reconfigure -backend-config="bucket=$GCP_PROJECT-tfstate" >/dev/null
# A plan reads only: no state lock, so a credential that can read the state bucket but not write it can plan.
[ "$cmd" = plan ] && vars+=(-lock=false)
tofu -chdir="$infra" "$cmd" -input=false "${vars[@]}"
