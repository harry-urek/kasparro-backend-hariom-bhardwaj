from pathlib import Path
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.api.routes import data, health, stats
from app.core.config import settings
from app.core.logging import get_logger


log = get_logger("app")


def run_migrations() -> None:
    """Execute Alembic migrations programmatically on startup."""
    project_root = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    log.info("Running Alembic migrations to head")
    command.upgrade(alembic_cfg, "head")
    log.info("Alembic migrations applied")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        run_migrations()
    except Exception:
        log.exception("Failed to apply migrations on startup")
        raise
    yield
    log.info("Application shutdown complete")


app = FastAPI(title="Crypto ETL Backend", lifespan=lifespan)


app.include_router(data.router)
app.include_router(health.router)
app.include_router(stats.router)
