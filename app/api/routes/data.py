import time
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db
from app.models.normalized import NormalizedCryptoAsset
from app.schemas.api import DataResponse

router = APIRouter(prefix="/data", tags=["data"])


@router.get("", response_model=DataResponse)
def get_data(
    source: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    stmt = select(NormalizedCryptoAsset)

    if source:
        stmt = stmt.where(NormalizedCryptoAsset.source == source)

    stmt = stmt.limit(limit).offset(offset)
    results = db.execute(stmt).scalars().all()

    latency_ms = int((time.perf_counter() - start) * 1000)

    return {
        "request_id": request_id,
        "api_latency_ms": latency_ms,
        "data": results,
    }
