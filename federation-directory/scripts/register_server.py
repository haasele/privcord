#!/usr/bin/env python3
"""
Register a public server with the Federation Directory.
Usage:
  DIRECTORY_URL=https://... DIRECTORY_API_KEY=... python register_server.py \\
    --server-name matrix.example.com --base-url https://matrix.example.com [--handle mycompany] [--federation-port 8448]
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
import json


def main() -> None:
    p = argparse.ArgumentParser(description="Register a public server with the Federation Directory")
    p.add_argument("--server-name", required=True, help="Matrix server name (e.g. matrix.example.com)")
    p.add_argument("--base-url", required=True, help="Public base URL (e.g. https://matrix.example.com)")
    p.add_argument("--handle", default="", help="Short handle (default: first label of server_name)")
    p.add_argument("--federation-port", type=int, default=8448, help="Federation port (default 8448)")
    p.add_argument("--directory-url", default=os.environ.get("DIRECTORY_URL"), help="Directory base URL (or DIRECTORY_URL)")
    p.add_argument("--api-key", default=os.environ.get("DIRECTORY_API_KEY"), help="API key (or DIRECTORY_API_KEY)")
    args = p.parse_args()

    base = (args.directory_url or "").strip().rstrip("/")
    key = (args.api_key or "").strip()
    if not base or not key:
        print("Set DIRECTORY_URL and DIRECTORY_API_KEY (or --directory-url and --api-key)", file=sys.stderr)
        sys.exit(1)

    url = f"{base}/api/v1/servers/register"
    body = {
        "server_name": args.server_name.strip(),
        "base_url": args.base_url.strip().rstrip("/"),
        "federation_port": args.federation_port,
    }
    if args.handle:
        body["handle"] = args.handle.strip()

    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
            print(json.dumps(data, indent=2))
    except urllib.error.HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
