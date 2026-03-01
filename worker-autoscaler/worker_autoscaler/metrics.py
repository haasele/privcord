"""
Fetch workload and worker usage metrics from Kubernetes metrics API or Prometheus.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_metrics_kubernetes(
    target_name: str,
    namespace: str,
    label_selector: Optional[str] = None,
) -> Dict[str, float]:
    """
    Use Kubernetes metrics API (metrics-server) to get CPU/memory for pods
    matching the target deployment. Returns average utilization (0.0–1.0) per resource.
    """
    try:
        from kubernetes import client
        from kubernetes.client.rest import ApiException
    except ImportError:
        logger.error("kubernetes package not installed: pip install kubernetes")
        return {"cpu": 0.0, "memory": 0.0}

    v1 = client.CustomObjectsApi()
    # metrics.k8s.io/v1beta1 PodMetricsList
    try:
        # List PodMetrics in namespace; we'll filter by owner (deployment)
        metrics_list = v1.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods",
        )
    except ApiException as e:
        logger.warning("Metrics API not available: %s", e)
        return {"cpu": 0.0, "memory": 0.0}

    items = metrics_list.get("items", [])
    if not items:
        return {"cpu": 0.0, "memory": 0.0}

    # Get pods for this deployment so we only average over target workers
    try:
        core = client.CoreV1Api()
        pods = core.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector or f"app={target_name}",
        )
        target_pod_names = {p.metadata.name for p in pods.items}
        requested = {}
        for pod in pods.items:
            req = pod.spec.containers[0].resources.requests if pod.spec.containers else None
            if req:
                requested[pod.metadata.name] = {
                    "cpu": _parse_quantity(str(req.get("cpu", "0") or "0")),
                    "memory": _parse_quantity(str(req.get("memory", "0") or "0")),
                }
            else:
                requested[pod.metadata.name] = {"cpu": 0.001, "memory": 128 * 1024 * 1024}
    except Exception as e:
        logger.debug("Could not list pods: %s", e)
        target_pod_names = {m.get("metadata", {}).get("name") for m in items}
        requested = {}

    total_cpu_nano = 0.0
    total_mem_bytes = 0.0
    count = 0
    for m in items:
        name = m.get("metadata", {}).get("name")
        if name and target_pod_names and name not in target_pod_names:
            continue
        conts = m.get("containers", [])
        for c in conts:
            usage = c.get("usage", {})
            cpu = _parse_quantity(usage.get("cpu", "0"))
            mem = _parse_quantity(usage.get("memory", "0"))
            req = requested.get(name, {})
            req_cpu = req.get("cpu") or 0.001
            req_mem = req.get("memory") or (128 * 1024 * 1024)
            total_cpu_nano += cpu
            total_mem_bytes += mem
            count += 1

    if count == 0:
        return {"cpu": 0.0, "memory": 0.0}
    # Return average utilization (usage / requested) – we don't have requested per-pod in metrics
    # So we return raw average usage; caller can compare to thresholds in a different way
    # Simpler: return average CPU (in cores) and average memory (bytes) so caller can threshold
    avg_cpu_nano = total_cpu_nano / count
    avg_mem_bytes = total_mem_bytes / count
    # Convert to "fraction of 1 core" for CPU (nanocores -> 0.0-1.0 if we assume 1 core per pod)
    cpu_util = min(1.0, avg_cpu_nano / 1e9)
    # Memory: return as fraction of 512Mi default request
    default_mem = 512 * 1024 * 1024
    mem_util = min(1.0, avg_mem_bytes / default_mem)
    return {"cpu": cpu_util, "memory": mem_util, "pods": float(count)}


def _parse_quantity(s: str) -> float:
    if not s:
        return 0.0
    s = s.strip()
    if s.endswith("n"):
        return float(s[:-1])  # nanocores
    if s.endswith("u"):
        return float(s[:-1]) * 1000  # micro -> nano
    if s.endswith("m"):
        return float(s[:-1]) * 1e6  # millicores -> nano
    if s.endswith("Ki"):
        return float(s[:-2]) * 1024
    if s.endswith("Mi"):
        return float(s[:-2]) * 1024 * 1024
    if s.endswith("Gi"):
        return float(s[:-2]) * 1024 * 1024 * 1024
    try:
        return float(s)
    except ValueError:
        return 0.0


def get_metrics_prometheus(
    url: str,
    scale_up_query: str,
    scale_down_query: str,
) -> Dict[str, float]:
    """Query Prometheus for a single numeric value (e.g. average CPU or request rate)."""
    import urllib.parse
    import urllib.request

    result = {"value": 0.0}
    for name, query in [("up", scale_up_query), ("down", scale_down_query)]:
        try:
            req = urllib.request.Request(
                f"{url.rstrip('/')}/api/v1/query?query={urllib.parse.quote(query)}"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                import json
                data = json.loads(resp.read().decode())
                vals = data.get("data", {}).get("result", [])
                if vals and len(vals) > 0:
                    v = vals[0].get("value", [None, 0])
                    result["value"] = float(v[1]) if v[1] is not None else 0.0
                break
        except Exception as e:
            logger.warning("Prometheus query failed: %s", e)
    return result
