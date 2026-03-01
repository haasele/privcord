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
  (cd "$CLONE_DIR" && git pull --rebase || true)
fi

STACK_DIR="$CLONE_DIR/enterprise-matrix-stack"
if [[ ! -f "$STACK_DIR/scripts/bootstrap-k3d.sh" ]]; then
  echo "Expected enterprise-matrix-stack at $STACK_DIR (missing bootstrap-k3d.sh)."
  exit 1
fi

cd "$STACK_DIR"
echo "Running k3d bootstrap (cluster: $CLUSTER_NAME) ..."
# Pass --recreate if bootstrap supports it (this repo); omit for upstream clone.
RECREATE_ARGS=""
if grep -q -- '--recreate' scripts/bootstrap-k3d.sh 2>/dev/null; then
  RECREATE_ARGS="--recreate"
fi
./scripts/bootstrap-k3d.sh $RECREATE_ARGS --build-image --cluster-name "$CLUSTER_NAME"

export KUBECONFIG="$(k3d kubeconfig write "$CLUSTER_NAME")"
echo ""
echo "Stack is running in Kubernetes (k3d). In this shell:"
echo "  kubectl get pods -n matrix-stack"
echo "Port 8443 on host is mapped to k3d loadbalancer (HTTPS)."
if [[ "${KEEP_ALIVE:-1}" == "1" ]]; then
  echo "Dropping to a shell (exit to stop). Cluster persists on host."
  exec bash
fi
