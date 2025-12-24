"""Orchestration logic for data ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from app.core.logging import get_logger
from .base import BaseSource

log = get_logger("ingestion.runner")


class IngestionRunner:
    """Runs multiple sources and returns fresh records."""

    def __init__(self, sources: List[BaseSource]):
        self.sources = sources

    async def run(self, checkpoints: Optional[Dict[str, datetime]] = None) -> Dict[str, List[dict]]:
        checkpoints = checkpoints or {}
        aggregated: Dict[str, List[dict]] = {}

        for source in self.sources:
            raw = await source.fetch()
            filtered = source.filter_incremental(raw, checkpoints.get(source.name))
            aggregated[source.name] = filtered
            log.info(f"Source={source.name} fetched={len(raw)} fresh={len(filtered)}")
        return aggregated
