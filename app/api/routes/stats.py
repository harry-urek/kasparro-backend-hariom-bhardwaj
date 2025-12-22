from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db
from app.models.runs import ETLRun
from app.schemas.api import StatsResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=list[StatsResponse])
def stats(db: Session = Depends(get_db)):
    stmt = select(ETLRun).order_by(ETLRun.started_at.desc()).limit(10)

    runs = db.execute(stmt).scalars().all()

    return runs
