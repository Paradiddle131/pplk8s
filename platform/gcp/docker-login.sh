#!/usr/bin/env bash
# Sign Docker in to the lab's Artifact Registry host for `make gcp-images` (#289), with no credential helper:
# `gcloud auth configure-docker` from the Windows SDK registers `docker-credential-gcloud.cmd`, which Linux
# Docker on WSL cannot run, so a short-lived access token goes to `docker login` instead; either SDK works.
# Usage: platform/gcp/docker-login.sh <region>-docker.pkg.dev
# The token, as platform/gcp/tofu.sh picks it, first that holds: a cloud session's proxy-injected token
# (CLOUDSDK_AUTH_ACCESS_TOKEN); a signed-in gcloud account ($GCP_ACCOUNT, default the active one).
# It lives an hour: the login is redone on every `make gcp-images`, so a stale one never matters.
set -euo pipefail
host=${1:?usage: docker-login.sh <region>-docker.pkg.dev}

if [ -n "${CLOUDSDK_AUTH_ACCESS_TOKEN:-}" ]; then
  token=$CLOUDSDK_AUTH_ACCESS_TOKEN
  who="the session's injected credential"
else
  command -v gcloud >/dev/null || { echo "docker-login.sh: gcloud is missing: install and sign in to it (platform/gcp/README.md)" >&2; exit 1; }
  who=${GCP_ACCOUNT:-$(gcloud config get-value account 2>/dev/null)}
  [ -n "$who" ] || { echo "docker-login.sh: no gcloud account is signed in: run gcloud auth login" >&2; exit 1; }
  token=$(gcloud auth print-access-token --account="$who")
fi
printf '%s' "$token" | docker login -u oauth2accesstoken --password-stdin "https://$host" >/dev/null
echo "docker-login.sh: Docker signed in to $host as $who (GCP_ACCOUNT=<account> picks another)"
