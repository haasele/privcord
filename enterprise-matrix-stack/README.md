# Enterprise Matrix Stack (K3s in container)

Production-ready example for deploying a **Matrix homeserver (Synapse)** with **Discordify module**, **Synapse workers** (scaled by worker-autoscaler), **Element Call**, **LiveKit SFU**, **lk-jwt-service** (MatrixRTC auth), **Redis**, **PostgreSQL** (main + media + optional federated), and **TURN** on **Kubernetes** — run as a **fully isolated container** (K3s inside the container).

Example server: **matrix.haasele.org** (`config/example.yaml`).

## What this folder contains

- **config/** – Master config (YAML): server handle, domain, space, federation, DB/TURN/LiveKit secrets. Example: `matrix.haasele.org`.
- **k8s/base/** – Kubernetes manifests for the full stack. Apply generated ConfigMaps (from `scripts/generate_manifests.py`) before base.
- **scripts/generate_manifests.py** – Reads the config and generates Synapse config, ConfigMaps, and optional `.env`.
- **scripts/bootstrap-k3s.sh** – Used by the K3s-in-container image: generate manifests, create namespace, apply secrets and base, build/load images, deploy the stack.
- **docker/** – `Dockerfile.ubuntu-k3s` and `entrypoint-k3s.sh` for the single fully isolated container (Docker + K3s inside).
- **backend/** – Minimal Flask API for the **Create new server** wizard (POST /api/v1/servers).
- **docs/** – Deployment guide and ports/URLs.

## Quick start

1. Copy and edit the config:
   ```bash
   cp config/example.yaml config/my-deployment.yaml
   # Edit server.handle, server.domain, space.name, space.description,
   # federation.mode (private | public), whitelist, and all passwords.
   ```

2. Generate manifests and env:
   ```bash
   pip install pyyaml
   python3 scripts/generate_manifests.py --config config/my-deployment.yaml --out k8s/generated --env .env.generated
   ```

3. Create secrets (do not commit):
   ```bash
   cp k8s/base/secrets.example.yaml k8s/base/secrets.yaml
   # Fill secrets.yaml from .env.generated or your secret store.
   kubectl apply -f k8s/base/namespace.yaml
   kubectl apply -f k8s/base/secrets.yaml
   ```

4. Apply generated Synapse config and base resources:
   ```bash
   kubectl apply -f k8s/generated/synapse-configmap.yaml
   kubectl apply -f k8s/base/postgres-main.yaml
   kubectl apply -f k8s/base/postgres-media.yaml
   kubectl apply -f k8s/base/redis.yaml
   kubectl apply -f k8s/base/synapse.yaml   # use generated ConfigMap
   kubectl apply -f k8s/base/livekit.yaml
   kubectl apply -f k8s/base/element-call.yaml
   kubectl apply -f k8s/base/turn.yaml
   ```

5. Expose services (Ingress/LoadBalancer) for your domain and federation port; point DNS to the cluster.

## Frontend “wizard” flow (button → new instance)

When the user presses **“Create new server”** (or equivalent) in your frontend client:

1. **Collect answers** (see [config/schema.md](config/schema.md)):
   - Server name (handle)
   - Domain for the deployment
   - Space name and description
   - Private (non-federated) vs Public (federated with whitelist + custom port)
   - Passwords for Postgres main, Postgres media, Redis (optional), Synapse registration secret, TURN secret, LiveKit API key/secret

2. **Call your backend** with this payload. The backend should:
   - Build the master config (e.g. `config/example.yaml` structure) from the answers.
   - Run `generate_manifests.py` to produce Synapse config and (optionally) env.
   - Create a new **Kubernetes namespace** (e.g. `matrix-<handle>`).
   - Create **Secrets** from the provided passwords (or from your secret manager).
   - Apply the **base manifests** plus the **generated Synapse ConfigMap**.
   - Optionally create **Ingress** and **DNS** so the server is reachable at the chosen domain.

3. **Result:** A new k3s instance with:
   - Synapse (with Discordify: auto Space, channels, roles)
   - Redis
   - Postgres (main + media; optional federated Postgres on another port)
   - LiveKit SFU (Element Call backend)
   - Element Call frontend
   - TURN server

See [docs/WIZARD_AND_DEPLOYMENT.md](docs/WIZARD_AND_DEPLOYMENT.md) for a detailed wizard spec and deployment checklist.

## Config reference

| Section | Purpose |
|--------|---------|
| `server` | Handle, domain, federation port |
| `space` | Auto-created Space name, description |
| `federation` | `private` (non-federated) or `public` (whitelist + port) |
| `databases` | Postgres main/media/federated, Redis – hosts, users, passwords |
| `synapse` | Discordify channels/roles, registration secret, signing key path |
| `turn` | TURN host, ports, shared secret, realm |
| `livekit` | LiveKit host, port, API key/secret, WebSocket URL |
| `element_call` | Element Call base URL |
| `deploy` | Kubernetes namespace, image pull secrets, resource overrides |

Full schema: [config/schema.md](config/schema.md).

## Private vs public federation

- **Private:** `federation.mode: private`. Synapse is not federated; no federation listener or whitelist.
- **Public:** `federation.mode: public`. Federation enabled; only servers in `federation.whitelist` are allowed. Use `server.federation_port` (e.g. 8448) and ensure the same Discordify module (and compatible config) is used on whitelisted servers.

## Requirements

- Kubernetes or k3s cluster
- `kubectl` configured
- (Optional) Ingress controller and DNS for domain and federation
- PyYAML for the generator script

## License and disclaimer

This is an **example** layout for production-style deployment. Adapt to your security and ops requirements (e.g. use Sealed Secrets, Vault, or a proper CI/CD pipeline instead of applying manifests by hand). Image tags and resource limits should be tuned per your environment.
