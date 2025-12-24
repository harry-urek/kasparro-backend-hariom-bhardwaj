"""Abstract source interface for ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class BaseSource(ABC):
    """Abstract base class for data sources."""

    name: str

    @abstractmethod
    async def fetch(self) -> List[Dict[str, Any]]:
        """Fetch raw records (must include payload and source_updated_at)."""

    @staticmethod
    def filter_incremental(records: List[Dict[str, Any]], checkpoint: Optional[datetime]) -> List[Dict[str, Any]]:
        if not checkpoint:
            return records
        return [rec for rec in records if rec.get("source_updated_at") and rec["source_updated_at"] > checkpoint]
