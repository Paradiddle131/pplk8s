#!/usr/bin/env bash
# Give the kind cluster the host's egress when the host reaches the internet only through an HTTPS
# proxy on its own loopback that intercepts TLS with its own CA (the cloud sandbox: HTTPS_PROXY on
# 127.0.0.1 and the Makefile's BUILD_CA). Without a proxy on loopback (a laptop) it does nothing.
# Idempotent; cluster-up.sh runs it, and every target that deploys into the cluster runs it first,
# because the proxy's port can change between sessions (#119).
#
# - A relay container `kind-egress` on the host network listens on the kind network's gateway and
#   pipes each connection to the proxy; Docker restarts it with the daemon.
# - Each node's containerd sends its HTTPS pulls through the relay (kind copies the host's
#   HTTPS_PROXY, 127.0.0.1, into the nodes, where it is the node itself) and trusts the proxy's CA;
#   docker.io pulls go to mirror.gcr.io first, as the host's Docker does, because Docker Hub
#   rate-limits the sandbox's shared address.
# - Pods that call out (workloads-up.sh) read the relay's address and CA from its labels.
set -euo pipefail
cd "$(dirname "$0")"

CLUSTER=pplk8s
RELAY=kind-egress
RELAY_PORT=3128
RELAY_IMAGE=python:3.13-slim
CA_IN_NODE=/usr/local/share/ca-certificates/egress-proxy.crt
DROP_IN=/etc/systemd/system/containerd.service.d/20-egress-proxy.conf

ca=${BUILD_CA-$(make -s --no-print-directory -C ../.. print-BUILD_CA)}
if ! [[ "${HTTPS_PROXY:-}" =~ ^http://127\.0\.0\.1:([0-9]+) ]] || [ -z "$ca" ]; then
  exit 0 # no loopback proxy: the nodes reach the internet the host's way
fi
upstream=${BASH_REMATCH[1]}
kind get clusters 2>/dev/null | grep -qx "$CLUSTER" || { echo "egress: no cluster $CLUSTER yet" >&2; exit 1; }
gateway=$(docker network inspect kind -f '{{json .IPAM.Config}}' | jq -r '[.[].Gateway | select(test("^[0-9.]+$"))][0]')
proxy="http://$gateway:$RELAY_PORT"
ca_sum=$(sha256sum "$ca" | cut -c1-16)

label() { docker inspect -f "{{index .Config.Labels \"pplk8s.egress.$1\"}}" "$RELAY" 2>/dev/null || true; }
if [ "$(docker inspect -f '{{.State.Running}}' "$RELAY" 2>/dev/null || true)" != true ] ||
  [ "$(label upstream)" != "$upstream" ] || [ "$(label proxy)" != "$proxy" ] || [ "$(label ca)" != "$ca" ]; then
  docker rm -f "$RELAY" >/dev/null 2>&1 || true
  docker run -d --restart=unless-stopped --network host --name "$RELAY" \
    --label "pplk8s.egress.upstream=$upstream" --label "pplk8s.egress.proxy=$proxy" --label "pplk8s.egress.ca=$ca" \
    "$RELAY_IMAGE" python -I -c '
import asyncio, sys

host, port, target = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()

async def relay(reader, writer):
    try:
        up_reader, up_writer = await asyncio.open_connection("127.0.0.1", target)
    except OSError:
        writer.close()
        return
    await asyncio.gather(pipe(reader, up_writer), pipe(up_reader, writer), return_exceptions=True)

async def main():
    server = await asyncio.start_server(relay, host, port)
    async with server:
        await server.serve_forever()

asyncio.run(main())
' "$gateway" "$RELAY_PORT" "$upstream" >/dev/null
  echo "egress: relay $RELAY on $proxy -> 127.0.0.1:$upstream"
fi

for node in $(kind get nodes --name "$CLUSTER"); do
  have=$(docker exec "$node" sh -c "cat $DROP_IN 2>/dev/null; sha256sum $CA_IN_NODE 2>/dev/null | cut -c1-16" || true)
  want=$(printf '[Service]\nEnvironment="HTTPS_PROXY=%s"\n%s' "$proxy" "$ca_sum")
  [ "$have" = "$want" ] && continue
  docker cp "$ca" "$node:$CA_IN_NODE"
  docker exec "$node" sh -c "update-ca-certificates >/dev/null 2>&1 && mkdir -p $(dirname "$DROP_IN") /etc/containerd/certs.d/docker.io"
  printf '[Service]\nEnvironment="HTTPS_PROXY=%s"\n' "$proxy" | docker exec -i "$node" cp /dev/stdin "$DROP_IN"
  printf '%s\n' 'server = "https://registry-1.docker.io"' '' '[host."https://mirror.gcr.io"]' '  capabilities = ["pull", "resolve"]' |
    docker exec -i "$node" cp /dev/stdin /etc/containerd/certs.d/docker.io/hosts.toml
  docker exec "$node" sh -c 'systemctl daemon-reload && systemctl restart containerd'
  echo "egress: $node pulls through $proxy"
done
