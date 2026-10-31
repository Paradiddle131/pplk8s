#!/usr/bin/env bash
# Create the kind cluster plus a local image registry (Artifact Registry stand-in).
# Follows https://kind.sigs.k8s.io/docs/user/local-registry/ and is idempotent.
set -euo pipefail
cd "$(dirname "$0")"

CLUSTER=pplk8s
NODE_IMAGE="${NODE_IMAGE:?set by the Makefile}"
REG_NAME=kind-registry
REG_PORT=5001
REG_IMAGE=registry:3

if [ "$(docker inspect -f '{{.State.Running}}' "$REG_NAME" 2>/dev/null || true)" != true ]; then
  docker rm -f "$REG_NAME" >/dev/null 2>&1 || true
  docker run -d --restart=unless-stopped -p "127.0.0.1:$REG_PORT:5000" \
    --network bridge --name "$REG_NAME" "$REG_IMAGE" >/dev/null
  echo "registry $REG_NAME listening on localhost:$REG_PORT"
fi

if kind get clusters | grep -qx "$CLUSTER"; then
  echo "cluster $CLUSTER already exists"
else
  config="$(mktemp)"
  trap 'rm -f "$config"' EXIT
  sed "s|__REPO__|$(cd ../.. && pwd)|g" cluster.yaml >"$config"
  # Hosts unlike a laptop (the cloud sandbox), asked of Docker, whose containers the nodes are: on
  # cgroup v1 the kubelet (1.35+) refuses to start unless told otherwise; where even a privileged
  # container may not lower its OOM score (no CAP_SYS_RESOURCE), containerd must not ask for the
  # negative scores it gives pod sandboxes.
  if [ "$(docker info --format '{{.CgroupVersion}}')" = 1 ]; then
    printf '%s\n' 'kubeadmConfigPatches:' '  - |' '    kind: KubeletConfiguration' '    failCgroupV1: false' >>"$config"
    echo "cgroup v1 host: kubelet failCgroupV1=false"
  fi
  if ! docker run --rm --privileged --entrypoint sh "$NODE_IMAGE" -c 'echo -999 >/proc/self/oom_score_adj' 2>/dev/null; then
    printf '%s\n' 'containerdConfigPatches:' '  - |-' '    [plugins."io.containerd.grpc.v1.cri"]' \
      '      restrict_oom_score_adj = true' >>"$config"
    echo "no CAP_SYS_RESOURCE: containerd restrict_oom_score_adj=true"
  fi
  kind create cluster --config "$config" --image "$NODE_IMAGE" --wait 120s
fi

# Inside a node, localhost is the node itself; alias localhost:5001 to the
# registry container so the same image reference works on host and in-cluster.
for node in $(kind get nodes --name "$CLUSTER"); do
  docker exec "$node" mkdir -p "/etc/containerd/certs.d/localhost:$REG_PORT"
  printf '[host."http://%s:5000"]\n' "$REG_NAME" |
    docker exec -i "$node" cp /dev/stdin "/etc/containerd/certs.d/localhost:$REG_PORT/hosts.toml"
done

if [ "$(docker inspect -f '{{json .NetworkSettings.Networks.kind}}' "$REG_NAME")" = null ]; then
  docker network connect kind "$REG_NAME"
fi

# kind's --wait covers only the control plane; workers must be Ready too.
kubectl --context "kind-$CLUSTER" wait node --all --for condition=Ready --timeout 120s

# Advertise the registry to tooling (KEP-1755).
kubectl --context "kind-$CLUSTER" apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:$REG_PORT"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

./join-services-network.sh
./egress-up.sh
