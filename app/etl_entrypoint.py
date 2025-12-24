"""ETL entrypoint - Standalone script for running ETL jobs."""

import asyncio

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.services.etl_service import ETLService

logger = get_logger("etl_entrypoint")


async def run_etl_job(source: str):
    logger.info(f"Starting ETL job for source: {source}")
    with SessionLocal() as db:
        service = ETLService(db)
        return await service.run(source)  # type: ignore[arg-type]


async def run_all_sources():
    sources = ["coingecko", "coinpaprika"]
    results = {}
    for source in sources:
        try:
            results[source] = await run_etl_job(source)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to process source {source}: {exc}")
            results[source] = {"success": False, "error": str(exc)}
    return results


def main():
    logger.info("ETL Pipeline starting...")
    import sys

    if len(sys.argv) > 1:
        source = sys.argv[1]
        result = asyncio.run(run_etl_job(source))
    else:
        result = asyncio.run(run_all_sources())
    logger.info(f"ETL Pipeline completed: {result}")
    return result


if __name__ == "__main__":
    main()
