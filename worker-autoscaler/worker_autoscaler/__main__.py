from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .autoscaler import run_loop
from .config import load_config, setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(description="Worker pool autoscaler: analyze workload, auto-adjust replicas")
    ap.add_argument("--config", "-c", type=Path, default=Path("config/example.yaml"), help="Config YAML")
    ap.add_argument("--once", action="store_true", help="Run once and exit (no loop)")
    args = ap.parse_args()
    if not args.config.exists():
        print(f"Config not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    cfg = load_config(args.config)
    setup_logging(cfg.get("log_level", "INFO"))
    if args.once:
        from .autoscaler import run_once
        run_once(cfg)
        return
    run_loop(args.config)


if __name__ == "__main__":
    main()
