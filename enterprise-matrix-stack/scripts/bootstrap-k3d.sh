#!/usr/bin/env bash
# Bootstrap a k3d cluster with 2 nodes and deploy the Matrix stack (Connecting branch setup).
# Prereqs: k3d, kubectl, Python 3 + PyYAML.
# Usage:
#   ./scripts/bootstrap-k3d.sh [--config ...] [--cluster-name matrix-local] [--skip-create] [--build-image] [--recreate]
#   --build-image: build synapse-discordify:latest from repo root and load into k3d (requires cluster to exist)
#   --recreate: if cluster exists, delete and recreate without prompting (for CI/Docker)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$STACK_DIR/.." && pwd)"
CONFIG="$STACK_DIR/config/example.yaml"
CLUSTER_NAME="matrix-local"
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

# Create k3d cluster (2 agents = 2 nodes) if not skipping
if [[ -z "$SKIP_CREATE" ]]; then
  if k3d cluster list 2>/dev/null | grep -q "$CLUSTER_NAME"; then
    if [[ -n "$RECREATE" ]]; then
      echo "Cluster $CLUSTER_NAME exists; deleting and recreating (--recreate)."
      k3d cluster delete "$CLUSTER_NAME"
    else
      echo "Cluster $CLUSTER_NAME already exists. Use --skip-create to only deploy or --recreate to replace."
      read -r -p "Delete and recreate? [y/N] " ans
      if [[ "${ans,,}" == "y" ]]; then
        k3d cluster delete "$CLUSTER_NAME"
      else
        echo "Exiting."
        exit 0
      fi
    fi
  fi
  echo "Creating k3d cluster $CLUSTER_NAME with 2 nodes..."
  k3d cluster create "$CLUSTER_NAME" --agents 2 --port 8443:443@loadbalancer
  echo "Cluster created. Waiting for node readiness..."
  kubectl wait --for=condition=Ready nodes --all --timeout=120s 2>/dev/null || true
fi

# Ensure kubeconfig points to the cluster
export KUBECONFIG="$(k3d kubeconfig write "$CLUSTER_NAME" 2>/dev/null || true)"
if [[ -z "$KUBECONFIG" ]]; then
  echo "Could not get kubeconfig for $CLUSTER_NAME. Is the cluster running?"
  exit 1
fi

# Wait for API server to be reachable (k3d can be slow right after create)
echo "Waiting for API server..."
for i in {1..30}; do
  if kubectl get nodes &>/dev/null; then break; fi
  [[ $i -eq 30 ]] && { echo "API server did not become ready."; exit 1; }
  sleep 2
done

# Apply namespace first
kubectl apply -f "$BASE_DIR/namespace.yaml"

# Apply secrets (must exist; copy from secrets.example.yaml and fill, or create minimal secrets)
if [[ -f "$BASE_DIR/secrets.yaml" ]]; then
  kubectl apply -f "$BASE_DIR/secrets.yaml"
else
  echo "WARNING: $BASE_DIR/secrets.yaml not found. Create it from secrets.example.yaml and fill values."
  echo "Applying example secrets with empty values (stack may not work until you set real secrets)..."
  kubectl apply -f "$BASE_DIR/secrets.example.yaml" 2>/dev/null || true
fi

# Apply generated ConfigMaps (Synapse + worker config + stack-env for element-call/lk-jwt-service URLs)
kubectl apply -f "$GENERATED_DIR/synapse-configmap.yaml"
kubectl apply -f "$GENERATED_DIR/synapse-worker-configmap.yaml"
kubectl apply -f "$GENERATED_DIR/stack-env-configmap.yaml"

# Apply all base resources (kustomization order)
echo "Applying base resources..."
kubectl apply -k "$BASE_DIR"

# Optional: deploy worker-autoscaler (from API-Addon/worker-autoscaler/k8s)
WORKER_AUTOSCALER_DIR="$STACK_DIR/../worker-autoscaler/k8s"
if [[ -f "$WORKER_AUTOSCALER_DIR/deployment.yaml" ]]; then
  echo "Applying worker-autoscaler..."
  kubectl apply -f "$WORKER_AUTOSCALER_DIR/deployment.yaml"
fi

# Optional: build and load Synapse+Discordify image into k3d
if [[ -n "$BUILD_IMAGE" ]]; then
  echo "Building synapse-discordify:latest from repo root..."
  (cd "$REPO_ROOT" && docker build -t synapse-discordify:latest .)
  echo "Loading image into k3d cluster $CLUSTER_NAME..."
  k3d image import synapse-discordify:latest -c "$CLUSTER_NAME"
fi

echo "Done. Cluster: $CLUSTER_NAME. Use: kubectl get pods -n matrix-stack"
