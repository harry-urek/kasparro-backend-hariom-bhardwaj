"""Health routes - System health and readiness checks."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from app.api.deps import get_db
from app.models.runs import ETLRun
from app.schemas.api import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health(response: Response, db: Session = Depends(get_db)):
    """
    Health check endpoint for load balancer and Docker health checks.

    Checks database connectivity and last ETL run status.
    Returns 503 if database is unreachable.
    """
    # DB connectivity
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"down: {e}"
        response.status_code = 503

    # Last ETL run
    stmt = select(ETLRun).order_by(ETLRun.started_at.desc()).limit(1)
    last_run = db.execute(stmt).scalar_one_or_none()

    return HealthResponse(
        database=db_status,
        last_etl_status=last_run.status if last_run else None,
    )


@router.get("/ready")
def readiness(response: Response, db: Session = Depends(get_db)):
    """
    Kubernetes/ELB readiness probe - checks if service can serve traffic.

    Returns 200 if ready, 503 if database is unreachable.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        response.status_code = 503
        return {"status": "not_ready", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
