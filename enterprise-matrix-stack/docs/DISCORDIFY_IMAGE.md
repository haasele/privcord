# Synapse + Discordify image (build and load)

The stack expects the image **synapse-discordify:latest**, which is the official Synapse image with the [Discordify](https://github.com/your-org/API-Addon/tree/main/discordify) module installed.

## Build

From the **API-Addon repo root** (parent of `enterprise-matrix-stack`):

```bash
docker build -t synapse-discordify:latest .
```

The root `Dockerfile` uses `matrixdotorg/synapse:latest` and installs the `discordify` package from `./discordify`.

## Load into K3s (fully isolated container)

When using the K3s-in-container setup, `scripts/bootstrap-k3s.sh` builds and imports the image into the in-container cluster. If you build the image yourself (e.g. at repo root), import it so the cluster can use it:

```bash
docker save synapse-discordify:latest | k3s ctr -n k8s.io images import -
```

Run this inside the K3s container after building; if the image is not in the cluster, Synapse and worker pods will stay in ImagePullBackOff until you import it.

## Fallback

To run without Discordify (plain Synapse), change the image in `k8s/base/synapse.yaml` and `k8s/base/synapse-workers.yaml` back to `matrixdotorg/synapse:latest`. The generated config still loads the Discordify module; remove or override the `modules` section in the generator if you do not want the module.
