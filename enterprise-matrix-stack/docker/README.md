# Run the stack in an Ubuntu container (Kubernetes)

Two options: **fully isolated (KIND)** so nothing runs on your PC, or **k3d** with the cluster on the host.

---

## Option 1: Fully isolated (KIND) — recommended

**Everything runs inside the container**: Docker daemon, KIND cluster, and all workloads. Your PC is not used for the cluster.

### Build

From `enterprise-matrix-stack/`:

```bash
docker build -f docker/Dockerfile.ubuntu-kind -t privcord-kind .
```

### Run

On **cgroup v2** hosts (most recent Linux distros), mount cgroups and use the host cgroup namespace so KIND’s node containers can start:

```bash
docker run -it --rm --privileged \
  --cgroupns=host \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  privcord-kind
```

On **cgroup v1** hosts, `--privileged` alone may be enough; if KIND fails with cgroup errors, add `--cgroupns=host` and `-v /sys/fs/cgroup:/sys/fs/cgroup:rw`.

- **`--privileged`** — required for Docker-in-Docker.
- **`-v /sys/fs/cgroup:/sys/fs/cgroup:rw`** — required on cgroup v2 so the inner Docker/KIND can use cgroups (avoids “failed to enable controllers” / “no such file or directory”).
- Optional: mount the repo to avoid clone: `-v /path/to/API-Addon:/workspace/privcord`.
- Optional: expose ports, e.g. `-p 8008:8008` then inside the container run `kubectl port-forward -n matrix-stack svc/synapse 8008:8008`.

The container will:

1. Start the Docker daemon inside the container.
2. Clone the git repo (or use the mounted path).
3. Run `bootstrap-kind.sh --recreate --build-image` to create a KIND cluster and deploy the stack.
4. Drop you into a shell; run `kubectl get pods -n matrix-stack`. The cluster is **only** inside this container.

To reach services from your PC: keep the container running, then in another terminal run port-forward **inside** the container and publish the port:

```bash
# Terminal 1: run container with port 8008 published
docker run -it --rm --privileged -p 8008:8008 privcord-kind

# Inside the container shell:
kubectl port-forward -n matrix-stack svc/synapse 8008:8008
# Then on your PC: http://localhost:8008
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
