# Ports and URLs Overview

Use this guide to access services when running the stack locally.

---

## 1. Fully isolated: K3s inside the container (recommended)

K3s runs in the **same** container. No host cluster.

```bash
cd enterprise-matrix-stack
docker build -f docker/Dockerfile.ubuntu-k3s -t privcord-k3s .
docker run -it --rm --privileged --cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw -p 8008:8008 privcord-k3s
```

Inside the container: `kubectl get pods -n matrix-stack`. To reach Synapse from your PC: `kubectl port-forward -n matrix-stack svc/synapse 8008:8008`, then http://localhost:8008.

Example config domain: **matrix.haasele.org**. Point that domain (or localhost) at your machine for client testing.

---

## 2. Port-forwards (K3s in container)

After bootstrap, use port-forward to access services from your machine:

```bash
# Inside the container (or with KUBECONFIG pointing at the in-container cluster):

# Synapse (client API)
kubectl port-forward -n matrix-stack svc/synapse 8008:8008 &
# → http://localhost:8008

# Synapse federation
kubectl port-forward -n matrix-stack svc/synapse 8448:8448 &

# Element Call (if deployed)
kubectl port-forward -n matrix-stack svc/element-call 8080:80 &
# → http://localhost:8080
```

| Component         | Cluster service      | Typical port-forward | URL (after port-forward) |
|-------------------|----------------------|----------------------|---------------------------|
| Synapse           | synapse (8008, 8448) | 8008, 8448           | http://localhost:8008     |
| Element Call      | element-call (80)    | 8080→80              | http://localhost:8080    |
| LiveKit           | livekit (7880, 7881) | 7880, 7881           | ws://localhost:7880       |
| lk-jwt-service    | lk-jwt-service (8080)| 8081→8080            | http://localhost:8081     |
| TURN              | turn (3478, 5349)    | 3478, 5349           | udp/tcp as configured    |
| Postgres main     | postgres-main (5432) | 5432                 | localhost:5432 (debug)    |
| Postgres media    | postgres-media (5432)| 5433→5432            | localhost:5433 (debug)    |
| Postgres metadata | postgres-metadata (5432) | 5434→5432        | localhost:5434 (debug)    |
| Redis             | redis (6379)         | 6379                 | localhost:6379 (debug)    |

---

## 3. Docker Compose E2E (optional local test)

From the repo root (or `enterprise-matrix-stack/`):

```bash
cd enterprise-matrix-stack
./scripts/run-e2e-docker.sh
```

Then use **host** URLs on localhost (see `config/e2e-docker.yaml`): Synapse 8008, Backend 5000, Postgres/Redis as listed in that config.

---

## 4. Quick reference

| What you want to do           | URL / command |
|------------------------------|---------------|
| Check Synapse is up           | `curl http://localhost:8008/_matrix/client/versions` |
| Open Element                 | Point app to `http://localhost:8008` (or your domain) |
| Domain for example config    | **matrix.haasele.org** — set in `config/example.yaml` |
