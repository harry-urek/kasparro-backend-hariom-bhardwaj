"""ETL entrypoint - Standalone script for running ETL jobs"""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.etl_service import ETLService
from app.core.logging import get_logger
from app.core.config import settings
from app.core.checkpoints import CheckpointManager

logger = get_logger("etl_entrypoint")


async def run_etl_job(source_type: str):
    """Run ETL job for specified source"""
    logger.info(f"Starting ETL job for source: {source_type}")

    try:
        etl_service = ETLService()
        checkpoint_manager = CheckpointManager()

        # Get last checkpoint
        last_checkpoint = checkpoint_manager.load_checkpoint(source_type)
        logger.info(f"Last checkpoint: {last_checkpoint}")

        # Run ETL
        result = await etl_service.run_etl(source_type)

        # Save checkpoint
        checkpoint_manager.save_checkpoint(source_type, {"records_processed": result["records_processed"], "success": result["success"]})

        logger.info(f"ETL job completed: {result}")
        return result

    except Exception as e:
        logger.error(f"ETL job failed: {str(e)}", exc_info=True)
        raise


async def run_all_sources():
    """Run ETL for all configured sources"""
    sources = ["api", "csv", "third_party"]
    results = {}

    for source in sources:
        try:
            result = await run_etl_job(source)
            results[source] = result
        except Exception as e:
            logger.error(f"Failed to process source {source}: {str(e)}")
            results[source] = {"success": False, "error": str(e)}

    return results


def main():
    """Main entrypoint"""
    logger.info("ETL Pipeline starting...")

    # Check if specific source is provided
    if len(sys.argv) > 1:
        source_type = sys.argv[1]
        logger.info(f"Running ETL for single source: {source_type}")
        result = asyncio.run(run_etl_job(source_type))
    else:
        logger.info("Running ETL for all sources")
        result = asyncio.run(run_all_sources())

    logger.info(f"ETL Pipeline completed: {result}")
    return result


if __name__ == "__main__":
    main()
