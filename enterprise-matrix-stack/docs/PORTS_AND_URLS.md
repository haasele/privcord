# Ports and URLs Overview

Use this guide to access services when testing the [privcord](https://github.com/haasele/privcord) stack locally (Docker E2E or k3d).

---

## 1. Docker Compose E2E (local test)

From the repo root (or `enterprise-matrix-stack/`):

```bash
cd enterprise-matrix-stack
./scripts/run-e2e-docker.sh
```

Then use these **host** URLs and ports (all on `localhost` unless you changed `config/e2e-docker.yaml`):

| Service           | Port | URL / usage |
|-------------------|------|-------------|
| **Synapse**       | 8008 | `http://localhost:8008` — Client-Server API, `/_matrix/client/versions` |
| **Synapse federation** | 8448 | `https://localhost:8448` — Federation (not exposed by default in E2E) |
| **Backend (Create Server API)** | 5000 | `http://localhost:5000` — `POST /api/v1/servers`, `GET /api/v1/servers/:id`, `GET /health` |
| **Postgres main**  | 5432 | `localhost:5432` — DB `synapse`, user `synapse` (for debugging only) |
| **Postgres media** | 5433 | `localhost:5433` — DB `synapse_media` (for debugging only) |
| **Postgres metadata** | 5434 | `localhost:5434` — DB `metadata` (backend jobs) |
| **Redis**          | 6379 | `localhost:6379` — Synapse caches (for debugging only) |

**Frontend (Element):** Run separately and point it at Synapse:

```bash
cd frontend
npm start
# In config or .env: set base URL to http://localhost:8008
# Registration: enable in Synapse (registration_shared_secret is set in e2e-docker.yaml)
```

**Stop E2E stack:**

```bash
cd enterprise-matrix-stack
docker compose -f docker-compose.e2e.yml down
```

---

## 2. Ubuntu container: clone repo and run on Kubernetes (k3d)

Docker is used only as an **isolated environment** (one Ubuntu container). The stack runs in **Kubernetes** via k3d (the container uses the host Docker socket so k3d can create the cluster).

**Build and run:**

```bash
cd enterprise-matrix-stack
docker build -f docker/Dockerfile.ubuntu-k8s -t privcord-k8s .
docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock -p 8443:8443 privcord-k8s
```

The container will: pull the latest Ubuntu image (as base), clone the git repo, and run `bootstrap-k3d.sh --recreate --build-image` so the stack runs in a k3d cluster. You get a shell inside the container with `KUBECONFIG` set; use `kubectl get pods -n matrix-stack` and port-forwards as in section 3. To use the same cluster from the host, run:

```bash
export KUBECONFIG=$(k3d kubeconfig write matrix-local)
kubectl get pods -n matrix-stack
```

**Optional env vars:** `REPO_URL`, `CLONE_DIR`, `CLUSTER_NAME`, `KEEP_ALIVE=0` (exit after bootstrap instead of dropping to shell).

---

## 3. k3d deployment (full stack)

After running `./scripts/bootstrap-k3d.sh` (from `enterprise-matrix-stack/`), services run **inside** the cluster. There is no Ingress by default, so use **port-forward** to access them from your machine:

```bash
export KUBECONFIG=$(k3d kubeconfig write matrix-local)

# Synapse (client API)
kubectl port-forward -n matrix-stack svc/synapse 8008:8008 &
# → http://localhost:8008

# Synapse federation
kubectl port-forward -n matrix-stack svc/synapse 8448:8448 &

# Element Call (if deployed)
kubectl port-forward -n matrix-stack svc/element-call 8080:80 &
# → http://localhost:8080

# Backend (if you deploy it in the cluster)
# kubectl port-forward -n matrix-stack svc/backend 5000:5000 &
# → http://localhost:5000
```

**k3d load balancer:** The bootstrap script maps `8443:443` on the k3d load balancer. If you add an Ingress that uses TLS on port 443, you would use `https://localhost:8443` (or your configured hostname).

| Component        | Cluster service      | Typical port-forward | URL (after port-forward) |
|------------------|----------------------|----------------------|---------------------------|
| Synapse          | synapse (8008, 8448) | 8008, 8448           | http://localhost:8008    |
| Element Call     | element-call (80)    | 8080→80              | http://localhost:8080    |
| LiveKit          | livekit (7880, 7881) | 7880, 7881           | ws://localhost:7880      |
| lk-jwt-service   | lk-jwt-service (8080)| 8081→8080            | http://localhost:8081    |
| TURN             | turn (3478, 5349)    | 3478, 5349           | udp/tcp as configured    |
| Postgres main    | postgres-main (5432) | 5432                 | localhost:5432 (debug)   |
| Postgres media   | postgres-media (5432)| 5433→5432            | localhost:5433 (debug)   |
| Postgres metadata| postgres-metadata (5432) | 5434→5432        | localhost:5434 (debug)   |
| Redis            | redis (6379)         | 6379                 | localhost:6379 (debug)   |
| Backend          | (not in base K8s)    | 5000                 | http://localhost:5000    |

**Domain:** In k3d, `server.domain` from your config (e.g. `matrix.example.com`) must resolve to your machine or localhost for the client. Use `/etc/hosts` or a local DNS to point that domain to `127.0.0.1` when testing.

---

## 4. Quick reference (Docker E2E)

| What you want to do        | URL / command |
|----------------------------|---------------|
| Check Synapse is up         | `curl http://localhost:8008/_matrix/client/versions` |
| Check Backend is up         | `curl http://localhost:5000/health` |
| Open Element (after npm start) | Point app to `http://localhost:8008` |
| Create server (wizard API)  | `POST http://localhost:5000/api/v1/servers` (JSON body, see backend README) |
| Stop everything             | `docker compose -f docker-compose.e2e.yml down` |
