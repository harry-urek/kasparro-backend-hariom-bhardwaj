from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
from typing import Optional

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.api.routes import data, etl, health, stats
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.services.etl_service import ETLService
from app.services.asset_service import init_asset_service, shutdown_asset_service, get_asset_service


log = get_logger("app")

# Background task handle
_etl_task: Optional[asyncio.Task] = None


def run_migrations() -> None:
    """Execute Alembic migrations programmatically on startup."""
    project_root = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    log.info("Running Alembic migrations to head")
    command.upgrade(alembic_cfg, "head")
    log.info("Alembic migrations applied")


async def run_etl_pipeline() -> None:
    """Run the full ETL pipeline for all sources."""
    log.info("Starting ETL pipeline for all sources...")
    db = SessionLocal()
    try:
        # Get the global asset service for normalization
        asset_service = get_asset_service()
        service = ETLService(db, asset_service=asset_service)
        results = await service.run_all()

        # Log results for each source
        for source, result in results.items():
            if result.get("success"):
                log.info(f"ETL {source}: processed {result.get('records_processed', 0)} records")
            else:
                log.error(f"ETL {source}: failed - {result.get('error', 'unknown error')}")

        log.info("ETL pipeline completed")
    except Exception as exc:
        log.exception(f"ETL pipeline failed: {exc}")
    finally:
        db.close()


async def scheduled_etl_task() -> None:
    """Background task that runs ETL at configured interval."""
    interval = settings.ETL_INTERVAL_SECONDS
    log.info(f"Scheduled ETL task started (interval: {interval}s)")

    # Run immediately on startup
    await run_etl_pipeline()

    # Then run at configured interval
    while True:
        try:
            await asyncio.sleep(interval)
            await run_etl_pipeline()
        except asyncio.CancelledError:
            log.info("Scheduled ETL task cancelled")
            break
        except Exception as exc:
            log.exception(f"Scheduled ETL task error: {exc}")
            # Continue running despite errors
            await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _etl_task

    # Log environment mode
    log.info(f"Starting application in {settings.ENV.upper()} mode")
    if settings.is_production:
        log.info("Production mode: Debug disabled, docs disabled, stricter logging")
    else:
        log.info("Development mode: Debug enabled, docs available")

    # Startup
    try:
        run_migrations()
    except Exception:
        log.exception("Failed to apply migrations on startup")
        raise

    # Initialize Asset Unification Service (performs bootstrap + starts CSV updater)
    log.info("Initializing Asset Unification Service...")
    db = SessionLocal()
    try:
        await init_asset_service(db)
        log.info("Asset Unification Service initialized successfully")
        log.info("  - Asset mappings bootstrapped from CoinGecko & CoinPaprika")
        log.info("  - CSV updater started (generates from CoinCap every 20 mins)")
    except Exception as exc:
        log.warning(f"Asset service initialization failed (will use fallback): {exc}")
    # Note: Don't close db - the service keeps it for resolution queries

    # Start the recurring ETL task if enabled (runs every 22 minutes)
    if settings.ETL_ENABLED:
        log.info("Starting scheduled ETL background task...")
        _etl_task = asyncio.create_task(scheduled_etl_task())
    else:
        log.info("Scheduled ETL is disabled (ETL_ENABLED=false)")

    yield

    # Shutdown
    log.info("Shutting down services...")

    # Stop ETL task
    if _etl_task:
        log.info("Cancelling scheduled ETL task...")
        _etl_task.cancel()
        try:
            await _etl_task
        except asyncio.CancelledError:
            pass

    # Shutdown asset service (stops CSV updater)
    shutdown_asset_service()

    # Close the database session
    db.close()

    log.info("Application shutdown complete")


# Configure FastAPI based on environment
app = FastAPI(
    title="Crypto ETL Backend",
    description="Production-grade ETL system for cryptocurrency market data",
    version="1.0.0",
    lifespan=lifespan,
    # Disable docs in production for security
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    # Debug mode only in development
    debug=settings.debug_enabled,
)


app.include_router(data.router)
app.include_router(etl.router)
app.include_router(health.router)
app.include_router(stats.router)
