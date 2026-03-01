#!/usr/bin/env bash
# Generate config for E2E and start docker-compose (Synapse, Postgres, Redis, Backend).
# From repo root or enterprise-matrix-stack: ./scripts/run-e2e-docker.sh
# Requires: Docker, docker-compose, Python 3, PyYAML.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$STACK_DIR/config/e2e-docker.yaml"
OUT="$STACK_DIR/e2e-generated"

echo "Using config: $CONFIG"
mkdir -p "$OUT"
python3 "$SCRIPT_DIR/generate_manifests.py" --config "$CONFIG" --out "$OUT"
cp "$OUT/synapse-homeserver.yaml" "$OUT/homeserver.yaml"
echo "Generated $OUT/homeserver.yaml"

cd "$STACK_DIR"
echo "Starting Docker Compose (builds Synapse+Discordify if needed)..."
docker compose -f docker-compose.e2e.yml up -d --build
# So Synapse (user 991) can write to the volume, fix ownership of synapse-data volume
if docker volume inspect enterprise-matrix-stack_synapse-data &>/dev/null; then
  docker run --rm -v enterprise-matrix-stack_synapse-data:/data --user 0 alpine chown -R 991:991 /data 2>/dev/null || true
  docker compose -f docker-compose.e2e.yml up -d synapse --force-recreate
fi

echo ""
echo "Waiting for Synapse to be healthy..."
for i in {1..30}; do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:8008/_matrix/client/versions 2>/dev/null | grep -q 200; then
    echo "Synapse is up."
    break
  fi
  if [[ $i -eq 30 ]]; then
    echo "Synapse did not become healthy in time. Check: docker compose -f docker-compose.e2e.yml logs synapse"
    exit 1
  fi
  sleep 2
done

echo ""
echo "E2E stack is running. See PORTS_AND_URLS.md (or docs/PORTS_AND_URLS.md) for all ports and URLs."
echo "  Synapse:    http://localhost:8008"
echo "  Backend:    http://localhost:5000"
echo "  Stop:       docker compose -f docker-compose.e2e.yml down"
