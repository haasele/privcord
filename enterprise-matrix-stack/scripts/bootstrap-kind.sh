#!/usr/bin/env bash
# Bootstrap a KIND cluster inside the container and deploy the Matrix stack (fully isolated).
# Prereqs: Docker daemon running in container, kind, kubectl, Python 3 + PyYAML.
# Usage:
#   ./scripts/bootstrap-kind.sh [--config ...] [--cluster-name matrix-local] [--skip-create] [--build-image] [--recreate]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$STACK_DIR/.." && pwd)"
CONFIG="$STACK_DIR/config/example.yaml"
CLUSTER_NAME="matrix-local"
KIND_CONFIG="$STACK_DIR/k8s/kind-config.yaml"
SKIP_CREATE=""
BUILD_IMAGE=""
RECREATE=""
GENERATED_DIR="$STACK_DIR/k8s/generated"
BASE_DIR="$STACK_DIR/k8s/base"

while [[ $# -gt 0 ]]; do
  case $1 in
    --config) CONFIG="$2"; shift 2 ;;
    --cluster-name) CLUSTER_NAME="$2"; shift 2 ;;
    --skip-create) SKIP_CREATE=1; shift ;;
    --build-image) BUILD_IMAGE=1; shift ;;
    --recreate) RECREATE=1; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "Using config: $CONFIG"
echo "Cluster name: $CLUSTER_NAME"

# Generate manifests from config
echo "Generating manifests..."
python3 "$SCRIPT_DIR/generate_manifests.py" --config "$CONFIG" --out "$GENERATED_DIR"
echo "Generated ConfigMaps in $GENERATED_DIR"

# Create KIND cluster if not skipping
if [[ -z "$SKIP_CREATE" ]]; then
  if kind get kubeconfig --name "$CLUSTER_NAME" &>/dev/null; then
    if [[ -n "$RECREATE" ]]; then
      echo "Cluster $CLUSTER_NAME exists; deleting and recreating (--recreate)."
      kind delete cluster --name "$CLUSTER_NAME"
    else
      echo "Cluster $CLUSTER_NAME already exists. Use --skip-create to only deploy or --recreate to replace."
      exit 0
    fi
  fi
  echo "Creating KIND cluster $CLUSTER_NAME..."
  kind create cluster --name "$CLUSTER_NAME" --config "$KIND_CONFIG"
  echo "Cluster created."
fi

# Kubeconfig is updated by kind; use default or explicit
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
if ! kind get kubeconfig --name "$CLUSTER_NAME" >/dev/null 2>&1; then
  echo "Could not get kubeconfig for $CLUSTER_NAME. Is the cluster running?"
  exit 1
fi

# Wait for API server
echo "Waiting for API server..."
for i in {1..30}; do
  if kubectl get nodes &>/dev/null; then break; fi
  [[ $i -eq 30 ]] && { echo "API server did not become ready."; exit 1; }
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

# Apply base resources
echo "Applying base resources..."
kubectl apply -k "$BASE_DIR"

# Worker-autoscaler
WORKER_AUTOSCALER_DIR="$STACK_DIR/../worker-autoscaler/k8s"
if [[ -f "$WORKER_AUTOSCALER_DIR/deployment.yaml" ]]; then
  echo "Applying worker-autoscaler..."
  kubectl apply -f "$WORKER_AUTOSCALER_DIR/deployment.yaml"
fi

# Build and load images into KIND
if [[ -n "$BUILD_IMAGE" ]]; then
  echo "Building synapse-discordify:latest from repo root..."
  (cd "$REPO_ROOT" && docker build -t synapse-discordify:latest .)
  echo "Loading synapse-discordify into KIND cluster $CLUSTER_NAME..."
  kind load docker-image synapse-discordify:latest --name "$CLUSTER_NAME"

  if [[ -f "$REPO_ROOT/worker-autoscaler/Dockerfile" ]]; then
    echo "Building worker-autoscaler:latest..."
    (cd "$REPO_ROOT/worker-autoscaler" && docker build -t worker-autoscaler:latest .)
    echo "Loading worker-autoscaler into KIND cluster $CLUSTER_NAME..."
    kind load docker-image worker-autoscaler:latest --name "$CLUSTER_NAME"
  fi
fi

echo "Done. Cluster: $CLUSTER_NAME (fully inside this container). Use: kubectl get pods -n matrix-stack"
