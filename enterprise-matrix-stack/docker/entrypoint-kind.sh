#!/usr/bin/env bash
# Run KIND (Kubernetes) fully inside this container. No host Docker socket.
# Requires: docker run --privileged (Docker-in-Docker).
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/haasele/privcord.git}"
CLONE_DIR="${CLONE_DIR:-/workspace/privcord}"
CLUSTER_NAME="${CLUSTER_NAME:-matrix-local}"

# Start Docker daemon (Docker-in-Docker). On cgroup v2 hosts, run the container with:
#   -v /sys/fs/cgroup:/sys/fs/cgroup:rw
# so the inner Docker/KIND can use cgroups.
if ! docker info &>/dev/null; then
  echo "Starting Docker daemon inside container..."
  # cgroupfs driver often works better than systemd when nesting; vfs avoids overlay issues
  dockerd --storage-driver=vfs --exec-opt native.cgroupdriver=cgroupfs &
  for i in {1..30}; do
    if docker info &>/dev/null; then break; fi
    [[ $i -eq 30 ]] && { echo "Docker daemon did not start."; exit 1; }
    sleep 1
  done
  echo "Docker daemon ready."
fi

if [[ ! -d "$CLONE_DIR/.git" ]]; then
  echo "Cloning $REPO_URL into $CLONE_DIR ..."
  git clone --depth 1 "$REPO_URL" "$CLONE_DIR"
else
  echo "Repo already present at $CLONE_DIR; pulling latest."
  git config --global --add safe.directory "$CLONE_DIR" 2>/dev/null || true
  (cd "$CLONE_DIR" && git pull --rebase 2>/dev/null || git pull 2>/dev/null || true)
fi

STACK_DIR="$CLONE_DIR/enterprise-matrix-stack"
if [[ ! -f "$STACK_DIR/scripts/bootstrap-kind.sh" ]]; then
  echo "Expected enterprise-matrix-stack at $STACK_DIR (missing bootstrap-kind.sh)."
  exit 1
fi

cd "$STACK_DIR"
echo "Running KIND bootstrap (cluster: $CLUSTER_NAME, fully inside this container) ..."
RECREATE_ARGS=""
if grep -q -- '--recreate' scripts/bootstrap-kind.sh 2>/dev/null; then
  RECREATE_ARGS="--recreate"
fi
./scripts/bootstrap-kind.sh $RECREATE_ARGS --build-image --cluster-name "$CLUSTER_NAME"

# Kubeconfig is already set by kind (default ~/.kube/config)
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
echo ""
echo "Stack is running in Kubernetes (KIND) inside this container. In this shell:"
echo "  kubectl get pods -n matrix-stack"
echo "To reach Synapse from your PC: docker exec -it <container> kubectl port-forward -n matrix-stack svc/synapse 8008:8008"
echo "Then open http://localhost:8008 on your PC (with -p 8008:8008 on docker run)."
if [[ "${KEEP_ALIVE:-1}" == "1" ]]; then
  echo "Dropping to a shell (exit to stop). Cluster is isolated inside this container."
  exec bash
fi
