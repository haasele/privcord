# Run the stack in an Ubuntu container (Kubernetes)

Three options: **fully isolated with K3s** (recommended), **fully isolated with KIND** (often fails in DinD), or **k3d** with the cluster on the host.

---

## Option 1: Fully isolated — K3s (recommended)

**Everything runs inside the container**: Docker daemon (for building images only), **K3s server** (runs in this container, no nested node), and all workloads. No KIND — avoids control-plane timeouts in Docker-in-Docker.

### Build

From `enterprise-matrix-stack/`:

```bash
docker build -f docker/Dockerfile.ubuntu-k3s -t privcord-k3s .
```

### Run

On **cgroup v2** hosts, use the same cgroup mount as for any DinD:

```bash
docker run -it --rm --privileged \
  --cgroupns=host \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  privcord-k3s
```

Optional: `-v /path/to/API-Addon:/workspace/privcord` to use your repo; `-p 8008:8008` then inside the container run `kubectl port-forward -n matrix-stack svc/synapse 8008:8008` to reach Synapse from your PC.

The container will: start Docker (for builds), start **K3s server** in this container, clone repo, run `bootstrap-k3s.sh --build-image`, then drop to a shell. Run `kubectl get pods -n matrix-stack`.

---

## Option 1b: Fully isolated — KIND (alternative)

**Everything inside the container** via KIND. Often fails with “control plane not healthy” in Docker-in-Docker; use Option 1 (K3s) if that happens.

### Build & run

```bash
docker build -f docker/Dockerfile.ubuntu-kind -t privcord-kind .
docker run -it --rm --privileged --cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw privcord-kind
```

---

## Option 2: k3d (cluster on host)

The container only runs the bootstrap script; the Kubernetes cluster and workloads run on **your host PC** (via the Docker socket).

**Where does the cluster run?** Because the container mounts the host Docker socket, k3d creates the cluster on your host. So `kubectl` on your PC talks to that cluster (fix kubeconfig with `127.0.0.1` as below).

### Build

```bash
docker build -f docker/Dockerfile.ubuntu-k8s -t privcord-k8s .
```

### Run

```bash
docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock --network host privcord-k8s
```

- **`-v /var/run/docker.sock:/var/run/docker.sock`** — required so k3d creates the cluster on the host.
- **`--network host`** — recommended so kubectl inside the container can reach the API server.

### Using kubectl from your PC

```bash
export KUBECONFIG=$(k3d kubeconfig write matrix-local)
sed -i.bak 's|https://0.0.0.0:|https://127.0.0.1:|g' "$KUBECONFIG"
kubectl get pods -n matrix-stack
```

---

## Env vars (both options)

| Variable       | Default                          | Description |
|----------------|-----------------------------------|-------------|
| `REPO_URL`     | `https://github.com/haasele/privcord.git` | Git URL to clone. |
| `CLONE_DIR`    | `/workspace/privcord`            | Directory to clone into. |
| `CLUSTER_NAME` | `matrix-local`                   | Cluster name (kind/k3d). |
| `KEEP_ALIVE`   | `1`                              | `0` = exit after bootstrap; `1` = drop to shell. |
