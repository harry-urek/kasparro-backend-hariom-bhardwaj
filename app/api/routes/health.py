from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from app.api.deps import get_db
from app.models.runs import ETLRun
from app.schemas.api import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    # DB connectivity
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"down: {e}"

    # Last ETL run
    stmt = select(ETLRun).order_by(ETLRun.started_at.desc()).limit(1)
    last_run = db.execute(stmt).scalar_one_or_none()

    return {
        "database": db_status,
        "last_etl_status": last_run.status if last_run else None,
    }
