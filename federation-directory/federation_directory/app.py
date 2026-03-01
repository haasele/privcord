"""
Federation Directory API: central index of public Matrix servers.
- POST /api/v1/servers/register — register a public server (requires API key).
- GET  /api/v1/servers         — list all registered servers (for Synapse whitelist / fallback).
"""
from __future__ import annotations

import re
from flask import Flask, jsonify, request

from .config import CORS_ORIGINS, DIRECTORY_API_KEY
from . import storage

app = Flask(__name__)

if CORS_ORIGINS:
    origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
    if origins:

        @app.after_request
        def _cors(resp):
            origin = request.environ.get("HTTP_ORIGIN")
            if origin and origin in origins:
                resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-API-Key"
            return resp


def _auth_ok() -> bool:
    if not DIRECTORY_API_KEY:
        return False
    auth = request.headers.get("Authorization") or request.headers.get("X-API-Key")
    if not auth:
        return False
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
    else:
        token = auth.strip()
    return token == DIRECTORY_API_KEY


# Server name: hostname-like (letters, digits, dots, hyphens)
SERVER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}[a-zA-Z0-9]$")


@app.route("/api/v1/servers", methods=["GET"])
def get_servers():
    """Return the list of registered public servers. No auth required (read-only index)."""
    servers = storage.list_servers()
    return jsonify({"servers": servers})


@app.route("/api/v1/servers/register", methods=["POST"])
def register():
    """Register or update a public server. Requires DIRECTORY_API_KEY (Bearer or X-API-Key)."""
    if not _auth_ok():
        return jsonify({"error": "unauthorized", "message": "Missing or invalid API key"}), 401
    data = request.get_json(silent=True) or {}
    server_name = (data.get("server_name") or data.get("serverName") or "").strip()
    base_url = (data.get("base_url") or data.get("baseUrl") or "").strip().rstrip("/")
    handle = (data.get("handle") or "").strip() or None
    federation_port = data.get("federation_port") or data.get("federationPort")
    if federation_port is not None:
        try:
            federation_port = int(federation_port)
        except (TypeError, ValueError):
            federation_port = 8448
    if not server_name:
        return jsonify({"error": "bad_request", "message": "server_name is required"}), 400
    if not base_url:
        return jsonify({"error": "bad_request", "message": "base_url is required"}), 400
    if not SERVER_NAME_RE.match(server_name):
        return jsonify({
            "error": "bad_request",
            "message": "server_name must be a valid hostname (e.g. matrix.example.com)",
        }), 400
    try:
        record = storage.register_server(
            server_name,
            base_url,
            handle=handle,
            federation_port=federation_port,
        )
    except ValueError as e:
        return jsonify({"error": "bad_request", "message": str(e)}), 400
    return jsonify(record), 201


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200
