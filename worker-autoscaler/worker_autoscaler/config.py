from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

def load_config(path: Path) -> Dict[str, Any]:
    with open(path) as f:
        try:
            import yaml
            return yaml.safe_load(f) or {}
        except ImportError:
            raise RuntimeError("pip install pyyaml")

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
