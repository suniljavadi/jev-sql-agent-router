# Jev SQL Agent Router

[![CI](https://github.com/suniljavadi/jev-sql-agent-router/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/suniljavadi/jev-sql-agent-router/actions/workflows/ci.yml)

A runnable SQL assistant combining an LLM proposal with TypeSafe's Jev decision model. Local mode runs without credentials or external services using deterministic mock providers and seeded SQLite data. The live adapter follows TypeSafe's documented [System One API](https://docs.typesafe.ai/api): it sends a typed Choice question and maps the returned choice, confidence, and probabilities into the app's action model.

## What Jev does

TypeSafe AI's Jev is used here as a decision model: it receives application state, the request, possible actions and decision questions and returns a structured choice with confidence. Unlike the LLM, which translates language into SQL or intent, Jev selects the workflow action. This separation allows a fast decision path, independent confidence thresholds and an auditable router. Live usage requires verification against TypeSafe's current documentation and credentials; the local mock is not a measurement of model quality, speed or cost.

## Architecture and request lifecycle

`User -> FastAPI -> LLM -> Jev -> Router -> Security validator / SQL executor / retry / clarification / rejection / review / tool selection -> database -> audit`. See [architecture](docs/architecture.md) and [decision flow](docs/jev_decision_flow.md).

1. FastAPI validates the request. The LLM returns SQL or a clarification/unsupported intent.
2. SQL is prechecked; Jev receives the state, request, available actions and decision questions.
3. The router applies confidence policy. At >= 0.90 a safe SELECT can execute; 0.70-0.90 triggers strict read-only validation; below 0.70 it requires human review. Non-execute actions do not execute SQL.
4. The security service checks the SQL again. The executor enforces timeouts, row limits and bounded transient retries. The response and audit row contain Jev's proposal, final action, security status, result and duration. Human review creates a pending queue item; reviewer approval revalidates SQL strictly and writes a separate resolution audit, while rejection executes nothing.

## Installation (Windows PowerShell, Python 3.12)

```powershell
cd 'c:\Users\javad\New folder\jev-sql-agent-router'
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.seed_data
```

Python 3.12 is required for the supported runtime/Docker image. On this workspace machine only Python 3.14 was available during validation; install 3.12 to reproduce the documented commands. From the project root, run in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
.\.venv\Scripts\python.exe -m streamlit run streamlit_app/app.py --server.port 8501
```

Open http://localhost:8000/docs for Swagger and http://localhost:8501 for the dashboard. The API applies Alembic migrations and seeds an empty DB on startup. To apply migrations manually use `.\.venv\Scripts\python.exe -m scripts.setup_db`; seed with `.\.venv\Scripts\python.exe -m scripts.seed_data`. To run all tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Environment variables

Copy `.env.example` and override only what you need. `DATABASE_URL` defaults to `sqlite:///./jev_agent.db`; PostgreSQL uses `postgresql+psycopg://user:password@host/dbname` and a restricted database role. `JEV_PROVIDER=mock|typesafe`, `JEV_BASE_URL` (defaults to `https://api.typesafe.ai/v1/systemone`), `JEV_MODEL` (defaults to `jev-latest`), and `TYPESAFE_API_KEY` select Jev. The TypeSafe adapter sends a `state`, `model`, and `questions.selected_action` Choice question, then reads `answers.selected_action.choice`, `confidence`, and `probabilities`. See the official [API reference](https://docs.typesafe.ai/api) and [Python quick start](https://docs.typesafe.ai/introduction/quickstart). `LLM_PROVIDER=mock|openai_compatible`, `LLM_BASE_URL` (full chat completions endpoint), `LLM_MODEL`, `LLM_API_KEY` select the LLM. Live providers require their respective endpoint/model/key settings. `API_KEY` protects query/audit routes when set; `REVIEWER_API_KEY` separately protects review routes and also permits query/audit access. Both distinct keys are mandatory with a live provider; mock mode allows keyless queries but never keyless review. Generate independent random secrets and keep them out of source control. `AUTO_EXECUTE_THRESHOLD=0.90`, `REVIEW_THRESHOLD=0.70`, `SQL_ALLOWED_TABLES=customers`, `ALLOW_DESTRUCTIVE_SQL=false`, `QUERY_TIMEOUT_SECONDS=5`, `EXTERNAL_TIMEOUT_SECONDS=10`, `MAX_RETRIES=2`, `MAX_ROWS=100` configure policy. `API_URL` configures the Streamlit connection. Never commit `.env`.

## Example requests and decisions

```powershell
curl.exe -X POST http://localhost:8000/api/query -H "Content-Type: application/json" -d '{"user_request":"Count customers"}'
curl.exe -X POST http://localhost:8000/api/query -H "Content-Type: application/json" -d '{"user_request":"low confidence customers"}'
curl.exe http://localhost:8000/api/decisions/1
```

High-confidence mock execution returns `selected_action: execute_sql`, `confidence: 0.96`, `execution_status: success`. Low confidence proposes `execute_sql` at `0.55` but routes to `human_review` with `review_required`. `retry customers`, `clarify customers`, `review customers`, `reject customers`, `another tool please` demonstrate the other branches; `select_tool` returns an allowlisted schema inspection. See [API examples](docs/api_examples.md). The mock LLM supports customer listings, counts and revenue totals; other prompts need clarification or a different tool.

## Security and production considerations

Only one parsed SQL statement is accepted. Comments, administrative statements, writes by default, unsafe functions and access outside `SQL_ALLOWED_TABLES` are blocked. Review approval always enforces strict read-only SQL even if `ALLOW_DESTRUCTIVE_SQL=true`. That setting explicitly enables writes on the ordinary path and should **never** be used with an untrusted LLM or a privileged database role. Use a read-only database user, separate the audit write role from the query role, and enforce server-side statement and connection limits in production. A SQL parser/allowlist is defense in depth, not a full SQL sandbox. API keys provide basic access control, not per-user identity. Before production exposure add SSO, tenant scoping, rate limiting, secret rotation, database migrations and a recovery process for reviews left `processing` after a crash. SQLite progress handlers enforce local timeouts; PostgreSQL uses transaction-local `statement_timeout` through `set_config`. A bounded fetch caps returned rows but not query compute cost.

For observability, requests emit JSON log events without API keys or raw request text; audit events persist timestamp, request, SQL, Jev decision/confidence, final action, status, execution duration and errors. Protect and retain this sensitive audit table under a governed policy. Provider timeouts, HTTP failures and invalid Jev responses fail closed and are audited. Retries happen only on Jev's retry action and transient database failures; a failed query is never silently retried. Mock mode avoids per-request provider charges; live deployments can reduce costs by restricting LLM context, caching schema metadata, limiting tokens and using Jev for decision routing, then measure real latency/cost before making claims.

## Docker

The Compose stack runs API and Streamlit containers from the same non-root Python 3.12 image, plus PostgreSQL 16. The database has no host port; only the API and dashboard are published, bound to loopback by default. PostgreSQL has a persistent named volume. The API has egress for configured providers, while PostgreSQL is on an internal network. Container health checks gate startup dependencies.

```powershell
Copy-Item .env.example .env
```

Edit `.env` and fill `POSTGRES_PASSWORD`, `API_KEY`, and `REVIEWER_API_KEY` with independent random strings. Compose refuses to start while any required secret is blank. Run this command three times and use each generated value once:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build -d
docker compose --env-file .env ps
docker compose --env-file .env logs -f api ui
```

Open http://127.0.0.1:8000/docs and http://127.0.0.1:8501. Stop services without deleting database data using `docker compose --env-file .env down`. The `postgres_data` volume survives container recreation; deleting that volume permanently deletes local database contents. To bind beyond localhost, configure a TLS-terminating reverse proxy and firewall explicitly; do not expose the development HTTP ports directly to the internet.

For production, replace `.env` interpolation with the deployment platform's secret manager, TLS, identity-aware authentication, rotation, backups, migrations, resource limits and review recovery monitoring. `create_all` initializes fresh installations but does not migrate existing production schemas. See [deployment notes](docs/deployment.md). The Docker image starts Python 3.12; the local validation environment used Python 3.14 and did not build or run Docker containers.