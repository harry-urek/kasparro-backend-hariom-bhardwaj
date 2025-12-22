"""Orchestration logic for data ingestion"""

from typing import List
from .base import BaseSource


class IngestionRunner:
    """Orchestrates data ingestion from multiple sources"""

    def __init__(self, sources: List[BaseSource]):
        self.sources = sources

    async def run(self):
        """Run ingestion for all sources"""
        results = []
        for source in self.sources:
            data = await source.fetch()
            if await source.validate(data):
                results.extend(data)
        return results
