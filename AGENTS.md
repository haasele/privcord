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

- **Frontend**: `cd frontend && pnpm start` — serves at http://localhost:8080. Requires `config.json` (copy from `config.sample.json`). Set `default_theme` to `"element"` in `config.json` to avoid theme resolution errors. Node.js >=22.18 and pnpm are required. Pre-existing PostCSS errors in `_PersistentCallBar.pcss` (undefined CSS variables) cause webpack compilation errors but do not block the dev server.
- **Federation Directory**: `cd federation-directory && source /workspace/.venv/bin/activate && DIRECTORY_API_KEY=test-secret-key DIRECTORY_DATA_PATH=./data/servers.json python -m federation_directory` — serves at http://localhost:8765.
- **Enterprise Backend**: `cd enterprise-matrix-stack/backend && source /workspace/.venv/bin/activate && ENABLE_DEPLOY=0 python app.py` — serves at http://localhost:5000.

### Testing

- **Frontend unit tests**: `cd frontend && pnpm test` — runs Jest. Individual test files can be run with `npx jest --testPathPatterns="<path>"`. The full suite is large and may take 8+ minutes.
- **Frontend lint**: `cd frontend && pnpm lint` — runs TypeScript type checks, ESLint, stylelint, and workflow linting. Pre-existing lint errors exist in the `Connecting` branch.
- **Discordify tests**: `cd discordify && source /workspace/.venv/bin/activate && pytest` — 13 unit tests.

### Gotchas

- The Python virtual environment is at `/workspace/.venv`. Activate it before running any Python service.
- inotify limits should be increased for webpack file watching: `sudo sysctl fs.inotify.max_user_watches=131072 fs.inotify.max_user_instances=512`.
- `pnpm install` may warn about ignored build scripts for `esbuild` and `unrs-resolver`; this is expected from the `pnpm.onlyBuiltDependencies` config.
- The frontend desktop client (`frontend-client/`) uses yarn (not pnpm) and is optional for web development.
