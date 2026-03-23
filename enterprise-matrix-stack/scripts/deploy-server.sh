#!/usr/bin/env bash
# Deploy a new Privcord server as a Docker Compose stack.
# Each server gets its own project name (privcord-<handle>) and isolated volumes.
#
# Usage:
#   ./scripts/deploy-server.sh --handle myserver --domain myserver.example.com \
#     --space-name "My Server" --postgres-password secret --livekit-key key --livekit-secret secret
#
# Or with a config YAML:
#   ./scripts/deploy-server.sh --config config/myserver.yaml
#
# Requires: Docker with Compose plugin, Python 3, PyYAML, synapse-discordify:latest image.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$STACK_DIR/.." && pwd)"
COMPOSE_TEMPLATE="$STACK_DIR/docker/docker-compose.server.yml"
GENERATED_BASE="$STACK_DIR/docker/generated"

# Defaults
HANDLE=""
DOMAIN=""
SPACE_NAME=""
SPACE_DESCRIPTION=""
FEDERATION_MODE="private"
FEDERATION_WHITELIST=""
POSTGRES_MAIN_PASSWORD="$(openssl rand -hex 16 2>/dev/null || echo changeme)"
POSTGRES_MEDIA_PASSWORD="$(openssl rand -hex 16 2>/dev/null || echo changeme)"
REDIS_PASSWORD=""
REGISTRATION_SECRET="$(openssl rand -hex 16 2>/dev/null || echo changeme)"
LIVEKIT_API_KEY="devkey$(openssl rand -hex 4 2>/dev/null || echo 1234)"
LIVEKIT_API_SECRET="$(openssl rand -hex 16 2>/dev/null || echo changeme)"
SYNAPSE_PORT=""
FEDERATION_PORT=""
LIVEKIT_PORT=""
ELEMENT_CALL_PORT=""
CONFIG_FILE=""
DIRECTORY_URL=""
DIRECTORY_API_KEY=""
ENABLE_REGISTRATION="true"

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --handle NAME           Server handle (lowercase, no spaces) [required]
  --domain DOMAIN         Server domain [required]
  --space-name NAME       Space display name
  --space-description TXT Space description
  --federation-mode MODE  private|public (default: private)
  --federation-whitelist   Comma-separated server names
  --postgres-password PW  Postgres main password
  --livekit-key KEY       LiveKit API key
  --livekit-secret SECRET LiveKit API secret
  --synapse-port PORT     Host port for Synapse (default: auto)
  --livekit-port PORT     Host port for LiveKit (default: auto)
  --element-call-port PORT Host port for Element Call (default: auto)
  --config FILE           Use a YAML config file instead of CLI args
  --directory-url URL     Federation directory URL to register with
  --directory-api-key KEY Federation directory API key
  --no-registration       Disable open registration
  -h, --help              Show this help
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --handle) HANDLE="$2"; shift 2 ;;
        --domain) DOMAIN="$2"; shift 2 ;;
        --space-name) SPACE_NAME="$2"; shift 2 ;;
        --space-description) SPACE_DESCRIPTION="$2"; shift 2 ;;
        --federation-mode) FEDERATION_MODE="$2"; shift 2 ;;
        --federation-whitelist) FEDERATION_WHITELIST="$2"; shift 2 ;;
        --postgres-password) POSTGRES_MAIN_PASSWORD="$2"; POSTGRES_MEDIA_PASSWORD="$2"; shift 2 ;;
        --livekit-key) LIVEKIT_API_KEY="$2"; shift 2 ;;
        --livekit-secret) LIVEKIT_API_SECRET="$2"; shift 2 ;;
        --synapse-port) SYNAPSE_PORT="$2"; shift 2 ;;
        --livekit-port) LIVEKIT_PORT="$2"; shift 2 ;;
        --element-call-port) ELEMENT_CALL_PORT="$2"; shift 2 ;;
        --config) CONFIG_FILE="$2"; shift 2 ;;
        --directory-url) DIRECTORY_URL="$2"; shift 2 ;;
        --directory-api-key) DIRECTORY_API_KEY="$2"; shift 2 ;;
        --no-registration) ENABLE_REGISTRATION="false"; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -n "$CONFIG_FILE" ]]; then
    HANDLE=$(python3 -c "import yaml; c=yaml.safe_load(open('$CONFIG_FILE')); print(c.get('server',{}).get('handle',''))")
    DOMAIN=$(python3 -c "import yaml; c=yaml.safe_load(open('$CONFIG_FILE')); print(c.get('server',{}).get('domain',''))")
fi

if [[ -z "$HANDLE" ]] || [[ -z "$DOMAIN" ]]; then
    echo "Error: --handle and --domain are required (or use --config)"
    exit 1
fi

PROJECT_NAME="privcord-${HANDLE}"
GENERATED_DIR="$GENERATED_BASE/$HANDLE"
mkdir -p "$GENERATED_DIR"

echo "=== Deploying Privcord server: $HANDLE ($DOMAIN) ==="
echo "  Project: $PROJECT_NAME"

# Build synapse-discordify image if not present
if ! docker image inspect synapse-discordify:latest &>/dev/null; then
    echo "Building synapse-discordify:latest..."
    (cd "$REPO_ROOT" && docker build -t synapse-discordify:latest .)
