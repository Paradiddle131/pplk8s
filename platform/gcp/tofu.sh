#!/usr/bin/env bash
# OpenTofu on the lab project's root (platform/gcp/infra), for `make gcp-plan|gcp-up|gcp-down`.
# Usage: platform/gcp/tofu.sh plan|apply|destroy; IMAGES='{"semantic-agent": "<ref>", "dbt": "<ref>"}' names the
# Cloud Run workloads' images (below), else the deployed ones are kept.
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
# Quota preferences cannot be deleted: pass the BigQuery ones already on the project (the console's, #226,
# or an earlier gcp-up's), so infra/bigquery.tf imports them instead of creating a second one.
token=${GOOGLE_OAUTH_ACCESS_TOKEN:-$(gcloud auth print-access-token 2>/dev/null || true)}
existing=$(curl -fsS -H "Authorization: Bearer $token" \
  "https://cloudquotas.googleapis.com/v1/projects/$GCP_PROJECT/locations/global/quotaPreferences" |
  python3 -c 'import json, sys
prefs = json.load(sys.stdin).get("quotaPreferences", [])
print(json.dumps({p["quotaId"]: p["name"].rsplit("/", 1)[1] for p in prefs if p["service"] == "bigquery.googleapis.com"}))') ||
  { echo "tofu.sh: could not list the project's quota preferences" >&2; exit 1; }
vars+=(-var "existing_quota_preferences=$existing")
[ -n "${KILL_SWITCH_USD:-}" ] && vars+=(-var "kill_switch_usd=$KILL_SWITCH_USD")

# The Cloud Run workloads exist only while `images` names their images (infra/run.tf). IMAGES (a JSON map,
# `make gcp-workloads-up`) sets them; otherwise the images running now are read back from the Run Admin API,
# so a plain plan, apply or destroy keeps (or, for destroy, removes) what is deployed and never diffs it.
# Read live rather than from state: the API is the truth after a console change, and an absent workload
# (404) or a Run API not enabled yet (403 SERVICE_DISABLED) means no image; any other answer stops here,
# because guessing "none" would plan the workloads' removal.
if [ -z "${IMAGES:-}" ]; then
  deployed() { # $1: services|jobs, $2: name, $3: the images key; prints `"key": "image"` or nothing
    local body code
    body=$(curl -sS -w '\n%{http_code}' -H "Authorization: Bearer $token" \
      "https://run.googleapis.com/v2/projects/$GCP_PROJECT/locations/us-central1/$1/$2") || return 1
    code=${body##*$'\n'}
    body=${body%$'\n'*}
    case "$code" in
      200) python3 -c 'import json, sys
t = json.load(sys.stdin)["template"]
print(json.dumps(sys.argv[1]) + ": " + json.dumps(t.get("template", t)["containers"][0]["image"]))' "$3" <<<"$body" ;;
      404) ;;
      403) grep -q SERVICE_DISABLED <<<"$body" || { echo "tofu.sh: $1/$2: $body" >&2; return 1; } ;;
      *) echo "tofu.sh: $1/$2: HTTP $code: $body" >&2; return 1 ;;
    esac
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
