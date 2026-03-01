"""Federation Directory configuration from environment."""
from __future__ import annotations

import os
from pathlib import Path


def _str(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value.strip()


def _int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


# API key required for POST /api/v1/servers/register. If unset, registration is disabled.
DIRECTORY_API_KEY: str | None = _str(os.environ.get("DIRECTORY_API_KEY"))

# Path to JSON file storing registered servers. Created if missing.
DIRECTORY_DATA_PATH: Path = Path(
    os.environ.get("DIRECTORY_DATA_PATH", "/data/servers.json")
)

# Listen host and port
HOST: str = os.environ.get("DIRECTORY_HOST", "0.0.0.0")
PORT: int = _int(os.environ.get("DIRECTORY_PORT"), 8765)

# Optional: CORS origins for GET /api/v1/servers (comma-separated). Empty = no CORS.
CORS_ORIGINS: str = os.environ.get("DIRECTORY_CORS_ORIGINS", "")
