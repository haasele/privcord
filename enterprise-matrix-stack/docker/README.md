# Run the stack in a fully isolated container (K3s)

Everything runs inside one container: Docker daemon (for building images), **K3s server**, and all workloads. No host cluster, no KIND.

Example server: **matrix.haasele.org** (see `config/example.yaml`).

---

## Build & run (K3s)

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

The container will: start Docker, start **K3s** in this container, clone the repo (or use the mounted path), run `scripts/bootstrap-k3s.sh --build-image`, then drop to a shell. Run `kubectl get pods -n matrix-stack`.

---

## Env vars

| Variable     | Default                                  | Description |
|-------------|-------------------------------------------|-------------|
| `REPO_URL`  | `https://github.com/haasele/privcord.git` | Git URL to clone. |
| `CLONE_DIR` | `/workspace/privcord`                     | Directory to clone into. |
| `KEEP_ALIVE`| `1`                                       | `0` = exit after bootstrap; `1` = drop to shell. |
