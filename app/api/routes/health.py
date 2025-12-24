"""Health routes - System health and readiness checks."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from app.api.deps import get_db
from app.models.runs import ETLRun
from app.schemas.api import HealthResponse
from app.services.data_service import DataService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    """
    Health check endpoint.

    Checks:
    - Database connectivity
    - Last ETL run status

    Use this for load balancer health checks and monitoring.
    """
    # DB connectivity
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"down: {e}"

    # Last ETL run
    stmt = select(ETLRun).order_by(ETLRun.started_at.desc()).limit(1)
    last_run = db.execute(stmt).scalar_one_or_none()

    return HealthResponse(
        database=db_status,
        last_etl_status=last_run.status if last_run else None,
    )


@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """
    Readiness probe - checks if the service is ready to serve traffic.

    Returns 200 if ready, 503 if not.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}


@router.get("/live")
def liveness():
    """
    Liveness probe - checks if the service is alive.

    Always returns 200 if the service can respond.
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/detailed")
def detailed_health(db: Session = Depends(get_db)):
    """
    Detailed health check with comprehensive system information.

    Use for debugging and monitoring dashboards.
    """
    service = DataService(db)

    # DB connectivity
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
        db_latency_ms = None
        import time

        start = time.perf_counter()
        db.execute(text("SELECT 1"))
        db_latency_ms = int((time.perf_counter() - start) * 1000)
    except Exception as e:
        db_status = f"down: {e}"
        db_latency_ms = None

    # Get latest runs per source
    latest_runs = {}
    for source in ["coingecko", "coinpaprika", "csv"]:
        run = service.get_latest_etl_run(source)
        if run:
            latest_runs[source] = {
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "records_processed": run.records_processed,
            }

    # Get counts
    debug_info = service.get_debug_info()

    return {
        "status": "healthy" if db_status == "ok" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": db_status,
            "latency_ms": db_latency_ms,
        },
        "etl": {
            "total_runs": debug_info["etl_runs_count"],
            "latest_runs": latest_runs,
        },
        "data": {
            "normalized_records": debug_info["normalized_count"],
            "raw_coingecko": debug_info["raw_coingecko_count"],
            "raw_coinpaprika": debug_info["raw_coinpaprika_count"],
            "raw_csv": debug_info["raw_csv_count"],
        },
    }
