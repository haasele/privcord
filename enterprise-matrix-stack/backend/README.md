# Create Server API (Connecting branch)

Minimal Flask backend for the **Create new server** wizard in the Element frontend.

## Endpoints

- **POST /api/v1/servers** – Accepts wizard JSON (see frontend `CreateServerPayload`), builds config, runs `generate_manifests.py`, and optionally runs `kubectl apply`. Returns `job_id`, `namespace`, `status`.
- **GET /api/v1/servers/:job_id** – Returns status and URLs for the deployment.
- **GET /health** – Health check.

## Run locally

```bash
cd enterprise-matrix-stack/backend
pip install -r requirements.txt
export STACK_DIR=/path/to/enterprise-matrix-stack   # default: parent of backend/
# Optional: set ENABLE_DEPLOY=1 to run kubectl apply (requires kubeconfig)
export ENABLE_DEPLOY=0
python app.py
```

Then set the frontend config `server_creation_api_url` to `http://localhost:5000` (or your host).

## Environment

| Variable        | Description |
|----------------|-------------|
| `STACK_DIR`    | Path to enterprise-matrix-stack (default: parent of backend). |
| `ENABLE_DEPLOY`| Set to `1` to run `kubectl apply` after generating manifests. |
| `PORT`         | Server port (default 5000). |

## Note

Deployments currently target the default namespace `matrix-stack`. Per-handle namespaces (e.g. `matrix-mycompany`) can be added by generating and applying namespace-specific manifests.