fi

# Generate Synapse homeserver.yaml
echo "Generating homeserver config..."
cat > "$GENERATED_DIR/homeserver.yaml" <<HSEOF
server_name: "$DOMAIN"
public_baseurl: "http://$DOMAIN:${SYNAPSE_PORT:-8008}/"
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

enable_registration: $ENABLE_REGISTRATION
enable_registration_without_verification: $ENABLE_REGISTRATION
registration_shared_secret: "$REGISTRATION_SECRET"
suppress_key_server_warning: true
serve_server_wellknown: true

database:
  name: psycopg2
  args:
    database: synapse
    user: synapse
    password: "$POSTGRES_MAIN_PASSWORD"
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
      space_name: "${SPACE_NAME:-$HANDLE}"
      space_avatar: ""
HSEOF

# Generate LiveKit config
cat > "$GENERATED_DIR/livekit.yaml" <<LKEOF
port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: false
redis:
  address: redis:6379
keys:
  $LIVEKIT_API_KEY: $LIVEKIT_API_SECRET
logging:
  level: info
LKEOF

echo "Config generated in $GENERATED_DIR"

# Auto-assign ports if not specified
if [[ -z "$SYNAPSE_PORT" ]]; then
    SYNAPSE_PORT=$(python3 -c "
import socket, random
for _ in range(100):
    p = random.randint(8100, 8999)
    s = socket.socket(); s.settimeout(0.1)
    try:
        s.bind(('', p)); s.close(); print(p); break
    except: s.close()
else: print(8008)
")
fi
if [[ -z "$LIVEKIT_PORT" ]]; then
    LIVEKIT_PORT=$((SYNAPSE_PORT + 1000))
fi
if [[ -z "$ELEMENT_CALL_PORT" ]]; then
    ELEMENT_CALL_PORT=$((SYNAPSE_PORT + 2000))
fi
FEDERATION_PORT="${FEDERATION_PORT:-$((SYNAPSE_PORT + 440))}"

echo "  Synapse:      http://localhost:$SYNAPSE_PORT"
echo "  LiveKit:      http://localhost:$LIVEKIT_PORT"
echo "  Element Call: http://localhost:$ELEMENT_CALL_PORT"

# Launch Docker Compose
cd "$STACK_DIR/docker"
export SERVER_HANDLE="$HANDLE"
export SERVER_DOMAIN="$DOMAIN"
export SPACE_NAME="${SPACE_NAME:-$HANDLE}"
export POSTGRES_MAIN_PASSWORD
export POSTGRES_MEDIA_PASSWORD
export REDIS_PASSWORD
export LIVEKIT_API_KEY
export LIVEKIT_API_SECRET
export SYNAPSE_PORT
export FEDERATION_PORT
export LIVEKIT_PORT
export ELEMENT_CALL_PORT

docker compose -p "$PROJECT_NAME" -f docker-compose.server.yml up -d
echo ""

# Fix Synapse data volume permissions
VOLUME_NAME="${PROJECT_NAME}_synapse-data"
if docker volume inspect "$VOLUME_NAME" &>/dev/null; then
    docker run --rm -v "$VOLUME_NAME:/data" --user 0 alpine chown -R 991:991 /data 2>/dev/null || true
    docker compose -p "$PROJECT_NAME" -f docker-compose.server.yml up -d synapse --force-recreate
fi

# Wait for Synapse
echo "Waiting for Synapse to be healthy..."
for i in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$SYNAPSE_PORT/_matrix/client/versions" 2>/dev/null | grep -q 200; then
        echo "Synapse is up at http://localhost:$SYNAPSE_PORT"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo "Synapse did not become healthy in time."
        echo "Check: docker compose -p $PROJECT_NAME -f docker-compose.server.yml logs synapse"
        exit 1
    fi
    sleep 3
done

# Register with federation directory if configured
if [[ -n "$DIRECTORY_URL" ]] && [[ -n "$DIRECTORY_API_KEY" ]]; then
    echo "Registering with federation directory at $DIRECTORY_URL..."
    curl -s -X POST "$DIRECTORY_URL/api/v1/servers/register" \
        -H "Authorization: Bearer $DIRECTORY_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"server_name\":\"$DOMAIN\",\"base_url\":\"http://localhost:$SYNAPSE_PORT\",\"handle\":\"$HANDLE\",\"federation_port\":$FEDERATION_PORT}" \
        || echo "Warning: Could not register with federation directory"
fi

echo ""
echo "=== Server '$HANDLE' is running ==="
echo "  Synapse:       http://localhost:$SYNAPSE_PORT"
echo "  Element Call:  http://localhost:$ELEMENT_CALL_PORT"
echo "  LiveKit:       http://localhost:$LIVEKIT_PORT"
echo "  Project:       $PROJECT_NAME"
echo "  Stop:          docker compose -p $PROJECT_NAME -f $STACK_DIR/docker/docker-compose.server.yml down"
echo "  Logs:          docker compose -p $PROJECT_NAME -f $STACK_DIR/docker/docker-compose.server.yml logs -f"
