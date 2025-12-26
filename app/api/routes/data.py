"""Data routes - Exposes normalized and raw data with proper request metadata."""

import time
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.api import (
    CryptoAssetOut,
    DataResponse,
    RawDataResponse,
    RawRecordOut,
)
from app.services.data_service import DataService

router = APIRouter(prefix="/data", tags=["data"])


# -----------------------------------------------------------------------------
# Normalized Data Endpoints
# -----------------------------------------------------------------------------


@router.get("", response_model=DataResponse)
def get_normalized_data(
    source: Optional[Literal["coingecko", "coinpaprika", "csv"]] = Query(None, description="Filter by source (coingecko, coinpaprika, csv)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol (case-insensitive partial match)"),
    name: Optional[str] = Query(None, description="Filter by name (case-insensitive partial match)"),
    min_rank: Optional[int] = Query(None, ge=1, description="Filter assets with rank >= min_rank"),
    max_rank: Optional[int] = Query(None, ge=1, description="Filter assets with rank <= max_rank"),
    sort_by: Literal["rank", "price_usd", "market_cap_usd", "symbol", "name"] = Query("rank", description="Sort by field"),
    sort_order: Literal["asc", "desc"] = Query("asc", description="Sort order"),
    limit: int = Query(50, ge=1, le=500, description="Number of records to return (max 500)"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db),
):
    """
    Get normalized cryptocurrency data with advanced filtering and sorting.

    Returns unified schema across all sources with:
    - Pagination (limit/offset)
    - Filtering by source, symbol, name, and rank range
    - Sorting by rank, price, market cap, symbol, or name
    - Cross-source IDs (coingecko_id, coinpaprika_id) for traceability

    Includes request metadata (request_id, latency_ms).
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    service = DataService(db)
    results = service.get_normalized_data(
        source=source,
        symbol=symbol,
        name=name,
        min_rank=min_rank,
        max_rank=max_rank,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )

    latency_ms = int((time.perf_counter() - start) * 1000)

    return DataResponse(
        request_id=request_id,
        api_latency_ms=latency_ms,
        data=[CryptoAssetOut.model_validate(r) for r in results],
    )


@router.get("/count")
def get_normalized_count(
    source: Optional[str] = Query(None, description="Filter by source"),
    db: Session = Depends(get_db),
):
    """Get total count of normalized records."""
    service = DataService(db)
    count = service.get_normalized_count(source=source)
    return {"count": count, "source": source}


@router.get("/{asset_uid}", response_model=CryptoAssetOut)
def get_normalized_by_uid(
    asset_uid: str,
    db: Session = Depends(get_db),
):
    """Get a single normalized asset by its unique ID (lowercase symbol)."""
    service = DataService(db)
    result = service.get_normalized_by_uid(asset_uid.lower())

    if not result:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_uid}' not found")

    return CryptoAssetOut.model_validate(result)


# -----------------------------------------------------------------------------
# Raw Data Endpoints
# -----------------------------------------------------------------------------


@router.get("/raw/{source}", response_model=RawDataResponse)
def get_raw_data(
    source: Literal["coingecko", "coinpaprika", "csv"],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get raw data for a specific source.

    Raw data is stored as-is from the source for auditability and replay.
    """
    request_id = str(uuid.uuid4())
    service = DataService(db)

    results = service.get_raw_data(source=source, limit=limit, offset=offset)
    total_count = service.get_raw_count(source=source)

    return RawDataResponse(
        request_id=request_id,
        source=source,
        total_count=total_count,
        data=[
            RawRecordOut(
                id=str(r.id),
                payload=r.payload,
                source_updated_at=r.source_updated_at,
                ingested_at=r.ingested_at,
            )
            for r in results
        ],
    )


@router.get("/raw/{source}/{record_id}")
def get_raw_by_id(
    source: Literal["coingecko", "coinpaprika", "csv"],
    record_id: str,
    db: Session = Depends(get_db),
):
    """Get a single raw record by ID."""
    service = DataService(db)
    result = service.get_raw_by_id(source=source, record_id=record_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Raw record '{record_id}' not found in {source}")

    return {
        "id": str(result.id),
        "payload": result.payload,
        "source_updated_at": result.source_updated_at,
        "ingested_at": result.ingested_at,
    }
