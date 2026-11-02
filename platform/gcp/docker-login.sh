#!/usr/bin/env bash
# Sign Docker in to the lab's Artifact Registry host for `make gcp-images` (#289), with no credential helper:
# `gcloud auth configure-docker` from the Windows SDK registers `docker-credential-gcloud.cmd`, which Linux
# Docker on WSL cannot run, so a short-lived access token goes to `docker login` instead; either SDK works.
# Usage: platform/gcp/docker-login.sh <region>-docker.pkg.dev
# The token: a signed-in gcloud account's ($GCP_ACCOUNT, default the active one, as platform/gcp/tofu.sh picks it).
# It lives an hour: the login is redone on every `make gcp-images`, so a stale one never matters.
# A cloud session (CLOUDSDK_AUTH_ACCESS_TOKEN set) is refused: its egress proxy injects the real credential only
# for *.googleapis.com, never for <region>-docker.pkg.dev, so `docker login` there fails; push from the owner's shell.
set -euo pipefail
host=${1:?usage: docker-login.sh <region>-docker.pkg.dev}

if [ -n "${CLOUDSDK_AUTH_ACCESS_TOKEN:-}" ]; then
  echo "docker-login.sh: a cloud session's credential is injected only for *.googleapis.com, so it cannot sign Docker in to $host: run make gcp-images from the owner's shell" >&2
  exit 1
fi
command -v gcloud >/dev/null || { echo "docker-login.sh: gcloud is missing: install and sign in to it (platform/gcp/README.md)" >&2; exit 1; }
who=${GCP_ACCOUNT:-$(gcloud config get-value account 2>/dev/null)}
[ -n "$who" ] || { echo "docker-login.sh: no gcloud account is signed in: run gcloud auth login" >&2; exit 1; }
token=$(gcloud auth print-access-token --account="$who")
printf '%s' "$token" | docker login -u oauth2accesstoken --password-stdin "https://$host" >/dev/null
echo "docker-login.sh: Docker signed in to $host as $who (GCP_ACCOUNT=<account> picks another)"
