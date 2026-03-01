# Federation Directory

Central **index server** for public Matrix homeservers. Public servers register here when they are created; other servers fetch the index to build their federation whitelist (direct first, index as fallback).

## Purpose

- **Single source of truth** for “which servers are public” in your federation.
- When you create a **public** server (e.g. via enterprise-matrix-stack), it **POSTs** to this directory to register.
- Each public server **fetches** the index (periodically or on startup) and uses it to populate `federation_domain_whitelist` (or as fallback when direct directory access fails).

## API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/servers` | None | List all registered servers (for Synapse / index consumer). |
| POST | `/api/v1/servers/register` | API key (Bearer or X-API-Key) | Register or update a public server. |
| GET | `/health` | None | Health check. |

### Register (POST /api/v1/servers/register)

**Headers:** `Authorization: Bearer <DIRECTORY_API_KEY>` or `X-API-Key: <DIRECTORY_API_KEY>`

**Body (JSON):**

```json
{
  "server_name": "matrix.example.com",
  "base_url": "https://matrix.example.com",
  "handle": "mycompany",
  "federation_port": 8448
}
```

- `server_name` (required): Matrix server name (hostname).
- `base_url` (required): Public base URL of the homeserver (no trailing slash).
- `handle` (optional): Short handle; defaults to first label of `server_name`.
- `federation_port` (optional): Default 8448.

### Index (GET /api/v1/servers)

Returns:

```json
{
  "servers": [
    {
      "server_name": "matrix.example.com",
      "base_url": "https://matrix.example.com",
      "handle": "mycompany",
      "federation_port": 8448,
      "registered_at": "2025-02-17T12:00:00Z",
      "updated_at": "2025-02-17T12:00:00Z"
    }
  ]
}
```

Consumers (e.g. Synapse) use `server_name` for `federation_domain_whitelist`.

## Configuration (environment)

| Variable | Description | Default |
|----------|-------------|---------|
| `DIRECTORY_API_KEY` | API key for register; if unset, registration is disabled. | — |
| `DIRECTORY_DATA_PATH` | Path to JSON file storing the index. | `/data/servers.json` |
| `DIRECTORY_HOST` | Bind host. | `0.0.0.0` |
| `DIRECTORY_PORT` | Bind port (used by dev server; gunicorn uses 8765 in Docker). | `8765` |
| `DIRECTORY_CORS_ORIGINS` | Comma-separated CORS origins for GET. | — |

## Run locally

```bash
cd federation-directory
pip install -r requirements.txt
export DIRECTORY_API_KEY=your-secret-key
export DIRECTORY_DATA_PATH=./data/servers.json
python -m federation_directory
```

Then: `curl http://localhost:8765/api/v1/servers` and register with `curl -X POST http://localhost:8765/api/v1/servers/register -H "Authorization: Bearer your-secret-key" -H "Content-Type: application/json" -d '{"server_name":"matrix.example.com","base_url":"https://matrix.example.com"}'`.

## Docker

```bash
docker build -t federation-directory .
docker run -p 8765:8765 -e DIRECTORY_API_KEY=your-secret-key -v /path/to/data:/data federation-directory
```

## Scripts

- **`scripts/register_server.py`** — Register a server (for use after deploying a public server).  
  `DIRECTORY_URL` and `DIRECTORY_API_KEY` required; `--server-name`, `--base-url` required; optional `--handle`, `--federation-port`.

- **`scripts/fetch_index.py`** — Fetch index and print one `server_name` per line (for building Synapse whitelist).  
  Use `DIRECTORY_URL`; optional `--exclude-server` or `MY_SERVER_NAME` to omit your own server. Use `--json` to print the full response.

## Integration with enterprise-matrix-stack

1. **On public server creation**  
   After generating manifests and deploying a server with `federation.mode: public`, the backend should **POST** to the directory’s `/api/v1/servers/register` with that server’s `server_name`, `base_url`, and optional `handle` / `federation_port`. See [FEDERATION_DIRECTORY.md](../enterprise-matrix-stack/docs/FEDERATION_DIRECTORY.md) for the exact step and example.

2. **Public servers: use the index**  
   Each public Synapse should:
   - Prefer **direct** access to the directory (e.g. call `GET /api/v1/servers` on startup or when needed).
   - Use a **periodic job** (cron or sidecar) to fetch the index and update `federation_domain_whitelist` (e.g. rewrite Synapse config and reload), so the index acts as a **fallback** and keeps the whitelist in sync.

See the same doc for a sample “fetch index and write whitelist” script.

## Invite-only visibility

Users only see rooms and spaces they are invited to or have joined. So “users can only join a server if they have an invitation to at least one Space on that server” is enforced by Matrix: federation is at room/space level; the client can show a Discord-like left sidebar of “all my spaces” (from any federated server) while remaining segmented and isolated per server behind the scenes.
