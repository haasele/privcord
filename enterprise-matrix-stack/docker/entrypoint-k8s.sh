#!/usr/bin/env bash
# Run inside Ubuntu container: clone repo and bootstrap k3d (Kubernetes) stack.
# Requires: -v /var/run/docker.sock:/var/run/docker.sock
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/haasele/privcord.git}"
CLONE_DIR="${CLONE_DIR:-/workspace/privcord}"
CLUSTER_NAME="${CLUSTER_NAME:-matrix-local}"

if [[ ! -d "$CLONE_DIR/.git" ]]; then
  echo "Cloning $REPO_URL into $CLONE_DIR ..."
  git clone --depth 1 "$REPO_URL" "$CLONE_DIR"
else
  echo "Repo already present at $CLONE_DIR; pulling latest."
  git config --global --add safe.directory "$CLONE_DIR" 2>/dev/null || true
  (cd "$CLONE_DIR" && git pull --rebase 2>/dev/null || git pull 2>/dev/null || true)
fi

STACK_DIR="$CLONE_DIR/enterprise-matrix-stack"
if [[ ! -f "$STACK_DIR/scripts/bootstrap-k3d.sh" ]]; then
  echo "Expected enterprise-matrix-stack at $STACK_DIR (missing bootstrap-k3d.sh)."
  exit 1
fi

cd "$STACK_DIR"
# So kubectl from inside Docker can reach k3d API server on the host
export DOCKER_GATEWAY="$(getent hosts host.docker.internal 2>/dev/null | awk '{print $1}' || ip route | awk '/default/ {print $3}')"
echo "Running k3d bootstrap (cluster: $CLUSTER_NAME) ..."
# Pass --recreate if bootstrap supports it (this repo); omit for upstream clone.
RECREATE_ARGS=""
if grep -q -- '--recreate' scripts/bootstrap-k3d.sh 2>/dev/null; then
  RECREATE_ARGS="--recreate"
fi
./scripts/bootstrap-k3d.sh $RECREATE_ARGS --build-image --cluster-name "$CLUSTER_NAME"

export KUBECONFIG="$(k3d kubeconfig write "$CLUSTER_NAME")"
# From inside Docker, 0.0.0.0/127.0.0.1 in kubeconfig is the container, not the host. Use host gateway so kubectl works.
if [[ -f "$KUBECONFIG" ]]; then
  HOST_IP="$(getent hosts host.docker.internal 2>/dev/null | awk '{print $1}' || ip route | awk '/default/ {print $3}')"
  if [[ -n "$HOST_IP" ]]; then
    sed -i "s|https://0.0.0.0:|https://${HOST_IP}:|g; s|https://127.0.0.1:|https://${HOST_IP}:|g" "$KUBECONFIG"
  fi
fi
echo ""
echo "Stack is running in Kubernetes (k3d). In this shell:"
echo "  kubectl get pods -n matrix-stack"
echo "Port 8443 on host is mapped to k3d loadbalancer (HTTPS)."
if [[ "${KEEP_ALIVE:-1}" == "1" ]]; then
  echo "Dropping to a shell (exit to stop). Cluster persists on host."
  exec bash
fi
