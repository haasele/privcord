#!/usr/bin/env bash
# Run K3s (no KIND) fully inside this container. Docker daemon only for building images.
# Requires: docker run --privileged; on cgroup v2 add -v /sys/fs/cgroup:/sys/fs/cgroup:rw --cgroupns=host
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/haasele/privcord.git}"
CLONE_DIR="${CLONE_DIR:-/workspace/privcord}"
K3S_KUBECONFIG="${K3S_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

# Start Docker daemon (for building images only)
if ! docker info &>/dev/null; then
  echo "Starting Docker daemon (for image builds)..."
  dockerd --storage-driver=vfs --exec-opt native.cgroupdriver=cgroupfs &
  for i in {1..30}; do
    if docker info &>/dev/null; then break; fi
    [[ $i -eq 30 ]] && { echo "Docker daemon did not start."; exit 1; }
    sleep 1
  done
  echo "Docker daemon ready."
fi

# Start K3s server in this container (no nested node - control plane runs here)
if [[ ! -f "$K3S_KUBECONFIG" ]]; then
  echo "Starting K3s server in this container..."
  mkdir -p /etc/rancher/k3s
  # Disable traefik/servicelb to avoid extra pods; use same ports as our stack
  k3s server --disable traefik --disable servicelb --write-kubeconfig-mode 644 &
  for i in {1..90}; do
    if [[ -f "$K3S_KUBECONFIG" ]] && kubectl --kubeconfig="$K3S_KUBECONFIG" get nodes &>/dev/null; then break; fi
    [[ $i -eq 90 ]] && { echo "K3s server did not become ready."; exit 1; }
    sleep 2
  done
  echo "K3s server ready."
else
  echo "K3s already has kubeconfig."
fi

export KUBECONFIG="${KUBECONFIG:-$K3S_KUBECONFIG}"

if [[ ! -d "$CLONE_DIR/.git" ]]; then
  echo "Cloning $REPO_URL into $CLONE_DIR ..."
  git clone --depth 1 "$REPO_URL" "$CLONE_DIR"
else
  echo "Repo already present at $CLONE_DIR; pulling latest."
  git config --global --add safe.directory "$CLONE_DIR" 2>/dev/null || true
  (cd "$CLONE_DIR" && git pull --rebase 2>/dev/null || git pull 2>/dev/null || true)
fi

STACK_DIR="$CLONE_DIR/enterprise-matrix-stack"
if [[ ! -f "$STACK_DIR/scripts/bootstrap-k3s.sh" ]]; then
  echo "Expected enterprise-matrix-stack at $STACK_DIR (missing bootstrap-k3s.sh)."
  exit 1
fi

cd "$STACK_DIR"
echo "Running K3s bootstrap (fully inside this container, no KIND)..."
./scripts/bootstrap-k3s.sh --build-image

echo ""
echo "Stack is running in K3s in this container. In this shell:"
echo "  kubectl get pods -n matrix-stack"
echo "To reach Synapse from your PC: docker exec -it <container> kubectl port-forward -n matrix-stack svc/synapse 8008:8008"
echo "Then use -p 8008:8008 when starting the container to access from host."
if [[ "${KEEP_ALIVE:-1}" == "1" ]]; then
  echo "Dropping to a shell (exit to stop). Cluster is isolated inside this container."
  exec bash
fi
