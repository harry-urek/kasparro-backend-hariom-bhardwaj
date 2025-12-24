"""ETL routes - Trigger and manage ETL jobs."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.logging import get_logger
from app.schemas.api import ETLTriggerResponse
from app.services.etl_service import ETLService

router = APIRouter(prefix="/etl", tags=["etl"])
log = get_logger("etl_routes")


@router.post("/run/{source}", response_model=ETLTriggerResponse)
async def trigger_etl(
    source: Literal["coingecko", "coinpaprika", "csv"],
    db: Session = Depends(get_db),
):
    """
    Trigger ETL job for a specific source.

    This runs the full ETL pipeline:
    1. Fetch data from source
    2. Store raw payloads
    3. Normalize and validate
    4. Upsert to normalized table
    5. Update checkpoint

    Sources:
    - coingecko: CoinGecko API (no key required)
    - coinpaprika: CoinPaprika API (optional key)
    - csv: Local CSV file
    """
    log.info(f"ETL triggered for source: {source}")

    try:
        service = ETLService(db)
        result = await service.run(source)  # type: ignore[arg-type]

        return ETLTriggerResponse(
            success=result["success"],
            source=source,
            records_processed=result.get("records_processed", 0),
        )
    except Exception as exc:
        log.error(f"ETL failed for {source}: {exc}")
        return ETLTriggerResponse(
            success=False,
            source=source,
            records_processed=0,
            error=str(exc),
        )


@router.post("/run-all")
async def trigger_etl_all(db: Session = Depends(get_db)):
    """
    Trigger ETL for all configured sources.

    Runs coingecko, coinpaprika, and csv (if file exists) sequentially.
    Returns results for each source.
    """
    log.info("ETL triggered for all sources")

    service = ETLService(db)
    results = await service.run_all()

    return {
        "success": all(r.get("success", False) for r in results.values()),
        "results": results,
    }


@router.post("/run-background/{source}")
async def trigger_etl_background(
    source: Literal["coingecko", "coinpaprika", "csv"],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger ETL job in background (non-blocking).

    Returns immediately while ETL runs in background.
    Check /stats for job completion status.
    """
    import asyncio

    async def run_etl():
        # Need a new session for background task
        from app.core.db import SessionLocal

        with SessionLocal() as session:
            try:
                service = ETLService(session)
                await service.run(source)  # type: ignore[arg-type]
                log.info(f"Background ETL completed for {source}")
            except Exception as exc:
                log.error(f"Background ETL failed for {source}: {exc}")

    # Schedule as background task
    background_tasks.add_task(asyncio.get_event_loop().run_until_complete, run_etl())

    return {
        "message": f"ETL job for {source} started in background",
        "source": source,
        "status": "queued",
    }
