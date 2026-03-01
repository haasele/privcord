"""
Main loop: analyze workload and worker usage, compute desired replicas, scale target.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict

from .config import load_config, setup_logging
from .metrics import get_metrics_kubernetes, get_metrics_prometheus
from .scaler import get_current_replicas, scale

logger = logging.getLogger(__name__)


def run_once(cfg: Dict[str, Any]) -> None:
    target = cfg.get("target", {})
    kind = target.get("kind", "Deployment")
    name = target.get("name", "")
    namespace = target.get("namespace", "default")
    replicas_cfg = cfg.get("replicas", {})
    min_rep = max(0, int(replicas_cfg.get("min", 1)))
    max_rep = max(min_rep, int(replicas_cfg.get("max", 10)))
    scaling_cfg = cfg.get("scaling", {})
    max_step = max(1, int(scaling_cfg.get("max_replica_step", 2)))

    current = get_current_replicas(kind, name, namespace)
    if current is None:
        logger.debug("Could not get current replicas; skipping")
        return

    source = cfg.get("metrics_source", "kubernetes")
    desired = current

    if source == "kubernetes":
        k8s_cfg = cfg.get("kubernetes_metrics", {})
        up_th = float(k8s_cfg.get("scale_up_cpu_threshold", 0.70))
        down_th = float(k8s_cfg.get("scale_down_cpu_threshold", 0.30))
        metrics = get_metrics_kubernetes(name, namespace)
        cpu = metrics.get("cpu", 0.0)
        logger.debug("Metrics: cpu=%.2f pods=%s", cpu, metrics.get("pods"))
        if cpu >= up_th and current < max_rep:
            desired = min(max_rep, current + max_step)
        elif cpu <= down_th and current > min_rep:
            desired = max(min_rep, current - max_step)
    elif source == "prometheus":
        prom = cfg.get("prometheus", {})
        url = prom.get("url", "")
        up_q = prom.get("scale_up_query", "")
        down_q = prom.get("scale_down_query", "")
        up_th = float(prom.get("scale_up_threshold", 0.70))
        down_th = float(prom.get("scale_down_threshold", 0.30))
        metrics = get_metrics_prometheus(url, up_q, down_q)
        value = metrics.get("value", 0.0)
        logger.debug("Prometheus value=%.2f", value)
        if value >= up_th and current < max_rep:
            desired = min(max_rep, current + max_step)
        elif value <= down_th and current > min_rep:
            desired = max(min_rep, current - max_step)
    else:
        logger.warning("Unknown metrics_source: %s", source)
        return

    desired = max(min_rep, min(max_rep, desired))
    if desired != current:
        if scale(kind, name, namespace, desired):
            logger.info("Replicas %s -> %d", current, desired)
    else:
        logger.debug("Replicas unchanged: %d", current)


def run_loop(config_path: Path) -> None:
    cfg = load_config(config_path)
    setup_logging(cfg.get("log_level", "INFO"))
    interval = max(15, int(cfg.get("interval", 60)))
    scale_up_cooldown = max(0, int(cfg.get("scaling", {}).get("scale_up_cooldown", 120)))
    scale_down_cooldown = max(0, int(cfg.get("scaling", {}).get("scale_down_cooldown", 300)))

    last_scale_up = 0.0
    last_scale_down = 0.0

    logger.info("Autoscaler started; interval=%ds", interval)
    while True:
        try:
            run_once(cfg)
        except Exception:
            logger.exception("Evaluation failed")
        time.sleep(interval)
