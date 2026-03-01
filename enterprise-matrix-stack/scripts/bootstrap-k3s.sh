#!/usr/bin/env bash
# Bootstrap K3s running in the SAME container (no KIND/node nesting). Fully isolated.
# Prereqs: Docker daemon for building images; K3s server already started by entrypoint.
# Usage:
#   ./scripts/bootstrap-k3s.sh [--config ...] [--skip-create] [--build-image]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$STACK_DIR/.." && pwd)"
CONFIG="$STACK_DIR/config/example.yaml"
SKIP_CREATE=""
BUILD_IMAGE=""
GENERATED_DIR="$STACK_DIR/k8s/generated"
BASE_DIR="$STACK_DIR/k8s/base"
K3S_KUBECONFIG="${K3S_KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --config) CONFIG="$2"; shift 2 ;;
    --skip-create) SKIP_CREATE=1; shift ;;
    --build-image) BUILD_IMAGE=1; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "Using config: $CONFIG"

# Generate manifests
echo "Generating manifests..."
python3 "$SCRIPT_DIR/generate_manifests.py" --config "$CONFIG" --out "$GENERATED_DIR"
echo "Generated ConfigMaps in $GENERATED_DIR"

# K3s server is started by entrypoint; we just need kubeconfig
export KUBECONFIG="${KUBECONFIG:-$K3S_KUBECONFIG}"
if [[ ! -f "$KUBECONFIG" ]]; then
  echo "Kubeconfig not found at $KUBECONFIG. Is K3s server running?"
  exit 1
fi

# Wait for API server
echo "Waiting for API server..."
for i in {1..60}; do
  if kubectl get nodes &>/dev/null; then break; fi
  [[ $i -eq 60 ]] && { echo "API server did not become ready."; exit 1; }
  sleep 2
done

# Apply namespace first
kubectl apply -f "$BASE_DIR/namespace.yaml"

# Create deploy namespace from config if different
DEPLOY_NS="$(python3 -c "
import yaml
with open('$CONFIG') as f:
    c = yaml.safe_load(f)
print(c.get('deploy', {}).get('namespace', 'matrix-stack'))
" 2>/dev/null)"
if [[ -n "$DEPLOY_NS" ]] && [[ "$DEPLOY_NS" != "matrix-stack" ]]; then
  kubectl create namespace "$DEPLOY_NS" 2>/dev/null || true
fi

# Apply secrets
if [[ -f "$BASE_DIR/secrets.yaml" ]]; then
  kubectl apply -f "$BASE_DIR/secrets.yaml"
else
  echo "Applying example secrets (change in production)..."
  kubectl apply -f "$BASE_DIR/secrets.example.yaml" 2>/dev/null || true
fi

# Apply generated ConfigMaps
kubectl apply -f "$GENERATED_DIR/synapse-configmap.yaml"
kubectl apply -f "$GENERATED_DIR/synapse-worker-configmap.yaml"
kubectl apply -f "$GENERATED_DIR/stack-env-configmap.yaml"
# Base resources (element-call, lk-jwt-service) are in matrix-stack and reference stack-env; ensure it exists there
if [[ -n "$DEPLOY_NS" ]] && [[ "$DEPLOY_NS" != "matrix-stack" ]]; then
  kubectl get configmap stack-env -n "$DEPLOY_NS" -o yaml 2>/dev/null | \
    sed '/resourceVersion:/d; /uid:/d; /creationTimestamp:/d' | \
    sed "s/namespace: $DEPLOY_NS/namespace: matrix-stack/" | \
    kubectl apply -f - 2>/dev/null || true
fi

# Apply base resources
echo "Applying base resources..."
kubectl apply -k "$BASE_DIR"

# Worker-autoscaler
WORKER_AUTOSCALER_DIR="$STACK_DIR/../worker-autoscaler/k8s"
if [[ -f "$WORKER_AUTOSCALER_DIR/deployment.yaml" ]]; then
  echo "Applying worker-autoscaler..."
  kubectl apply -f "$WORKER_AUTOSCALER_DIR/deployment.yaml"
fi

# Build images with Docker and import into K3s containerd
if [[ -n "$BUILD_IMAGE" ]]; then
  echo "Building synapse-discordify:latest from repo root..."
  (cd "$REPO_ROOT" && docker build -t synapse-discordify:latest .)
  echo "Importing synapse-discordify into K3s..."
  docker save synapse-discordify:latest | k3s ctr -n k8s.io images import -

  if [[ -f "$REPO_ROOT/worker-autoscaler/Dockerfile" ]]; then
    echo "Building worker-autoscaler:latest..."
    (cd "$REPO_ROOT/worker-autoscaler" && docker build -t worker-autoscaler:latest .)
    echo "Importing worker-autoscaler into K3s..."
    docker save worker-autoscaler:latest | k3s ctr -n k8s.io images import -
  fi
fi

echo "Done. K3s cluster is in this container. Use: kubectl get pods -n matrix-stack"
