"""
Minimal backend for the Create Server wizard.
Accepts wizard JSON, builds config, runs generate_manifests.py, and optionally deploys to Kubernetes.
Set env STACK_DIR to the path of enterprise-matrix-stack (default: parent of backend/).
Set env ENABLE_DEPLOY=1 to run kubectl apply; otherwise only config is generated.
Set env DATABASE_URL_METADATA to use the dedicated metadata Postgres for job storage (e.g. postgresql://metadata:PASSWORD@postgres-metadata:5432/metadata).
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)

STACK_DIR = Path(os.environ.get("STACK_DIR", Path(__file__).resolve().parent.parent))
ENABLE_DEPLOY = os.environ.get("ENABLE_DEPLOY", "").strip().lower() in ("1", "true", "yes")
CONFIG_DIR = STACK_DIR / "config"
GENERATED_DIR = STACK_DIR / "k8s" / "generated"
SCRIPT_DIR = STACK_DIR / "scripts"
BASE_DIR = STACK_DIR / "k8s" / "base"

METADATA_DB_URL = os.environ.get("DATABASE_URL_METADATA", "").strip() or None

# In-memory fallback when metadata DB is not configured
_memory_jobs: dict[str, dict] = {}


def _init_metadata_db():
    """Create jobs table in metadata DB if using Postgres."""
    if not METADATA_DB_URL:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(METADATA_DB_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deployment_jobs (
                job_id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass  # fall back to in-memory


def _get_job(job_id: str) -> dict | None:
    if METADATA_DB_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(METADATA_DB_URL)
            cur = conn.cursor()
            cur.execute("SELECT data FROM deployment_jobs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row[0] if row else None
        except Exception:
            pass
    return _memory_jobs.get(job_id)


def _set_job(job_id: str, data: dict) -> None:
    if METADATA_DB_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(METADATA_DB_URL)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO deployment_jobs (job_id, data) VALUES (%s, %s)
                ON CONFLICT (job_id) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                """,
                (job_id, json.dumps(data)),
            )
            conn.commit()
            cur.close()
            conn.close()
            return
        except Exception:
            pass
    _memory_jobs[job_id] = data


def _get_all_job_ids() -> list[str]:
    if METADATA_DB_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(METADATA_DB_URL)
            cur = conn.cursor()
            cur.execute("SELECT job_id FROM deployment_jobs")
            ids = [r[0] for r in cur.fetchall()]
            cur.close()
            conn.close()
            return ids
        except Exception:
            pass
    return list(_memory_jobs.keys())


# Lazy init metadata DB on first request; jobs read/write via _get_job / _set_job
def jobs_get(job_id: str) -> dict | None:
    return _get_job(job_id)


def jobs_set(job_id: str, data: dict) -> None:
    _set_job(job_id, data)


_init_metadata_db()


def payload_to_config(body: dict) -> dict:
    """Map CreateServerPayload (frontend) to config/example.yaml structure."""
    handle = (body.get("server_handle") or "matrix").strip().lower().replace(" ", "-")
    domain = (body.get("domain") or "").strip()
    passwords = body.get("passwords") or {}
    return {
        "server": {
            "handle": handle,
            "domain": domain,
            "federation_port": body.get("federation_port") or 8448,
        },
        "space": {
            "name": (body.get("space_name") or "").strip(),
            "description": (body.get("space_description") or "").strip(),
        },
        "federation": {
            "mode": body.get("federation_mode") or "private",
            "whitelist": body.get("federation_whitelist") or [],
        },
        "databases": {
            "postgres_main": {
                "host": "postgres-main",
                "port": 5432,
                "database": "synapse",
                "user": "synapse",
                "password": passwords.get("postgres_main") or "",
            },
            "postgres_media": {
                "host": "postgres-media",
                "port": 5432,
                "database": "synapse_media",
                "user": "synapse_media",
                "password": passwords.get("postgres_media") or "",
            },
            "redis": {
                "host": "redis",
                "port": 6379,
                "password": passwords.get("redis") or "",
            },
        },
        "synapse": {
            "discordify": {
                "channels": [
                    {"name": "general", "type": "text", "default": True},
                    {"name": "Voice", "type": "voice"},
                ],
                "roles": [
                    {"name": "Owner", "power_level": 100},
                    {"name": "Moderator", "power_level": 50},
                    {"name": "User", "power_level": 0},
                ],
            },
            "registration_shared_secret": passwords.get("registration_shared_secret") or "",
            "signing_key_path": "/data/signing.key",
        },
        "turn": {
            "enabled": True,
            "host": f"turn.{domain}" if domain else "turn.example.com",
            "port": 3478,
            "tls_port": 5349,
            "shared_secret": passwords.get("turn_shared_secret") or "",
            "realm": domain or "matrix.example.com",
        },
        "livekit": {
            "enabled": True,
            "host": "livekit",
            "port": 7880,
            "api_key": passwords.get("livekit_api_key") or "",
            "api_secret": passwords.get("livekit_api_secret") or "",
            "ws_url": f"wss://livekit.{domain}" if domain else "wss://livekit.matrix.example.com",
        },
        "element_call": {
            "enabled": True,
            "base_url": f"https://call.{domain}" if domain else "https://call.matrix.example.com",
        },
        "deploy": {
            "namespace": f"matrix-{handle}",
        },
    }


