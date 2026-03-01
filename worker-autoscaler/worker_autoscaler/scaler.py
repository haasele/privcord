"""
Scale a Kubernetes Deployment or StatefulSet by updating replicas.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_current_replicas(
    kind: str,
    name: str,
    namespace: str,
) -> Optional[int]:
    try:
        from kubernetes import client
        from kubernetes.client.rest import ApiException
    except ImportError:
        return None
    apps = client.AppsV1Api()
    try:
        if kind == "Deployment":
            obj = apps.read_namespaced_deployment(name, namespace)
            return obj.spec.replicas
        if kind == "StatefulSet":
            obj = apps.read_namespaced_stateful_set(name, namespace)
            return obj.spec.replicas
    except ApiException as e:
        logger.warning("Failed to read %s %s/%s: %s", kind, namespace, name, e)
        return None
    return None


def scale(
    kind: str,
    name: str,
    namespace: str,
    replicas: int,
) -> bool:
    try:
        from kubernetes import client
        from kubernetes.client.rest import ApiException
    except ImportError:
        logger.error("kubernetes package not installed")
        return False
    apps = client.AppsV1Api()
    try:
        if kind == "Deployment":
            body = {"spec": {"replicas": replicas}}
            apps.patch_namespaced_deployment_scale(name, namespace, body)
        elif kind == "StatefulSet":
            body = {"spec": {"replicas": replicas}}
            apps.patch_namespaced_stateful_set_scale(name, namespace, body)
        else:
            logger.error("Unsupported kind: %s", kind)
            return False
        logger.info("Scaled %s %s/%s to %d replicas", kind, namespace, name, replicas)
        return True
    except ApiException as e:
        logger.warning("Scale failed: %s", e)
        return False
