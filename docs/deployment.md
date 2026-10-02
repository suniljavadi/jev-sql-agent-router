# Deployment notes

## Local Compose

The Compose project runs three services:

- `db`: PostgreSQL 16 with persistent `postgres_data`, no published host port.
- `api`: FastAPI, waits for database health, initializes tables, exposes `/health`, and has egress for configured LLM/Jev providers.
- `ui`: Streamlit, waits for API health and reaches it through the private Compose network.

Both application services use the same Python 3.12 image, run as UID 10001, have a read-only root filesystem, drop Linux capabilities, and use writable temporary filesystems. Published ports bind to `127.0.0.1`; the API and UI do not have TLS by themselves. PostgreSQL resides on an internal network.

```powershell
Copy-Item .env.example .env
# Set POSTGRES_PASSWORD, API_KEY, and REVIEWER_API_KEY to independent URL-safe random values.
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
docker compose --env-file .env logs -f api ui
docker compose --env-file .env down
```

The `postgres_data` volume persists after `down`. Do not remove it except when intentionally deleting all local deployment data. Compose config validation checks YAML and interpolation; it does not prove that images build, the daemon is healthy, or network access to external providers works.

## Production changes required

Do not deploy the sample `.env` values. Inject secrets from a secret manager, configure TLS and a trusted ingress, use an identity provider and role-based reviewer identity rather than the shared reviewer key, and add rate limits. Set CPU/memory and database connection limits, backups, monitoring, and key rotation. API keys in this demo are static shared bearer secrets with constant-time equality checks; they are not user identities or a replacement for SSO.

Application startup applies the checked-in Alembic revision before seeding. The initial revision creates missing tables and adopts existing model-created tables, preserving local development databases. Review existing production schemas before applying this baseline. Each later schema change must add and review a new Alembic revision; `scripts.setup_db` applies revisions without starting the API. A review claimed by a process that crashes may stay in `processing`; production needs an operational recovery/reconciliation policy. Use a restricted database role, keep PostgreSQL unreachable from the host, and retain the internal database network. External provider connections require API egress, so deployment firewalls should allow only required destinations where possible.

Configure the actual TypeSafe Jev API endpoint and schema only after verifying current vendor documentation. The current `TypeSafeJevProvider` payload is an isolated sample adapter contract, not an official schema assertion. Enable live providers only with both distinct `API_KEY` and `REVIEWER_API_KEY` set.