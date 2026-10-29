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
  nohup dockerd >/tmp/dockerd.log 2>&1 &
  for _ in $(seq 30); do
    docker info >/dev/null 2>&1 && break
    sleep 1
  done
fi

if docker info >/dev/null 2>&1; then
  echo "docker: ok (mirrors: $(docker info --format '{{.RegistryConfig.Mirrors}}'))"
else
  echo "docker: failed to start; see /tmp/dockerd.log"
  exit 1
fi
