"""Stats routes - ETL observability and system monitoring."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.api import CheckpointOut, DebugResponse, StatsResponse
from app.services.data_service import DataService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=list[StatsResponse])
def get_etl_stats(
    source: Optional[str] = Query(None, description="Filter by source name"),
    status: Optional[str] = Query(None, description="Filter by status (running, success, failure)"),
    limit: int = Query(10, ge=1, le=50, description="Number of runs to return"),
    db: Session = Depends(get_db),
):
    """
    Get recent ETL run statistics.

    Shows records processed, duration, status, and error messages.
    Use this for monitoring ETL health and debugging failures.
    """
    service = DataService(db)
    runs = service.get_etl_runs(source=source, status=status, limit=limit)

    return [
        StatsResponse(
            run_id=str(run.run_id),
            source_name=run.source_name,
            status=run.status,
            records_processed=run.records_processed,
            error_message=run.error_message,
            started_at=run.started_at,
            ended_at=run.ended_at,
        )
        for run in runs
    ]


@router.get("/checkpoints", response_model=list[CheckpointOut])
def get_checkpoints(db: Session = Depends(get_db)):
    """
    Get all ETL checkpoints.

    Checkpoints track the last processed timestamp for each source,
    enabling incremental ingestion.
    """
    service = DataService(db)
    checkpoints = service.get_checkpoints()

    return [
        CheckpointOut(
            source_name=cp.source_name,
            last_updated_at=cp.last_updated_at,
            updated_at=cp.updated_at,
        )
        for cp in checkpoints
    ]


@router.get("/sources")
def get_sources_summary(db: Session = Depends(get_db)):
    """
    Get summary statistics for each data source.

    Includes record counts, last checkpoint, and last run status.
    """
    service = DataService(db)
    return service.get_sources_summary()


@router.get("/debug", response_model=DebugResponse)
def get_debug_info(db: Session = Depends(get_db)):
    """
    Get comprehensive debug information about system state.

    Includes all checkpoints and record counts for debugging.
    """
    service = DataService(db)
    info = service.get_debug_info()

    return DebugResponse(
        checkpoints=[
            CheckpointOut(
                source_name=cp.source_name,
                last_updated_at=cp.last_updated_at,
                updated_at=cp.updated_at,
            )
            for cp in info["checkpoints"]
        ],
        etl_runs_count=info["etl_runs_count"],
        normalized_count=info["normalized_count"],
        raw_coingecko_count=info["raw_coingecko_count"],
        raw_coinpaprika_count=info["raw_coinpaprika_count"],
        raw_csv_count=info["raw_csv_count"],
    )
