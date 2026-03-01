# Federation Directory integration

The **Federation Directory** (in repo root: `federation-directory/`) is the central index for public Matrix servers. Public servers register there when created and fetch the index to build their federation whitelist (direct first, index as fallback).

## 1. When creating a public server (POST to index)

After you deploy a **public** server (e.g. via the wizard with `federation.mode: public`), the backend must **register** it with the directory so other servers can discover it.

### Step (in your backend)

After successful deploy (or after Synapse is ready):

1. Read from your config: `server.domain`, `server.handle`, `server.federation_port`, and the public base URL (e.g. `https://<server.domain>`).
2. `POST` to the directory:

   ```
   POST <DIRECTORY_BASE_URL>/api/v1/servers/register
   Authorization: Bearer <DIRECTORY_API_KEY>
   Content-Type: application/json

   {
     "server_name": "<server.domain>",
     "base_url": "https://<server.domain>",
     "handle": "<server.handle>",
     "federation_port": <server.federation_port or 8448>
   }
   ```

3. Store `DIRECTORY_BASE_URL` and `DIRECTORY_API_KEY` in your deployment config or secrets; the wizard/backend needs them only for public servers.

### Example (curl)

```bash
DIRECTORY_URL="https://directory.example.com"
DIRECTORY_API_KEY="your-secret"
SERVER_DOMAIN="matrix.mycompany.com"
BASE_URL="https://matrix.mycompany.com"
HANDLE="mycompany"
FEDERATION_PORT="8448"

curl -s -X POST "${DIRECTORY_URL}/api/v1/servers/register" \
  -H "Authorization: Bearer ${DIRECTORY_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"server_name\":\"${SERVER_DOMAIN}\",\"base_url\":\"${BASE_URL}\",\"handle\":\"${HANDLE}\",\"federation_port\":${FEDERATION_PORT}}"
```

### Optional: call from generator

You can add an optional step in your automation (e.g. after `generate_manifests.py` and deploy) that, when `federation.mode == "public"`, calls a small script or HTTP client to perform this POST. The generator itself does not need to know the directory URL; that can be an env var in the environment that runs the “post-deploy register” step.

## 2. Public servers: fetch index (direct first, index as fallback)

Each **public** Synapse should use the directory index to build or refresh its `federation_domain_whitelist`:

- **Prefer direct:** On startup or when needed, call `GET <DIRECTORY_BASE_URL>/api/v1/servers` (e.g. from a sidecar or init container).
- **Fallback:** If the directory is unreachable, use a **cached** copy of the index (e.g. last successful fetch written to a file or ConfigMap) so Synapse still has a whitelist.
- **Periodic refresh:** Run a cron or loop that fetches the index, writes the new whitelist (see below), and triggers a Synapse config reload (e.g. rewrite `homeserver.yaml` and send SIGHUP, or restart the container).

### Whitelist format

From the index response, build the list of server names (e.g. `[s["server_name"] for s in data["servers"]]`). In Synapse config:

```yaml
federation_domain_whitelist:
  - matrix.server-a.com
  - matrix.server-b.com
```

Exclude your **own** `server_name` from this list.

### Example script: fetch index and print whitelist

In this repo, use the provided script (from repo root):

```bash
DIRECTORY_URL=https://directory.example.com MY_SERVER_NAME=matrix.mycompany.com \
  python3 federation-directory/scripts/fetch_index.py
```

Output is one `server_name` per line; use that list to build `federation_domain_whitelist`. Run from a sidecar or cron, then write the result into `homeserver.yaml` (or a ConfigMap) and reload Synapse.

## 3. Invite-only visibility (no extra code)

Users only see rooms and spaces they are invited to or have joined. So “users can only join a server if they have an invitation to at least one Space on that server” is already the Matrix model: you don’t “join a server” as a second account; you get invited to a **space (or room)** on another server and accept. Once you’re in that space, federation is “on” for that path; the client can show a Discord-like left sidebar of all your spaces (from any federated server) while remaining segmented per server under the hood. No extra logic is required in the directory or Synapse for this.

## Summary

| Action | Who | What |
|--------|-----|------|
| Create public server | Your backend / wizard | After deploy, POST to directory `/api/v1/servers/register` with server_name, base_url, handle, federation_port. |
| Use index | Each public Synapse | GET `/api/v1/servers` (direct first; cache as fallback). Periodically refresh and update `federation_domain_whitelist`, then reload Synapse. |
| Invite-only | Matrix / client | Handled by invites and membership; directory only stores the list of public servers. |