@app.route("/api/v1/servers", methods=["POST"])
def create_server():
    """Accept wizard payload, build config, generate manifests, optionally deploy."""
    body = request.get_json(force=True, silent=True) or {}
    config = payload_to_config(body)
    handle = config["server"]["handle"]
    domain = config["server"]["domain"]
    namespace = config["deploy"]["namespace"]
    job_id = str(uuid.uuid4())

    jobs_set(job_id, {
        "status": "creating",
        "namespace": namespace,
        "homeserver_url": f"https://{domain}" if domain else None,
        "element_call_url": config["element_call"]["base_url"],
    })

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path = CONFIG_DIR / f"generated-{handle}.yaml"
    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        data = jobs_get(job_id) or {}
        data["status"] = "error"
        data["error"] = str(e)
        jobs_set(job_id, data)
        return jsonify(data), 500

    try:
        subprocess.run(
            [
                "python3",
                str(SCRIPT_DIR / "generate_manifests.py"),
                "--config", str(config_path),
                "--out", str(GENERATED_DIR),
            ],
            check=True,
            cwd=str(STACK_DIR),
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        data = jobs_get(job_id) or {}
        data["status"] = "error"
        data["error"] = e.stderr or str(e)
        jobs_set(job_id, data)
        return jsonify(data), 500

    if ENABLE_DEPLOY:
        try:
            # Create namespace if not exists (per-deployment namespace matrix-<handle>)
            cr = subprocess.run(
                ["kubectl", "create", "namespace", namespace],
                capture_output=True,
                text=True,
            )
            if cr.returncode != 0 and "AlreadyExists" not in cr.stderr:
                raise subprocess.CalledProcessError(cr.returncode, cr.args, cr.stdout, cr.stderr)
            # Apply generated ConfigMaps (they have metadata.namespace set from config)
            subprocess.run(
                ["kubectl", "apply", "-f", str(GENERATED_DIR / "synapse-configmap.yaml")],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["kubectl", "apply", "-f", str(GENERATED_DIR / "synapse-worker-configmap.yaml")],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["kubectl", "apply", "-f", str(GENERATED_DIR / "stack-env-configmap.yaml")],
                check=True,
                capture_output=True,
                text=True,
            )
            # Apply base resources into the deployment namespace
            subprocess.run(
                ["kubectl", "apply", "-k", str(BASE_DIR), "-n", namespace],
                check=True,
                capture_output=True,
                text=True,
            )
            data = jobs_get(job_id) or {}
            data["status"] = "deployed"
            jobs_set(job_id, data)
        except subprocess.CalledProcessError as e:
            data = jobs_get(job_id) or {}
            data["status"] = "error"
            data["error"] = e.stderr or str(e)
            jobs_set(job_id, data)
            return jsonify(data), 500
    else:
        data = jobs_get(job_id) or {}
        data["status"] = "generated"
        jobs_set(job_id, data)

    out = jobs_get(job_id) or {}
    return jsonify({
        "job_id": job_id,
        "namespace": namespace,
        "status": out.get("status"),
        "homeserver_url": out.get("homeserver_url"),
        "element_call_url": out.get("element_call_url"),
    }), 202


@app.route("/api/v1/servers/<job_id>", methods=["GET"])
def get_server(job_id: str):
    """Return status and URLs for a deployment job."""
    job = jobs_get(job_id)
    if not job:
        return jsonify({"error": "not_found"}), 404
    return jsonify(job)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
