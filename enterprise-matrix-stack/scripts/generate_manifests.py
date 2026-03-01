#!/usr/bin/env python3
"""
Read the master config YAML and generate Kubernetes manifests (ConfigMaps, env)
with server name, space, federation, and DB settings applied.
Usage:
  python3 generate_manifests.py --config config/example.yaml --out k8s/generated
  python3 generate_manifests.py --config config/example.yaml --env .env
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def load_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_synapse_homeserver(config: dict) -> str:
    server = config.get("server", {})
    domain = server.get("domain", "CHANGEME_DOMAIN")
    handle = server.get("handle", "matrix")
    federation_port = server.get("federation_port", 8448)
    federation = config.get("federation", {})
    mode = federation.get("mode", "private")
    db = config.get("databases", {}).get("postgres_main", {})
    db_pass = db.get("password") or "CHANGEME_POSTGRES_MAIN_PASSWORD"
    redis_cfg = config.get("databases", {}).get("redis", {})
    redis_host = redis_cfg.get("host", "redis")
    redis_port = redis_cfg.get("port", 6379)
    redis_pass = redis_cfg.get("password") or ""
    discordify = config.get("synapse", {}).get("discordify", {})
    space = config.get("space", {})

    # Worker names for autoscaling (worker_list on main; workers use generic_worker_0 .. generic_worker_9)
    worker_names = [f"generic_worker_{i}" for i in range(10)]
    worker_list_yaml = yaml.dump(
        [{"worker_name": w, "worker_type": "generic_worker"} for w in worker_names],
        default_flow_style=False,
        allow_unicode=True,
    )
    worker_list_indent = "".join("  " + line + "\n" for line in worker_list_yaml.strip().split("\n"))

    # Build discordify module config (space name/description are applied at runtime or via client)
    modules_yaml = yaml.dump(
        [
            {
                "module": "discordify_module.module.DiscordifySpacesModule",
                "config": {
                    "channels": discordify.get("channels", [{"name": "general", "type": "text"}, {"name": "Voice", "type": "voice"}]),
                    "roles": discordify.get("roles", []),
                    "voice_room_type": "org.matrix.msc3401.video_room",
                    "join_rule": "public",
                    "history_visibility": "shared",
                    "encryption": False,
                    "admin_power_level": 100,
                    "restrict_to_local_users": False,
                    "max_concurrency": 4,
                    "retry_count": 3,
                    "space_name": space.get("name", ""),
                    "space_avatar": "",
                    "roles": discordify.get("roles", []),
                },
            }
        ],
        default_flow_style=False,
        allow_unicode=True,
    )

    return f"""# Generated from config - do not edit by hand
server_name: "{domain}"
public_baseurl: "https://{domain}/"
report_stats: false
listen_address: "0.0.0.0"
port: 8008
federation_port: {federation_port}
federation_domain_whitelist: {yaml.dump(federation.get("whitelist", []) if mode == "public" else None) if mode == "public" else "# private: no federation"}

database:
  name: psycopg2
  args:
    database: {db.get("database", "synapse")}
    user: {db.get("user", "synapse")}
    password: "{db_pass}"
    host: {db.get("host", "postgres-main")}
    port: {db.get("port", 5432)}
    cp_min: 5
    cp_max: 10
  allow_unsafe_locale: true

redis:
  enabled: true
  host: {redis_host}
  port: {redis_port}
  password: "{redis_pass}"

worker_list:
{worker_list_indent}
media_store_path: "/data/media_store"
signing_key_path: "/data/signing.key"

modules:
{modules_yaml}
"""


def build_synapse_worker_config(config: dict) -> str:
    """Build worker config (same DB/redis as main, plus worker_app/worker_name/listeners)."""
    server = config.get("server", {})
    domain = server.get("domain", "CHANGEME_DOMAIN")
    db = config.get("databases", {}).get("postgres_main", {})
    db_pass = db.get("password") or "CHANGEME_POSTGRES_MAIN_PASSWORD"
    redis_cfg = config.get("databases", {}).get("redis", {})
    redis_host = redis_cfg.get("host", "redis")
    redis_port = redis_cfg.get("port", 6379)
    redis_pass = redis_cfg.get("password") or ""
    # Worker name from env so each pod can be generic_worker_0, generic_worker_1, etc.
    return f"""# Generated worker config - do not edit by hand
# Worker name is set via WORKER_NAME env (e.g. generic_worker_0)
server_name: "{domain}"
public_baseurl: "https://{domain}/"

database:
  name: psycopg2
  args:
    database: {db.get("database", "synapse")}
    user: {db.get("user", "synapse")}
    password: "{db_pass}"
    host: {db.get("host", "postgres-main")}
    port: {db.get("port", 5432)}
    cp_min: 2
    cp_max: 5

