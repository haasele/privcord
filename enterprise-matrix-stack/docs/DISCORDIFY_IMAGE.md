# Synapse + Discordify image (build and load)

The stack expects the image **synapse-discordify:latest**, which is the official Synapse image with the [Discordify](https://github.com/your-org/API-Addon/tree/main/discordify) module installed.

## Build

From the **API-Addon repo root** (parent of `enterprise-matrix-stack`):

```bash
docker build -t synapse-discordify:latest .
```

The root `Dockerfile` uses `matrixdotorg/synapse:latest` and installs the `discordify` package from `./discordify`.

## Load into k3d

If you use k3d, load the image so the cluster can pull it:

```bash
k3d image import synapse-discordify:latest -c matrix-local
```

Use the same cluster name as in `bootstrap-k3d.sh` (default `matrix-local`). Run this after building and before or after applying the stack; if the image is not in the cluster, Synapse and worker pods will stay in ImagePullBackOff until you import it.

## Fallback

To run without Discordify (plain Synapse), change the image in `k8s/base/synapse.yaml` and `k8s/base/synapse-workers.yaml` back to `matrixdotorg/synapse:latest`. The generated config still loads the Discordify module; remove or override the `modules` section in the generator if you do not want the module.
