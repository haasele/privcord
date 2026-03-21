# AGENTS.md

## Cursor Cloud specific instructions

### Codebase overview

This is a Discord-like Matrix communication platform (DRCK) consisting of:

| Service | Location | Tech | Port |
|---|---|---|---|
| **Frontend** (Element Web) | `frontend/` | TypeScript/React, pnpm, webpack | 8080 |
| **Enterprise Backend** | `enterprise-matrix-stack/backend/` | Python/Flask | 5000 |
| **Federation Directory** | `federation-directory/` | Python/Flask | 8765 |
| **Discordify Module** | `discordify/` | Python (Synapse module) | — |
| **Frontend Client** (Desktop) | `frontend-client/` | Electron/yarn | — |
| **Worker Autoscaler** | `worker-autoscaler/` | Python | — |

### Running services

- **Frontend**: `cd frontend && pnpm start` — serves at http://localhost:8080. Requires `config.json` (copy from `config.sample.json`). Set `default_theme` to `"element"` in `config.json` to avoid theme resolution errors. Node.js >=22.18 and pnpm are required.
- **Federation Directory**: `cd federation-directory && source /workspace/.venv/bin/activate && DIRECTORY_API_KEY=test-secret-key DIRECTORY_DATA_PATH=./data/servers.json python -m federation_directory` — serves at http://localhost:8765.
- **Enterprise Backend**: `cd enterprise-matrix-stack/backend && source /workspace/.venv/bin/activate && ENABLE_DEPLOY=0 python app.py` — serves at http://localhost:5000.

### E2E testing with Docker Compose

The full backend stack (Synapse + Discordify + Postgres + Redis) can be run locally via Docker Compose:
1. Install Docker and configure with fuse-overlayfs storage driver (for container environments)
2. Generate config: `cd enterprise-matrix-stack && python3 scripts/generate_manifests.py --config config/e2e-docker.yaml --out e2e-generated`
3. Add `enable_registration: true` and proper `listeners` config to `e2e-generated/homeserver.yaml`
4. Remove `password: ""` from redis config (causes AUTH errors when Redis has no password)
5. Start: `cd enterprise-matrix-stack && docker compose -f docker-compose.e2e.yml up -d --build`
6. Fix volume permissions: see `scripts/run-e2e-docker.sh`
7. Point frontend `config.json` at `http://localhost:8008` as homeserver

### Testing

- **Frontend unit tests**: `cd frontend && pnpm test` — runs Jest. Individual test files can be run with `npx jest --testPathPatterns="<path>"`. The full suite is large and may take 8+ minutes.
- **Frontend lint**: `cd frontend && pnpm lint` — runs TypeScript type checks, ESLint, stylelint, and workflow linting.
- **Discordify tests**: `cd discordify && source /workspace/.venv/bin/activate && pytest` — 13 unit tests.

### Gotchas

- The Python virtual environment is at `/workspace/.venv`. Activate it before running any Python service.
- inotify limits should be increased for webpack file watching: `sudo sysctl fs.inotify.max_user_watches=131072 fs.inotify.max_user_instances=512`.
- `pnpm install` may warn about ignored build scripts for `esbuild` and `unrs-resolver`; this is expected from the `pnpm.onlyBuiltDependencies` config.
- The frontend desktop client (`frontend-client/`) uses yarn (not pnpm) and is optional for web development.
- K3s cannot run inside Cloud Agent VMs due to cgroup v2 and CNI limitations. Use Docker Compose for E2E testing instead.
- The Discordify module uses Synapse's `ModuleApi`. Key methods: `get_state_events_in_room`, `create_and_send_event_into_room`, `create_room(user_id, config_dict)`. Background tasks must use `twisted.internet.defer.ensureDeferred()` instead of `asyncio.create_task()`.
- When creating a Space in the Element frontend, Element also runs its own channel creation wizard alongside Discordify's auto-creation. The Discordify-created channels ("general", "Voice") appear alongside Element's ("General", "Random").
