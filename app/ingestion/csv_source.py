"""CSV source implementation (optional/local ingestion)."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from .base import BaseSource

log = get_logger("ingestion.csv")


class CSVSource(BaseSource):
    """Reads a CSV with required columns: symbol,name,price_usd,market_cap_usd,rank,source_updated_at."""

    name = "csv"

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    async def fetch(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            log.warning(f"CSV file not found: {self.file_path}")
            return []

        records: List[Dict[str, Any]] = []
        with self.file_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = self._parse_timestamp(row.get("source_updated_at"))
                if not ts:
                    continue
                records.append(
                    {
                        "payload": row,
                        "symbol": row.get("symbol"),
                        "name": row.get("name"),
                        "price_usd": self._to_float(row.get("price_usd")),
                        "market_cap_usd": self._to_float(row.get("market_cap_usd")),
                        "rank": self._to_int(row.get("rank")),
                        "source_updated_at": ts,
                    }
                )
        log.info(f"Loaded {len(records)} records from CSV")
        return records

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value)).astimezone(timezone.utc)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _to_float(val: Any) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _to_int(val: Any) -> Optional[int]:
        try:
            return int(val) if val not in (None, "") else None
        except Exception:  # noqa: BLE001
            return None
