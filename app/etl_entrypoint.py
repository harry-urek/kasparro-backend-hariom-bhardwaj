"""ETL entrypoint - Standalone script for running ETL jobs.

Usage:
    python -m app.etl_entrypoint                    # Run all sources
    python -m app.etl_entrypoint coingecko          # Run single source
    python -m app.etl_entrypoint coinpaprika        # Run single source
    python -m app.etl_entrypoint csv                # Run CSV source
"""

import asyncio
import sys
from typing import Literal

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.services.etl_service import ETLService, SourceName

logger = get_logger("etl_entrypoint")


async def run_etl_job(source: SourceName):
    """Run ETL for a single source."""
    logger.info(f"Starting ETL job for source: {source}")
    with SessionLocal() as db:
        service = ETLService(db)
        result = await service.run(source)
        logger.info(f"ETL job completed for {source}: {result}")
        return result


async def run_all_sources():
    """Run ETL for all sources."""
    logger.info("Running ETL for all sources")
    with SessionLocal() as db:
        service = ETLService(db)
        results = await service.run_all()
        logger.info(f"ETL completed for all sources: {results}")
        return results


def main():
    """Main entry point for ETL pipeline."""
    logger.info("ETL Pipeline starting...")

    if len(sys.argv) > 1:
        source = sys.argv[1]
        if source not in ("coingecko", "coinpaprika", "csv"):
            logger.error(f"Invalid source: {source}. Must be one of: coingecko, coinpaprika, csv")
            sys.exit(1)
        result = asyncio.run(run_etl_job(source))  # type: ignore[arg-type]
    else:
        result = asyncio.run(run_all_sources())

    logger.info(f"ETL Pipeline completed: {result}")

    # Exit with error code if any source failed
    if isinstance(result, dict):
        if any(not r.get("success", False) for r in result.values() if isinstance(r, dict)):
            sys.exit(1)
        elif not result.get("success", True):
            sys.exit(1)

    return result


if __name__ == "__main__":
    main()
