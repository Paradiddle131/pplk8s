#!/usr/bin/env bash
# Run EL Factory lite as a plain container next to the Compose services
# (Phase 1; from Phase 2 it runs in the kind cluster). Usage: up | down
set -euo pipefail

NAME=pplk8s-el-factory
PORT="${ELF_PORT:-8090}"

case "${1:-}" in
  up)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker run -d --name "$NAME" --network pplk8s -p "127.0.0.1:$PORT:8080" \
      -e WAREHOUSE_DSN=postgresql://warehouse:warehouse@warehouse:5432/warehouse \
      -e STORAGE_EMULATOR_HOST=http://gcs:4443 \
      ${PAGE_SIZE:+-e PAGE_SIZE="$PAGE_SIZE"} \
      "${ELF_IMAGE:?}" >/dev/null
    for _ in $(seq 30); do
      curl -sf "http://localhost:$PORT/healthz" >/dev/null && { echo "EL Factory on http://localhost:$PORT"; exit 0; }
      sleep 1
    done
    docker logs --tail 30 "$NAME" >&2
    echo "EL Factory did not become healthy" >&2
    exit 1
    ;;
  down)
    docker rm -f "$NAME" >/dev/null 2>&1 && echo "removed $NAME" || true
    ;;
  *)
    echo "usage: $0 up|down" >&2
    exit 2
    ;;
esac
