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


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

STACK_DIR = Path(os.environ.get("STACK_DIR", Path(__file__).resolve().parent.parent))
ENABLE_DEPLOY = os.environ.get("ENABLE_DEPLOY", "").strip().lower() in ("1", "true", "yes")
DEPLOY_MODE = os.environ.get("DEPLOY_MODE", "k8s").strip().lower()  # k8s | docker
CONFIG_DIR = STACK_DIR / "config"
GENERATED_DIR = STACK_DIR / "k8s" / "generated"
SCRIPT_DIR = STACK_DIR / "scripts"
BASE_DIR = STACK_DIR / "k8s" / "base"
DOCKER_GENERATED_DIR = STACK_DIR / "docker" / "generated"
DIRECTORY_URL = os.environ.get("DIRECTORY_URL", "").strip() or None
DIRECTORY_API_KEY_ENV = os.environ.get("DIRECTORY_API_KEY", "").strip() or None

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


def _find_free_port(start: int = 8100, end: int = 8999) -> int:
    import socket
    import random
    for _ in range(200):
        p = random.randint(start, end)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            try:
                s.bind(("", p))
                return p
            except OSError:
                continue
    return start


def _deploy_docker_compose(handle: str, domain: str, config: dict, body: dict) -> dict:
    """Deploy a new server stack as a Docker Compose project."""
    import shutil

    project_name = f"privcord-{handle}"
    gen_dir = DOCKER_GENERATED_DIR / handle
    gen_dir.mkdir(parents=True, exist_ok=True)

    passwords = body.get("passwords") or {}
    pg_pass = passwords.get("postgres_main") or "changeme"
    pg_media_pass = passwords.get("postgres_media") or "changeme"
    reg_secret = passwords.get("registration_shared_secret") or "changeme"
    lk_key = passwords.get("livekit_api_key") or f"devkey{handle}"
    lk_secret = passwords.get("livekit_api_secret") or "changeme"

    synapse_port = _find_free_port(8100, 8499)
    livekit_port = _find_free_port(9100, 9499)
    element_call_port = _find_free_port(10100, 10499)
    federation_port = synapse_port + 440

    space = config.get("space", {})

    homeserver_yaml = f"""server_name: "{domain}"
public_baseurl: "http://localhost:{synapse_port}/"
report_stats: false

listeners:
  - port: 8008
    tls: false
    type: http
    x_forwarded: true
    bind_addresses: ["0.0.0.0"]
    resources:
      - names: [client, federation]
        compress: false

enable_registration: true
enable_registration_without_verification: true
registration_shared_secret: "{reg_secret}"
suppress_key_server_warning: true
serve_server_wellknown: true

database:
  name: psycopg2
  args:
    database: synapse
    user: synapse
    password: "{pg_pass}"
    host: postgres-main
    port: 5432
    cp_min: 5
    cp_max: 10
  allow_unsafe_locale: true

redis:
  enabled: true
  host: redis
  port: 6379

media_store_path: "/data/media_store"
signing_key_path: "/data/signing.key"

modules:
  - module: discordify_module.module.DiscordifySpacesModule
    config:
      channels:
        - name: general
          type: text
          default: true
        - name: Voice
          type: voice
      roles:
        - name: Owner
          power_level: 100
        - name: Moderator
          power_level: 50
        - name: User
          power_level: 0
      voice_room_type: org.matrix.msc3401.video_room
      join_rule: public
      history_visibility: shared
      encryption: false
      admin_power_level: 100
      restrict_to_local_users: false
      max_concurrency: 4
      retry_count: 3
      space_name: "{space.get('name', handle)}"
      space_avatar: ""
"""
    (gen_dir / "homeserver.yaml").write_text(homeserver_yaml)

    livekit_yaml = f"""port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: false
redis:
  address: redis:6379
keys:
  {lk_key}: {lk_secret}
logging:
  level: info
"""
    (gen_dir / "livekit.yaml").write_text(livekit_yaml)

    compose_file = STACK_DIR / "docker" / "docker-compose.server.yml"
    env = {
        **os.environ,
        "SERVER_HANDLE": handle,
        "SERVER_DOMAIN": domain,
        "POSTGRES_MAIN_PASSWORD": pg_pass,
        "POSTGRES_MEDIA_PASSWORD": pg_media_pass,
        "REDIS_PASSWORD": "",
        "LIVEKIT_API_KEY": lk_key,
        "LIVEKIT_API_SECRET": lk_secret,
        "SYNAPSE_PORT": str(synapse_port),
        "FEDERATION_PORT": str(federation_port),
        "LIVEKIT_PORT": str(livekit_port),
        "ELEMENT_CALL_PORT": str(element_call_port),
    }

    result = subprocess.run(
        ["docker", "compose", "-p", project_name, "-f", str(compose_file), "up", "-d"],
        capture_output=True, text=True, env=env,
        cwd=str(STACK_DIR / "docker"),
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose up failed: {result.stderr}")

    volume_name = f"{project_name}_synapse-data"
    subprocess.run(
        ["docker", "run", "--rm", "-v", f"{volume_name}:/data", "--user", "0", "alpine", "chown", "-R", "991:991", "/data"],
        capture_output=True, text=True,
    )
    subprocess.run(
        ["docker", "compose", "-p", project_name, "-f", str(compose_file), "up", "-d", "synapse", "--force-recreate"],
        capture_output=True, text=True, env=env,
        cwd=str(STACK_DIR / "docker"),
    )

    if DIRECTORY_URL and DIRECTORY_API_KEY_ENV:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{DIRECTORY_URL}/api/v1/servers/register",
                data=json.dumps({
                    "server_name": domain,
                    "base_url": f"http://localhost:{synapse_port}",
                    "handle": handle,
                    "federation_port": federation_port,
                }).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DIRECTORY_API_KEY_ENV}",
                },
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    return {
        "synapse_port": synapse_port,
        "federation_port": federation_port,
        "livekit_port": livekit_port,
        "element_call_port": element_call_port,
    }


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

    if ENABLE_DEPLOY and DEPLOY_MODE == "docker":
        try:
            deploy_result = _deploy_docker_compose(handle, domain, config, body)
            data = jobs_get(job_id) or {}
            data["status"] = "deployed"
            data["synapse_port"] = deploy_result.get("synapse_port")
            data["homeserver_url"] = f"http://localhost:{deploy_result.get('synapse_port', 8008)}"
            data["element_call_port"] = deploy_result.get("element_call_port")
            data["livekit_port"] = deploy_result.get("livekit_port")
            jobs_set(job_id, data)
        except Exception as e:
            data = jobs_get(job_id) or {}
            data["status"] = "error"
            data["error"] = str(e)
            jobs_set(job_id, data)
            return jsonify(data), 500
    elif ENABLE_DEPLOY and DEPLOY_MODE == "k8s":
        try:
            cr = subprocess.run(
                ["kubectl", "create", "namespace", namespace],
                capture_output=True,
                text=True,
            )
            if cr.returncode != 0 and "AlreadyExists" not in cr.stderr:
                raise subprocess.CalledProcessError(cr.returncode, cr.args, cr.stdout, cr.stderr)
            subprocess.run(
                ["kubectl", "apply", "-f", str(GENERATED_DIR / "synapse-configmap.yaml")],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["kubectl", "apply", "-f", str(GENERATED_DIR / "synapse-worker-configmap.yaml")],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["kubectl", "apply", "-f", str(GENERATED_DIR / "stack-env-configmap.yaml")],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["kubectl", "apply", "-k", str(BASE_DIR), "-n", namespace],
                check=True, capture_output=True, text=True,
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
