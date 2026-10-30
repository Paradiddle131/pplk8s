#!/bin/bash
# Start Docker on a pplk8s-worker cloud VM (docs/agents/autopilot.md § Known conditions). Idempotent.
# The VM ships the engine but does not start the daemon, and anonymous Docker Hub pulls
# hit 429, so pulls go through Google's public mirror. cloud-setup.sh calls this, but the
# setup result is cached as a file snapshot that keeps no processes, so each run calls it
# again at start.
set -u

if ! command -v dockerd >/dev/null; then
  echo "docker: dockerd not installed"
  exit 1
fi

if [ ! -f /etc/docker/daemon.json ]; then
  mkdir -p /etc/docker
  echo '{"registry-mirrors": ["https://mirror.gcr.io"]}' >/etc/docker/daemon.json
fi

if ! docker info >/dev/null 2>&1; then
  # A restarted worker keeps the pid file of a daemon that is gone, and dockerd refuses to start over it.
  if [ -f /var/run/docker.pid ] && ! kill -0 "$(cat /var/run/docker.pid)" 2>/dev/null; then
    rm -f /var/run/docker.pid
  fi
  nohup dockerd >/tmp/dockerd.log 2>&1 &
  for _ in $(seq 30); do
    docker info >/dev/null 2>&1 && break
    sleep 1
  done
fi

# ghcr.io answers 403 to public images here (the proxy injects the account's own GHCR credential),
# so the uv stage the Dockerfiles name comes from Astral's Docker Hub copy, tagged under its ghcr name.
uv=$(grep -ho 'ghcr.io/astral-sh/uv:[0-9.]*' "$(dirname "$0")"/../../services/*/Dockerfile | sort -u)
for image in $uv; do
  docker image inspect "$image" >/dev/null 2>&1 ||
    { docker pull -q "astral/uv:${image##*:}" >/dev/null && docker tag "astral/uv:${image##*:}" "$image" && echo "docker: $image from astral/uv"; }
done

if docker info >/dev/null 2>&1; then
  echo "docker: ok (mirrors: $(docker info --format '{{.RegistryConfig.Mirrors}}'))"
else
  echo "docker: failed to start; see /tmp/dockerd.log"
  exit 1
fi
