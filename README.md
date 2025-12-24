# Kasparro Crypto ETL Backend

Production-grade FastAPI backend that ingests cryptocurrency market data from CoinGecko, CoinPaprika, and a local CSV feed. The service normalizes heterogeneous payloads into a unified schema, exposes operational APIs, and keeps Postgres in sync via Alembic migrations.

## Table of Contents
- [Architecture](#architecture)
- [Tech Stack & Tooling](#tech-stack--tooling)
- [Repository Layout](#repository-layout)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
  - [Local Python environment](#local-python-environment)
  - [Docker Compose](#docker-compose)
  - [Database migrations](#database-migrations)
- [ETL Operations](#etl-operations)
- [API Reference](#api-reference)
- [Testing & Quality](#testing--quality)
- [Troubleshooting](#troubleshooting)

## Architecture
```
┌──────────────┐        ┌────────────────────┐        ┌────────────────┐
│  Ingestion   │ async  │  ETL Orchestrator  │ writes │  Postgres 16   │
│  Sources     ├──────▶ │  (app/services)    ├──────▶ │  (raw + dims)  │
│  • CoinGecko │        │  • Checkpoints     │        │                │
│  • CoinPaprika       │  • Runs / telemetry │        │                │
│  • CSV file  │        └─────────┬──────────┘        └────────┬───────┘
└──────┬───────┘                  │                             │
       │          upserts/reads   │                             │
       │                          ▼                             ▼
       │                  ┌─────────────┐        ┌─────────────────────────┐
       └────────────────▶ │ FastAPI API │──────▶ │ Clients / Dashboards    │
                          │  (app/main) │        │ / Automation / Webhooks │
                          └─────────────┘        └─────────────────────────┘
```
Key flows:
1. `CoinGeckoSource`, `CoinPaprikaSource`, and `CSVSource` fetch raw payloads through `httpx` or filesystem.
2. `ETLService` ([app/services/etl_service.py](app/services/etl_service.py)) persists raw data, normalizes to a canonical shape, deduplicates by `asset_uid`, upserts into `NormalizedCryptoAsset`, and advances checkpoints.
3. A lifespan task ([app/main.py](app/main.py)) applies Alembic migrations at startup and schedules the recurring ETL loop (default every 5 minutes).
4. Observability endpoints under `/stats` expose run history, checkpoints, and debug summaries; `/data` serves normalized/raw records to downstream consumers.

## Tech Stack & Tooling
| Layer | Tools |
| --- | --- |
| Language & Runtime | Python 3.11 |
| Web Framework | FastAPI + Uvicorn |
| ORM & DB Schema | SQLAlchemy 2.x, Alembic migrations |
| Database | PostgreSQL 16 (Dockerized) |
| HTTP Clients | httpx (async) |
| Logging & Alerts | Loguru, optional Slack webhook integration |
| Background Scheduling | Native asyncio task in FastAPI lifespan |
| Containerization | Docker, Docker Compose |
| Testing | Pytest test suite under `app/tests` |
| Build Utilities | Makefile targets (`make up`, `make dev`, etc.) |

## Repository Layout
```
app/
  api/               # Router modules for /data, /etl, /stats, /health
  core/              # Config, logging, DB session helpers
  ingestion/         # Source adapters + runner abstraction
  models/            # SQLAlchemy models (raw, normalized, runs, checkpoints)
  schemas/           # Pydantic response contracts
  services/          # ETL + query services
  tests/             # API + ETL unit/integration tests
alembic/             # Migration environment & versions
Dockerfile           # Production image definition
docker-compose.yml   # API + Postgres orchestration
requirements.txt     # Locked Python dependencies
Makefile             # Quality-of-life commands
```

## Configuration
Create a `.env` (already referenced via `pydantic-settings`):
```
DATABASE_URL=postgresql+psycopg2://kasparro_user:kasparro_pass@localhost:5432/kasparro
LOG_LEVEL=INFO
ETL_INTERVAL_SECONDS=300
ETL_ENABLED=true
COINPAPRIKA_API_KEY=<optional>
SLACK_WEBHOOK_URL=<optional>
CGEKO_KEY=<optional>
```
Notes:
- `DATABASE_URL` is overridden automatically inside Docker to target the `db` service (`postgresql+psycopg2://kasparro_user:kasparro_pass@db:5432/kasparro`).
- Set `ETL_ENABLED=false` to skip the scheduler (manual ETL only).
- Provide `COINPAPRIKA_API_KEY` if your CoinPaprika plan requires authentication.
- `SLACK_WEBHOOK_URL` enables Loguru notifications for critical errors.

## Running the Project
### Local Python environment
1. **Prerequisites**: Python 3.11, Postgres (local or container), virtualenv recommended.
2. Install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Ensure Postgres is reachable and run Alembic migrations (see below).
4. Start the API with live reload:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Compose
```bash
# Build images
docker compose build

# Start API + Postgres
docker compose up -d

# Tail API logs
docker compose logs -f api

# Tear down
docker compose down -v
```
Bind mounts keep `app/`, `alembic/`, and `data/` in sync with the container for fast iteration. The API container waits for Postgres health before booting, applies migrations, and immediately runs the ETL pipeline.

### Make targets
```
make up          # docker compose up -d
make down        # docker compose down
make dev         # uvicorn with reload
make logs-api    # follow API logs
make health      # curl /health
```

### Database migrations
- **Automatic**: `run_migrations()` in [app/main.py](app/main.py) executes `alembic upgrade head` on every startup (both local and Docker).
- **Manual CLI** (when iterating on schema):
  ```bash
  alembic revision -m "add my table"
  alembic upgrade head
  ```
- Migration config lives in `alembic.ini` and `alembic/env.py` with the same models metadata used by the app.

## ETL Operations
- **Sources**: CoinGecko (top 100 market-cap assets), CoinPaprika (full ticker set), and `data/crypto_market.csv` (ingested only if the file exists).
- **Incremental strategy**: each record carries `source_updated_at`; checkpoints (table `etl_checkpoints`) ensure we only ingest new data.
- **Raw storage**: payloads are saved as JSON in `raw_coingecko`, `raw_coinpaprika`, and `raw_csv` for auditability and replay.
- **Normalization**: assets collapse to a canonical shape (UID = lowercase symbol) with safe casting and deduplication to prevent multi-write conflicts.
- **Runs tracking**: `etl_runs` captures run status, counts, and errors for observability.
- **Scheduling**: `scheduled_etl_task()` starts immediately then sleeps for `ETL_INTERVAL_SECONDS`. Disable by setting `ETL_ENABLED=false` or stop the background task by shutting down the API.
- **Manual triggers**: use `/etl/run/{source}`, `/etl/run-all`, or `/etl/run-background/{source}` endpoints for ad-hoc jobs.

## API Reference
| Endpoint | Method | Description |
| --- | --- | --- |
| `/health` | GET | Liveness probe leveraged by Docker health checks. |
| `/data` | GET | Paginated normalized assets (filters: `source`, `symbol`). |
| `/data/count` | GET | Total normalized rows (optionally per source). |
| `/data/{asset_uid}` | GET | Single normalized record by UID (lowercase symbol). |
| `/data/raw/{source}` | GET | Recent raw payloads for a source with pagination. |
| `/data/raw/{source}/{record_id}` | GET | Inspect a single raw JSON payload. |
| `/etl/run/{source}` | POST | Synchronous ETL run for a specific source. |
| `/etl/run-all` | POST | Sequential ETL for every configured source. |
| `/etl/run-background/{source}` | POST | Fire-and-forget ETL (check `/stats` for completion). |
| `/stats` | GET | Recent ETL runs (status, counts, durations). |
| `/stats/checkpoints` | GET | Current incremental checkpoints per source. |
| `/stats/sources` | GET | Summary of normalized/raw counts + last run metadata. |
| `/stats/debug` | GET | Aggregated debug payload (counts + checkpoints). |

Swagger UI is available at `http://localhost:8000/docs` (Redoc at `/redoc`).

## Testing & Quality
- Tests live under `app/tests`. Run them (after installing dev deps) with:
  ```bash
  pytest app/tests -v
  ```
- Linting/formatting placeholders exist in the `Makefile`; integrate Ruff, Black, or preferred tools and update the targets when ready.
- CI/CD can reuse `docker compose` or `pytest` commands for validation.

## Troubleshooting
- **`psycopg2` build errors**: ensure Docker image has `build-essential` and `libpq-dev` (already handled in the `Dockerfile`).
- **Migrations missing**: confirm Alembic files are mounted/copied (`docker-compose.yml` volume mounts them into `/app`).
- **ETL duplicates**: deduplication in `ETLService._normalize()` guarantees one `asset_uid` per insert; if you still see conflicts, clear checkpoints for the affected source.
- **External API rate limits**: CoinPaprika can require an API key for sustained traffic; configure `COINPAPRIKA_API_KEY` when necessary.
- **Background ETL stuck**: check `/stats` and container logs. You can disable the scheduler, run `/etl/run-all`, then re-enable once healthy.

Happy building! Contributions, new sources, and observability improvements are welcome.
