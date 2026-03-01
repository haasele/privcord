"""Persist and load the server index (JSON file with lock)."""
from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any

from .config import DIRECTORY_DATA_PATH


def _ensure_dir() -> None:
    DIRECTORY_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DIRECTORY_DATA_PATH.exists():
        DIRECTORY_DATA_PATH.write_text("[]", encoding="utf-8")


def _load_raw() -> list[dict[str, Any]]:
    _ensure_dir()
    with open(DIRECTORY_DATA_PATH, "r", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            data = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    if not isinstance(data, list):
        return []
    return data


def _save_raw(servers: list[dict[str, Any]]) -> None:
    _ensure_dir()
    with open(DIRECTORY_DATA_PATH, "w", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(servers, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def list_servers() -> list[dict[str, Any]]:
    """Return all registered servers (read-only copy)."""
    return list(_load_raw())


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def register_server(
    server_name: str,
    base_url: str,
    *,
    handle: str | None = None,
    federation_port: int | None = None,
) -> dict[str, Any]:
    """
    Register or update a server by server_name. Returns the stored record.
    server_name must be the Matrix server name (e.g. matrix.example.com).
    """
    servers = _load_raw()
    server_name = (server_name or "").strip().lower()
    base_url = (base_url or "").strip().rstrip("/")
    if not server_name or not base_url:
        raise ValueError("server_name and base_url are required")
    record = {
        "server_name": server_name,
        "base_url": base_url,
        "handle": (handle or "").strip() or server_name.split(".")[0],
        "federation_port": federation_port if federation_port is not None else 8448,
        "registered_at": None,
    }
    for i, s in enumerate(servers):
        if (s.get("server_name") or "").lower() == server_name:
            record["registered_at"] = s.get("registered_at") or _ts()
            servers[i] = {**record, "updated_at": _ts()}
            _save_raw(servers)
            return servers[i]
    record["registered_at"] = _ts()
    record["updated_at"] = _ts()
    servers.append(record)
    _save_raw(servers)
    return record
