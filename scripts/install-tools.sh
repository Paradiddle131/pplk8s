#!/usr/bin/env bash
# Install the pinned toolchain (kind, kubectl, helm, helm-diff, k9s; OpenTofu and tflint for platform/gcp/) into $BIN_DIR.
# Each artifact is verified against a checksum recorded here, so a fresh
# clone installs exactly the binaries the lab was built with.
set -euo pipefail

BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"

KIND_VERSION=v0.33.0
KIND_SHA256=aee6151561422756b764a4ae28e7f44cda5af5a9eead3cc9985112b1de8d8e0d
HELM_VERSION=v3.22.0
HELM_SHA256=1e4ab49e429626cf6c6958d914248b78c9730803c2751b87627e171dc800e7bb
HELM_DIFF_VERSION=v3.15.15
HELM_DIFF_SHA256=504e99410611daa70702362e1b10dc74929df8a912cb3f6b5d21d1ee9d0cb7d9
# kubectl within one minor of the cluster (kindest/node v1.36.4, PLAN.md D4); a distro or Docker
# Desktop kubectl further down PATH may be older, so ours must come first.
KUBECTL_VERSION=v1.36.5
KUBECTL_SHA256=33bc88a24c3b09cf55bfd59e6ca977881b61fc3f25ab65bc80c65b430248648e
K9S_VERSION=v0.51.0
K9S_SHA256=c3752ad51a5a4015a113819c4eeb6e55a4d0e4b8e652494797532f6fc8161dd7
# platform/gcp/ (semantic/PLAN.md SL-13): OpenTofu validates and applies the GCP root, tflint lints it.
TOFU_VERSION=1.10.7
TOFU_SHA256=c79bb458e7d7fa08c44be98b373ab3434647598808fc2a75dc9338aef7432ae6
TFLINT_VERSION=v0.59.1
TFLINT_SHA256=6108d84282292f11d793dc8038ce08fbc629dcd25324d6f13c63d8100b52e01f

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$BIN_DIR"

fetch() { # url sha256 dest
  curl -fsSL -o "$3" "$1"
  echo "$2  $3" | sha256sum --check --quiet
}

installed() { # name version-substring
  command -v "$1" >/dev/null && "$1" version 2>/dev/null | grep -q -- "$2"
}

if installed kind "$KIND_VERSION"; then echo "kind $KIND_VERSION already installed"; else
  fetch "https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-linux-amd64" "$KIND_SHA256" "$tmp/kind"
  install -m 0755 "$tmp/kind" "$BIN_DIR/kind"
  echo "installed kind $KIND_VERSION"
fi

if [ -x "$BIN_DIR/kubectl" ] && "$BIN_DIR/kubectl" version --client 2>/dev/null | grep -q -- "$KUBECTL_VERSION"; then
  echo "kubectl $KUBECTL_VERSION already installed"
else
  fetch "https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl" "$KUBECTL_SHA256" "$tmp/kubectl"
  install -m 0755 "$tmp/kubectl" "$BIN_DIR/kubectl"
  echo "installed kubectl $KUBECTL_VERSION"
fi

if installed helm "$HELM_VERSION"; then echo "helm $HELM_VERSION already installed"; else
  fetch "https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz" "$HELM_SHA256" "$tmp/helm.tgz"
  tar -xzf "$tmp/helm.tgz" -C "$tmp" linux-amd64/helm
  install -m 0755 "$tmp/linux-amd64/helm" "$BIN_DIR/helm"
  echo "installed helm $HELM_VERSION"
fi

# helm-diff is a helm plugin: unpack the verified release into helm's plugin dir.
helm_plugins="$("$BIN_DIR/helm" env HELM_PLUGINS 2>/dev/null || helm env HELM_PLUGINS)"
if grep -q "^version: \"\?${HELM_DIFF_VERSION#v}\"\?$" "$helm_plugins/diff/plugin.yaml" 2>/dev/null; then echo "helm-diff $HELM_DIFF_VERSION already installed"; else
  fetch "https://github.com/databus23/helm-diff/releases/download/$HELM_DIFF_VERSION/helm-diff-linux-amd64.tgz" "$HELM_DIFF_SHA256" "$tmp/helm-diff.tgz"
  mkdir -p "$helm_plugins"
  rm -rf "${helm_plugins:?}/diff"
  tar -xzf "$tmp/helm-diff.tgz" -C "$helm_plugins"
  echo "installed helm-diff $HELM_DIFF_VERSION"
fi

if installed k9s "$K9S_VERSION"; then echo "k9s $K9S_VERSION already installed"; else
  fetch "https://github.com/derailed/k9s/releases/download/$K9S_VERSION/k9s_Linux_amd64.tar.gz" "$K9S_SHA256" "$tmp/k9s.tgz"
  tar -xzf "$tmp/k9s.tgz" -C "$tmp" k9s
  install -m 0755 "$tmp/k9s" "$BIN_DIR/k9s"
  echo "installed k9s $K9S_VERSION"
fi

if installed tofu "v$TOFU_VERSION"; then echo "tofu $TOFU_VERSION already installed"; else
  fetch "https://github.com/opentofu/opentofu/releases/download/v$TOFU_VERSION/tofu_${TOFU_VERSION}_linux_amd64.zip" "$TOFU_SHA256" "$tmp/tofu.zip"
  python3 -m zipfile -e "$tmp/tofu.zip" "$tmp/tofu-dist"
  install -m 0755 "$tmp/tofu-dist/tofu" "$BIN_DIR/tofu"
  echo "installed tofu $TOFU_VERSION"
fi

if command -v tflint >/dev/null && tflint --version 2>/dev/null | grep -q -- "${TFLINT_VERSION#v}"; then echo "tflint $TFLINT_VERSION already installed"; else
  fetch "https://github.com/terraform-linters/tflint/releases/download/$TFLINT_VERSION/tflint_linux_amd64.zip" "$TFLINT_SHA256" "$tmp/tflint.zip"
  python3 -m zipfile -e "$tmp/tflint.zip" "$tmp/tflint-dist"
  install -m 0755 "$tmp/tflint-dist/tflint" "$BIN_DIR/tflint"
  echo "installed tflint $TFLINT_VERSION"
fi

case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "note: add $BIN_DIR to PATH" >&2 ;; esac
