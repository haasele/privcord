# Wizard and Deployment Guide

## Frontend button → automation

### 1. Wizard questions (in order)

Present these to the user when they click **“Create new server”** (or similar). Each question maps to the master config.

| # | Question | Config path | Example |
|---|----------|-------------|---------|
| 1 | Server name (handle, lowercase, no spaces) | `server.handle` | `mycompany` |
| 2 | Base domain for this server | `server.domain` | `matrix.example.com` |
| 3 | Space display name | `space.name` | `My Company Chat` |
| 4 | Space description | `space.description` | `Official company Matrix space.` |
| 5 | Private (no federation) or Public (federated with whitelist)? | `federation.mode` | `private` or `public` |
| 6 | (If public) Federation port | `server.federation_port` | `8448` |
| 7 | (If public) Allowed server names (whitelist) | `federation.whitelist` | `["other.example.com"]` |
| 8 | Postgres main password | `databases.postgres_main.password` | (secret) |
| 9 | Postgres media password | `databases.postgres_media.password` | (secret) |
| 10 | (Optional) Redis password | `databases.redis.password` | (secret) |
| 11 | (Optional) Enable federated Postgres (second instance, different port) | `databases.postgres_federated.enabled` | `false` |
| 12 | Synapse registration shared secret | `synapse.registration_shared_secret` | (secret) |
| 13 | TURN shared secret | `turn.shared_secret` | (secret) |
| 14 | LiveKit API key | `livekit.api_key` | (secret) |
| 15 | LiveKit API secret | `livekit.api_secret` | (secret) |

You can group these into steps (e.g. “Server & Space”, “Federation”, “Databases”, “Secrets”) and validate before submit.

### 2. Backend automation (what runs when user submits)

1. **Build config**  
   From the wizard answers, build a YAML object matching `config/example.yaml` (server, space, federation, databases, synapse, turn, livekit, element_call, deploy).

2. **Generate manifests**  
   - Run: `python3 scripts/generate_manifests.py --config <path> --out k8s/generated --env .env.generated`  
   - Or call the same logic from your backend (e.g. in-process or subprocess) with the built config.

3. **Create namespace**  
   - `kubectl create namespace matrix-<handle>` (or use `deploy.namespace` from config).

4. **Create Secrets**  
   - From wizard passwords and config, create a Kubernetes Secret manifest (or use your secret manager and inject into the cluster).  
   - Apply: `kubectl apply -f k8s/base/secrets.yaml` (after filling from config/env).

5. **Apply base + generated**  
   - Apply namespace, secrets, then in order: postgres-main, postgres-media, redis, (optional postgres-federated), synapse (using generated ConfigMap), livekit, element-call, turn.

6. **Expose services**  
   - Create Ingress (or LoadBalancer) for:  
     - `https://<server.domain>` → Synapse  
     - `https://call.<server.domain>` (or your choice) → Element Call  
     - `wss://livekit.<server.domain>` → LiveKit (if exposed)  
   - Open federation port (e.g. 8448) for federation when `federation.mode: public`.

7. **DNS**  
   - Point the chosen domain(s) to the Ingress/LoadBalancer IP or hostname.

8. **Register with Federation Directory (if public)**  
   - If `federation.mode` is `public`, POST the new server to the central directory so other servers can discover it.  
   - See [FEDERATION_DIRECTORY.md](FEDERATION_DIRECTORY.md) for the API and example; you can use `federation-directory/scripts/register_server.py` with `DIRECTORY_URL` and `DIRECTORY_API_KEY`.

9. **Return to user**  
   - Respond with: server URL, Element Call URL, and “Server is being created” (or wait until Synapse is ready and then return).

### 3. API contract (optional)

If the frontend calls a REST API instead of running scripts directly, the backend can expose:

- **POST /api/v1/servers**  
  Body: JSON mirror of the wizard (e.g. `{ "server_handle": "...", "domain": "...", "space_name": "...", "federation_mode": "private", "passwords": { ... } }`).  
  Response: `{ "job_id": "...", "namespace": "matrix-mycompany", "status": "creating" }`.

- **GET /api/v1/servers/:id**  
  Response: `{ "status": "ready", "homeserver_url": "https://...", "element_call_url": "https://..." }`.

The backend then runs the same steps (build config → generate → kubectl apply) asynchronously.

## Deployment checklist (production)

- [ ] Use a dedicated namespace per deployment (e.g. `matrix-<handle>`).
- [ ] Never commit `secrets.yaml` or `.env` with real passwords; use a secret manager or CI secrets.
- [ ] Set resource requests/limits in manifests (examples are in `k8s/base/`).
- [ ] Use TLS for Synapse, Element Call, and LiveKit (Ingress TLS or LB with certs).
- [ ] For federation (public): restrict to whitelist and ensure Discordify (or same module) on peer servers.
- [ ] Back up Postgres (main and media) and Synapse signing key; document restore.
- [ ] Optionally enable federated Postgres (second instance, different port) for HA or cross-region.
- [ ] TURN: set `realm` and `shared_secret`; expose UDP/TCP/TLS ports as required by your network.
- [ ] LiveKit: use official LiveKit self-hosted or cloud API keys; configure Redis for multi-pod if needed.
- [ ] Run `generate_manifests.py` in CI or from the backend so Synapse config (and space name/description) always matches the wizard.

## Kustomize (optional)

You can add a `kustomization.yaml` in `k8s/base/` to compose all resources and use overlays per environment (e.g. `k8s/overlays/prod`). The generator can still output the Synapse ConfigMap into a generated overlay so one `kubectl apply -k k8s/overlays/prod` deploys everything.
