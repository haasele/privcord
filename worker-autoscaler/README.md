# Worker pool autoscaler

Analyzes **server workload** and **worker usage** and **automatically adjusts the number of workers** so the worker pool stays performant (scale up under load, scale down when idle).

## What it does

- **Metrics:** Reads current load from either:
  - **Kubernetes metrics API** (metrics-server): average CPU (and optionally memory) utilization of pods belonging to the target Deployment/StatefulSet.
  - **Prometheus:** custom PromQL queries (e.g. request rate, queue depth).
- **Policy:** Scale up when utilization is above a threshold, scale down when below a lower threshold, with configurable min/max replicas and step size.
- **Action:** Patches the target Kubernetes Deployment or StatefulSet `spec.replicas` so the cluster scheduler adds or removes worker pods.

Typical use: scale **Synapse workers** (or any other worker Deployment) in the same cluster (e.g. the [enterprise-matrix-stack](../enterprise-matrix-stack/)).

## Config

Edit `config/example.yaml`:

| Key | Description |
|-----|-------------|
| `target.kind` | `Deployment` or `StatefulSet` |
| `target.name` | Name of the resource to scale (e.g. `synapse`) |
| `target.namespace` | Namespace (e.g. `matrix-stack`) |
| `replicas.min` / `replicas.max` | Replica bounds |
| `interval` | Evaluation interval in seconds |
| `metrics_source` | `kubernetes` or `prometheus` |
| `kubernetes_metrics.scale_up_cpu_threshold` | Scale up when average pod CPU ≥ this (0.0–1.0) |
| `kubernetes_metrics.scale_down_cpu_threshold` | Scale down when average pod CPU ≤ this |
| `scaling.max_replica_step` | Max change in replicas per evaluation |
| `scaling.scale_up_cooldown` / `scale_down_cooldown` | Seconds between scale-up / scale-down actions (optional) |

## Run locally

Requires `kubectl` and kubeconfig so the autoscaler can talk to the cluster (and, for `kubernetes` metrics, a working metrics-server).

```bash
pip install -r requirements.txt
python -m worker_autoscaler --config config/example.yaml
```

One-shot (evaluate once and exit):

```bash
python -m worker_autoscaler --config config/example.yaml --once
```

## Run in Kubernetes

1. Build image (from this directory):
   ```bash
   docker build -t worker-autoscaler:latest .
   ```

2. Apply RBAC and Deployment (edit the ConfigMap if your target name/namespace differ):
   ```bash
   kubectl apply -f k8s/deployment.yaml
   ```

3. The autoscaler runs in the cluster with a ServiceAccount that can read metrics and patch scale. Point the ConfigMap `config.yaml` at your worker Deployment (e.g. `synapse` in `matrix-stack`).

## Requirements

- **Kubernetes cluster** (e.g. k3s) with:
  - **metrics-server** installed if using `metrics_source: kubernetes` (many k3s installs include it).
  - Or **Prometheus** and a scrape config for your workers if using `metrics_source: prometheus`.
- **RBAC:** the manifest grants the autoscaler ServiceAccount permission to list pods, read PodMetrics, and patch deployments/statefulsets scale.

## Files

- `config/example.yaml` – config template
- `worker_autoscaler/` – Python package: `config`, `metrics`, `scaler`, `autoscaler`, `__main__`
- `requirements.txt` – pyyaml, kubernetes
- `Dockerfile` – image for running in-cluster
- `k8s/deployment.yaml` – ServiceAccount, ClusterRole, ClusterRoleBinding, ConfigMap, Deployment
