# Kasparro Crypto ETL Backend

Production-grade FastAPI backend that ingests cryptocurrency market data from CoinGecko, CoinPaprika, and CoinCap (via CSV). The service implements **cross-source entity unification** to normalize heterogeneous payloads into a unified schema, exposes operational APIs, and keeps Postgres in sync via Alembic migrations.

## Table of Contents
- [Architecture](#architecture)
- [Cross-Source Asset Unification](#cross-source-asset-unification)
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
- [AWS Deployment](#aws-deployment)
- [EC2 Production Deployment](#ec2-production-deployment)
- [Docker Configuration](#docker-configuration)
  - [Multi-Stage Dockerfile](#multi-stage-dockerfile)
  - [Development vs Production Docker Compose](#development-vs-production-docker-compose)

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

## Cross-Source Asset Unification

The system implements **deterministic cross-source entity matching** to unify cryptocurrency data from multiple sources into canonical entities.

### Data Flow
```
STARTUP (Bootstrap):
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Fetch top 100 from CoinGecko API ─┐                                  │
│                                      ├──> Match by symbol & rank        │
│ 2. Fetch top 100 from CoinPaprika API┘         │                        │
│                                                ▼                        │
│                                    100 unified asset mappings           │
│                                    (asset_uid ↔ coingecko_id ↔          │
│                                     coinpaprika_id ↔ symbol)            │
│                                                                         │
│ 3. Generate initial CSV from CoinCap API → data/crypto_market.csv       │
└─────────────────────────────────────────────────────────────────────────┘

EVERY 20 MINUTES (CSV Update):
┌─────────────────────────────────────────────────────────────────────────┐
│ CoinCap API ──> Regenerate data/crypto_market.csv with latest prices   │
└─────────────────────────────────────────────────────────────────────────┘

EVERY 22 MINUTES (ETL Pipeline):
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Ingest from CoinGecko API                                           │
│ 2. Ingest from CoinPaprika API                                         │
│ 3. Ingest from CSV (CoinCap data)                                      │
│                    ↓                                                    │
│ 4. Normalize all data using AssetUnificationService                    │
│    • Resolve each record to canonical asset_uid                        │
│    • Preserve source-specific IDs (coingecko_id, coinpaprika_id)       │
│                    ↓                                                    │
│ 5. Upsert to unified data store (normalized_crypto_assets)             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Asset Matching Strategy
| Priority | Strategy | Example |
|----------|----------|---------|
| 1 | Source-specific ID lookup | `coingecko_id: "bitcoin"` → `asset_uid: "bitcoin"` |
| 2 | Symbol + Name matching | `BTC` + `Bitcoin` → `asset_uid: "bitcoin"` |
| 3 | Generate canonical ID | New asset → `asset_uid` from CoinGecko ID or normalized name |

Key flows:
1. **Bootstrap at startup**: `AssetUnificationService` fetches top 100 assets from CoinGecko and CoinPaprika, matches by symbol/rank, creates unified mappings.
2. **CSV generation**: Every 20 minutes, CoinCap API data is fetched and written to `data/crypto_market.csv`.
3. **ETL pipeline**: Every 22 minutes, data from all 3 sources is ingested, normalized using the asset mappings, and upserted to `NormalizedCryptoAsset`.
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
  models/            # SQLAlchemy models (raw, normalized, runs, checkpoints, asset_mapping)
  schemas/           # Pydantic response contracts
  services/          # Asset unification service, ETL service, data service
  tests/             # API + ETL unit/integration tests
alembic/             # Migration environment & versions
data/                # Auto-generated CSV from CoinCap API
Dockerfile           # Multi-stage production image definition
docker-compose.yml   # Development: API + local Postgres orchestration
docker-compose.prod.yml  # Production: API only (uses external RDS)
requirements.txt     # Locked Python dependencies
Makefile             # Quality-of-life commands
```

## Configuration
Create a `.env` (already referenced via `pydantic-settings`):
```
ENV=dev                    # "dev" or "prod" – controls docs/debug behavior
DATABASE_URL=postgresql+psycopg2://kasparro_user:kasparro_pass@localhost:5432/kasparro
LOG_LEVEL=INFO
ETL_INTERVAL_SECONDS=1320  # 22 minutes (runs after CSV update)
ETL_ENABLED=true
CSV_UPDATE_INTERVAL_SECONDS=1200  # 20 minutes (CoinCap CSV generation)
DOCS_ENABLED=                # Optional: Override docs (true/false), defaults to auto (dev=true, prod=false)
COINPAPRIKA_API_KEY=<optional>
SLACK_WEBHOOK_URL=<optional>
CGEKO_KEY=<optional>
```
Notes:
- `ENV` controls environment mode: `dev` enables Swagger/Redoc docs and debug mode; `prod` disables docs for security.
- `DOCS_ENABLED` overrides the automatic docs behavior – set to `true` to enable docs in production if needed.
- `DATABASE_URL` is overridden automatically inside Docker to target the `db` service (`postgresql+psycopg2://kasparro_user:kasparro_pass@db:5432/kasparro`).
- `ETL_INTERVAL_SECONDS` defaults to 22 minutes (1320s) to run after CSV updates complete.
- `CSV_UPDATE_INTERVAL_SECONDS` defaults to 20 minutes (1200s) for CoinCap CSV generation.
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
- **Sources**: CoinGecko (top 100 market-cap assets), CoinPaprika (full ticker set), and `data/crypto_market.csv` (auto-generated from CoinCap API every 20 minutes).
- **Cross-source unification**: `AssetUnificationService` matches assets by symbol and market cap rank, creating canonical `asset_uid` mappings at startup.
- **Incremental strategy**: each record carries `source_updated_at`; checkpoints (table `etl_checkpoints`) ensure we only ingest new data.
- **Raw storage**: payloads are saved as JSON in `raw_coingecko`, `raw_coinpaprika`, and `raw_csv` for auditability and replay.
- **Normalization**: assets are resolved to canonical `asset_uid` using the `AssetUnificationService`, with source-specific IDs (`coingecko_id`, `coinpaprika_id`) preserved for traceability.
- **Runs tracking**: `etl_runs` captures run status, counts, and errors for observability.
- **Scheduling**: 
  - CSV generation from CoinCap runs every 20 minutes
  - ETL pipeline runs every 22 minutes (after CSV is refreshed)
  - Disable by setting `ETL_ENABLED=false` or stop the background task by shutting down the API.
- **Manual triggers**: use `/etl/run/{source}`, `/etl/run-all`, or `/etl/run-background/{source}` endpoints for ad-hoc jobs.

## API Reference

**Base URL**: `http://localhost:8000`

| Endpoint | Method | Description |
| --- | --- | --- |
| `/health` | GET | Liveness probe leveraged by Docker health checks. |
| `/data` | GET | Paginated normalized assets (filters: `source`, `symbol`). |
| `/data/count` | GET | Total normalized rows (optionally per source). |
| `/data/{asset_uid}` | GET | Single normalized record by UID (canonical identifier). |
| `/data/raw/{source}` | GET | Recent raw payloads for a source with pagination. |
| `/data/raw/{source}/{record_id}` | GET | Inspect a single raw JSON payload. |
| `/etl/run/{source}` | POST | Synchronous ETL run for a specific source. |
| `/etl/run-all` | POST | Sequential ETL for every configured source. |
| `/etl/run-background/{source}` | POST | Fire-and-forget ETL (check `/stats` for completion). |
| `/stats` | GET | Recent ETL runs (status, counts, durations). |
| `/stats/checkpoints` | GET | Current incremental checkpoints per source. |
| `/stats/sources` | GET | Summary of normalized/raw counts + last run metadata. |
| `/stats/debug` | GET | Aggregated debug payload (counts + checkpoints). |

### Example Requests

```bash
# Health check
curl http://localhost:8000/health

# Get all normalized assets (paginated)
curl "http://localhost:8000/data?limit=10&offset=0"

# Get assets from a specific source
curl "http://localhost:8000/data?source=coingecko&limit=10"

# Get a specific asset by canonical ID
curl http://localhost:8000/data/bitcoin

# Get raw CoinGecko payloads
curl "http://localhost:8000/data/raw/coingecko?limit=5"

# Trigger ETL for all sources
curl -X POST http://localhost:8000/etl/run-all

# Get ETL run statistics
curl http://localhost:8000/stats

# Get current checkpoints
curl http://localhost:8000/stats/checkpoints
```

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

## AWS Deployment
For production deployment on AWS App Runner (with Lambda-based ETL scheduling), see the full guide:

📄 **[AWS Deployment Guide](docs/AWS_DEPLOYMENT.md)**

Quick overview:
- **App Runner** hosts the FastAPI container with `ENV=prod` (docs disabled, stricter logging)
- **RDS PostgreSQL** provides managed database
- **Lambda + EventBridge** triggers scheduled ETL (App Runner lacks cron)
- Deployment scripts in `scripts/` automate ECR push and Lambda setup

---

## EC2 Production Deployment

🌐 **Live Production URL**: [http://kasparro-be.harry-dev.tech](http://kasparro-be.harry-dev.tech)

This section covers deploying the application to an **AWS EC2 instance** with a **public Elastic IP address** using Docker Compose.

### Architecture Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     EC2 Instance                          │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │              Docker Engine                          │  │  │
│  │  │  ┌───────────────────────────────────────────────┐  │  │  │
│  │  │  │         kasparro-backend container            │  │  │  │
│  │  │  │  • FastAPI + Uvicorn                          │  │  │  │
│  │  │  │  • Background ETL scheduler                   │  │  │  │
│  │  │  │  • Port 8000                                  │  │  │  │
│  │  │  └───────────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │                         │                                  │  │
│  │              Elastic IP: x.x.x.x:8000                     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Amazon RDS                             │  │
│  │                PostgreSQL 16 Instance                     │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Prerequisites
- AWS EC2 instance (t2.micro or larger recommended)
- Elastic IP address allocated and associated with the EC2 instance
- Amazon RDS PostgreSQL instance (or external Postgres)
- Security groups configured:
  - EC2: Inbound port 22 (SSH), 8000 (API)
  - RDS: Inbound port 5432 from EC2 security group

### Step 1: EC2 Instance Setup

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ec2-user@<ELASTIC_IP>

# Install Docker
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for group changes
exit
```

### Step 2: Clone and Configure

```bash
# Clone the repository
git clone https://github.com/your-org/kasparro-backend.git
cd kasparro-backend

# Create production environment file
cat > .env.prod << EOF
DATABASE_URL=postgresql+psycopg2://<RDS_USER>:<RDS_PASSWORD>@<RDS_ENDPOINT>:5432/<DB_NAME>
COINPAPRIKA_API_KEY=your-api-key
ETL_ENABLED=true
ETL_INTERVAL_SECONDS=300
LOG_LEVEL=info
DOCS_ENABLED=true
EOF
```

### Step 3: Deploy with Production Docker Compose

```bash
# Build and start the production container
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Verify the container is running
docker ps

# Check logs
docker-compose -f docker-compose.prod.yml logs -f api

# Health check
curl http://localhost:8000/health
```

### Step 4: Access the Application

Once deployed, the API is accessible at:
- **API Base URL**: `http://kasparro-be.harry-dev.tech:8000`
- **Swagger Docs**: `http://kasparro-be.harry-dev.tech:8000/docs` (if `DOCS_ENABLED=true`)
- **ReDoc**: `http://kasparro-be.harry-dev.tech:8000/redoc` (if `DOCS_ENABLED=true`)
- **Health Check**: `http://kasparro-be.harry-dev.tech:8000/health`

> **Note**: Replace with your own domain or use `http://<ELASTIC_IP>:8000` if not using a custom domain.

---

## Docker Configuration

### Multi-Stage Dockerfile

The project uses a **multi-stage Dockerfile** for optimized production builds:

```
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Builder                                           │
│  ─────────────────                                          │
│  • Base: python:3.11-slim                                   │
│  • Installs build dependencies (build-essential, libpq-dev) │
│  • Creates virtual environment                              │
│  • Installs Python packages into venv                       │
│  • Image size: ~500MB (discarded after build)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: Runtime                                           │
│  ────────────────                                           │
│  • Base: python:3.11-slim                                   │
│  • Only runtime dependencies (libpq5)                       │
│  • Copies venv from builder (no build tools)                │
│  • Non-root user (appuser) for security                     │
│  • Final image size: ~180MB                                 │
└─────────────────────────────────────────────────────────────┘
```

**Benefits:**
- **Smaller image size**: ~180MB vs ~500MB+ with single-stage
- **Security**: No build tools in production, runs as non-root user
- **Faster deployments**: Smaller images = faster pulls
- **Layer caching**: Dependencies cached separately from code

### Development vs Production Docker Compose

| Feature | `docker-compose.yml` (Dev) | `docker-compose.prod.yml` (Prod) |
|---------|---------------------------|----------------------------------|
| **Database** | Local Postgres container | External RDS (DATABASE_URL required) |
| **Environment** | `ENV=dev` | `ENV=prod` |
| **Docs** | Enabled by default | Controlled via `DOCS_ENABLED` |
| **Volumes** | Bind mounts for hot reload | No volumes (immutable) |
| **Debug** | Enabled | Disabled |
| **Resource Limits** | None | CPU/Memory limits set |
| **Logging** | Default | JSON file with rotation |
| **Network** | Custom bridge network | Default bridge |

#### Development Docker Compose
```bash
# Start with local Postgres
docker-compose up -d

# Features:
# - Local Postgres container included
# - Hot reload via volume mounts
# - Swagger docs at /docs
# - Debug mode enabled
```

#### Production Docker Compose
```bash
# Requires DATABASE_URL pointing to RDS/external Postgres
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Features:
# - No database container (uses RDS)
# - Immutable container (no volumes)
# - Resource limits (512MB RAM, 1 CPU)
# - Log rotation enabled
# - Health checks configured
```

### Environment Variables (Production)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ Yes | - | PostgreSQL connection string |
| `ENV` | No | `prod` | Environment mode |
| `LOG_LEVEL` | No | `info` | Logging level |
| `DOCS_ENABLED` | No | `true` | Enable Swagger/ReDoc |
| `ETL_ENABLED` | No | `true` | Enable background ETL |
| `ETL_INTERVAL_SECONDS` | No | `1320` | ETL run interval (22 mins) |
| `CSV_UPDATE_INTERVAL_SECONDS` | No | `1200` | CSV generation interval (20 mins) |
| `COINPAPRIKA_API_KEY` | No | - | API key for CoinPaprika |

### Production Management Commands

```bash
# View running containers
docker ps

# View logs (follow mode)
docker-compose -f docker-compose.prod.yml logs -f api

# Restart the service
docker-compose -f docker-compose.prod.yml restart api

# Stop the service
docker-compose -f docker-compose.prod.yml down

# Rebuild and redeploy
docker-compose -f docker-compose.prod.yml up -d --build

# View resource usage
docker stats kasparro-backend

# Execute commands inside container
docker exec -it kasparro-backend /bin/bash
```

---

Happy building! Contributions, new sources, and observability improvements are welcome.