redis:
  enabled: true
  host: {redis_host}
  port: {redis_port}
  password: "{redis_pass}"

signing_key_path: "/data/signing.key"
media_store_path: "/data/media_store"

worker_app: synapse.app.generic_worker
worker_name: "${{WORKER_NAME}}"
worker_listeners:
  - type: http
    port: 8083
    x_forwarded: true
    resources:
      - names: [client, federation]
"""


def build_stack_env_configmap(config: dict) -> dict:
    """Build ConfigMap with domain/URLs for element-call, lk-jwt-service (no secrets)."""
    server = config.get("server", {})
    domain = server.get("domain", "CHANGEME_DOMAIN")
    livekit = config.get("livekit", {})
    ws_url = livekit.get("ws_url") or f"wss://livekit.{domain}"
    element_call = config.get("element_call", {})
    base_url = element_call.get("base_url") or f"https://call.{domain}"
    namespace = config.get("deploy", {}).get("namespace", "matrix-stack")
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "stack-env", "namespace": namespace},
        "data": {
            "HOMESERVER_URL": f"https://{domain}/",
            "LIVEKIT_WS_URL": ws_url,
            "LIVEKIT_LOCAL_HOMESERVERS": domain,
            "ELEMENT_CALL_BASE_URL": base_url,
        },
    }


def build_env_file(config: dict) -> str:
    lines = ["# Generated from config - source into shell or use with --env-file"]
    db_main = config.get("databases", {}).get("postgres_main", {})
    db_media = config.get("databases", {}).get("postgres_media", {})
    redis = config.get("databases", {}).get("redis", {})
    synapse_cfg = config.get("synapse", {})
    turn_cfg = config.get("turn", {})
    livekit_cfg = config.get("livekit", {})

    lines.append(f"POSTGRES_MAIN_PASSWORD={db_main.get('password') or ''}")
    lines.append(f"POSTGRES_MEDIA_PASSWORD={db_media.get('password') or ''}")
    lines.append(f"REDIS_PASSWORD={redis.get('password') or ''}")
    lines.append(f"SYNAPSE_REGISTRATION_SHARED_SECRET={synapse_cfg.get('registration_shared_secret') or ''}")
    lines.append(f"TURN_SHARED_SECRET={turn_cfg.get('shared_secret') or ''}")
    lines.append(f"LIVEKIT_API_KEY={livekit_cfg.get('api_key') or ''}")
    lines.append(f"LIVEKIT_API_SECRET={livekit_cfg.get('api_secret') or ''}")
    lines.append(f"SERVER_DOMAIN={config.get('server', {}).get('domain', '')}")
    lines.append(f"SPACE_NAME={config.get('space', {}).get('name', '')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate k8s manifests and env from master config")
    ap.add_argument("--config", "-c", type=Path, default=Path("config/example.yaml"), help="Master config YAML")
    ap.add_argument("--out", "-o", type=Path, help="Output directory for generated manifests")
    ap.add_argument("--env", type=Path, help="Output path for .env file")
    args = ap.parse_args()

    if not args.config.exists():
        print(f"Config not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)

    if args.env:
        args.env.parent.mkdir(parents=True, exist_ok=True)
        args.env.write_text(build_env_file(config))
        print(f"Wrote {args.env}")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        namespace = config.get("deploy", {}).get("namespace", "matrix-stack")
        homeserver = build_synapse_homeserver(config)
        (args.out / "synapse-homeserver.yaml").write_text(homeserver)
        print(f"Wrote {args.out / 'synapse-homeserver.yaml'}")

        worker_config = build_synapse_worker_config(config)
        (args.out / "synapse-worker.yaml").write_text(worker_config)
        print(f"Wrote {args.out / 'synapse-worker.yaml'}")

        cm = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "synapse-config", "namespace": namespace},
            "data": {"homeserver.yaml": homeserver},
        }
        (args.out / "synapse-configmap.yaml").write_text(
            "---\n" + yaml.dump(cm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        )
        print(f"Wrote {args.out / 'synapse-configmap.yaml'}")

        cm_worker = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "synapse-worker-config", "namespace": namespace},
            "data": {"worker.yaml": worker_config},
        }
        (args.out / "synapse-worker-configmap.yaml").write_text(
            "---\n" + yaml.dump(cm_worker, default_flow_style=False, allow_unicode=True, sort_keys=False)
        )
        print(f"Wrote {args.out / 'synapse-worker-configmap.yaml'}")

        stack_env = build_stack_env_configmap(config)
        (args.out / "stack-env-configmap.yaml").write_text(
            "---\n" + yaml.dump(stack_env, default_flow_style=False, allow_unicode=True, sort_keys=False)
        )
        print(f"Wrote {args.out / 'stack-env-configmap.yaml'}")


if __name__ == "__main__":
    main()
