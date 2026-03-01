# Run the stack in an Ubuntu container (Kubernetes via k3d)

Docker is used only as an **isolated environment**: one Ubuntu container where we clone the repo and run the **Kubernetes** stack with k3d. The stack does **not** run as Docker Compose inside the container; it runs as a k3d cluster (using the host Docker socket).

## Build

From `enterprise-matrix-stack/`:

```bash
docker build -f docker/Dockerfile.ubuntu-k8s -t privcord-k8s .
```

## Run

```bash
docker run -it --rm -v /var/run/docker.sock:/var/run/docker.sock -p 8443:8443 privcord-k8s
```

- **`-v /var/run/docker.sock:/var/run/docker.sock`** — required so k3d can create the cluster on the host.
- **`-p 8443:8443`** — optional; maps k3d load balancer port if you use Ingress on 443.

The container will:

1. Clone the git repo (default: `https://github.com/haasele/privcord.git`).
2. Run `bootstrap-k3d.sh --recreate --build-image` to create a k3d cluster and deploy the stack.
3. Drop you into a shell with `KUBECONFIG` set; use `kubectl get pods -n matrix-stack` and port-forwards as in [PORTS_AND_URLS.md](../docs/PORTS_AND_URLS.md).

## Env vars

| Variable       | Default                          | Description |
|----------------|-----------------------------------|-------------|
| `REPO_URL`     | `https://github.com/haasele/privcord.git` | Git URL to clone. |
| `CLONE_DIR`    | `/workspace/privcord`            | Directory to clone into. |
| `CLUSTER_NAME` | `matrix-local`                   | k3d cluster name. |
| `KEEP_ALIVE`   | `1`                              | `0` = exit after bootstrap; `1` = drop to shell. |

## Using the cluster from the host

After the container has created the cluster, you can use it from the host:

```bash
export KUBECONFIG=$(k3d kubeconfig write matrix-local)
kubectl get pods -n matrix-stack
```

The cluster keeps running even if the Ubuntu container is stopped.
