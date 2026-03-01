#!/usr/bin/env python3
"""
Fetch the server index from the Federation Directory and print server_name per line
(for building federation_domain_whitelist). Optionally exclude own server.
Usage:
  DIRECTORY_URL=https://... python fetch_index.py [--exclude-server matrix.mycompany.com]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch directory index and print server_name list")
    p.add_argument("--directory-url", default=os.environ.get("DIRECTORY_URL"), help="Directory base URL")
    p.add_argument("--exclude-server", default=os.environ.get("MY_SERVER_NAME", ""), help="Exclude this server_name from output")
    p.add_argument("--json", action="store_true", help="Output full JSON instead of one name per line")
    args = p.parse_args()

    base = (args.directory_url or "").strip().rstrip("/")
    if not base:
        print("Set DIRECTORY_URL or --directory-url", file=sys.stderr)
        sys.exit(1)

    url = f"{base}/api/v1/servers"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    servers = data.get("servers") or []
    exclude = (args.exclude_server or "").strip().lower()

    if args.json:
        print(json.dumps(data, indent=2))
        return

    for s in servers:
        name = (s.get("server_name") or "").strip()
        if name and name.lower() != exclude:
            print(name)


if __name__ == "__main__":
    main()
