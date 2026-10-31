#!/usr/bin/env bash
# OpenTofu on the lab project's root (platform/gcp/infra), for `make gcp-plan|gcp-up|gcp-down`.
# Usage: platform/gcp/tofu.sh plan|apply|destroy
# Refuses without GCP_PROJECT. Credentials: a cloud session's proxy-injected token (CLOUDSDK_AUTH_ACCESS_TOKEN,
# which the provider and the gcs backend read as GOOGLE_OAUTH_ACCESS_TOKEN), else application default
# credentials (Cloud Shell). State: gs://<project>-tfstate, created once by the owner (platform/gcp/README.md).
# A cloud session's credential can plan but not apply (it holds no IAM or API-enabling role, by design);
# the owner applies from Cloud Shell.
set -euo pipefail
cmd=${1:?usage: tofu.sh plan|apply|destroy}
case "$cmd" in plan | apply | destroy) ;; *) echo "tofu.sh: plan, apply or destroy, not $cmd" >&2; exit 2 ;; esac
: "${GCP_PROJECT:?GCP_PROJECT is unset: the gcp- targets act on the lab project and need its id (platform/gcp/README.md)}"
infra=$(cd "$(dirname "$0")/infra" && pwd)

if [ -n "${CLOUDSDK_AUTH_ACCESS_TOKEN:-}" ] && [ -z "${GOOGLE_OAUTH_ACCESS_TOKEN:-}" ]; then
  export GOOGLE_OAUTH_ACCESS_TOKEN=$CLOUDSDK_AUTH_ACCESS_TOKEN
fi
vars=(-var "project=$GCP_PROJECT")
[ -n "${KILL_SWITCH_USD:-}" ] && vars+=(-var "kill_switch_usd=$KILL_SWITCH_USD")

tofu -chdir="$infra" init -input=false -reconfigure -backend-config="bucket=$GCP_PROJECT-tfstate" >/dev/null
# A plan reads only: no state lock, so a credential that can read the state bucket but not write it can plan.
[ "$cmd" = plan ] && vars+=(-lock=false)
tofu -chdir="$infra" "$cmd" -input=false "${vars[@]}"
