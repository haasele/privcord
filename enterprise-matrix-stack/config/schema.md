# Config Schema Reference

The master config file (YAML) drives the entire stack. Below are all keys and how they map to the wizard and deployments.

## Wizard Questions → Config Keys

| Wizard question | Config path | Notes |
|-----------------|-------------|--------|
| Server name (handle) | `server.handle` | Lowercase, no spaces (e.g. `mycompany`) |
| Server domain | `server.domain` | e.g. `matrix.example.com` |
| Federation port | `server.federation_port` | Default 8448; only relevant when public |
| Space name | `space.name` | Display name of the auto-created Space |
| Space description | `space.description` | Shown in Space summary |
| Private or Public federation? | `federation.mode` | `private` \| `public` |
| Whitelist (if public) | `federation.whitelist` | List of server names to allow |
| Postgres main password | `databases.postgres_main.password` | Synapse main DB |
| Postgres media password | `databases.postgres_media.password` | Media store DB |
| Postgres federated (optional) | `databases.postgres_federated` | Enable + host/port/password |
| Redis password | `databases.redis.password` | Optional |
| Registration shared secret | `synapse.registration_shared_secret` | Admin registration |
| TURN shared secret | `turn.shared_secret` | TURN auth |
| LiveKit API key/secret | `livekit.api_key`, `livekit.api_secret` | For Element Call SFU |

## Required vs Optional

- **Required:** `server.handle`, `server.domain`, `space.name`, `databases.postgres_main.password`
- **Optional but recommended:** `space.description`, `federation.mode` (default `private`), `turn.*`, `livekit.*`, `synapse.registration_shared_secret`
- **Optional:** `postgres_media`, `postgres_federated`, `server.federation_port`, `federation.whitelist`

## Secrets in Production

Do not commit real passwords. Use placeholders in the config and:

- Provide secrets via environment variables (e.g. `POSTGRES_MAIN_PASSWORD`), or
- Use Kubernetes Secrets and reference them in the generator (e.g. `--secret postgres_main_password=env:POSTGRES_MAIN_PASSWORD`), or
- Use a secret manager (Vault, etc.) and inject at deploy time.

The generator script can read from env: `password: ${POSTGRES_MAIN_PASSWORD}` or from a `.env` file (not committed).
