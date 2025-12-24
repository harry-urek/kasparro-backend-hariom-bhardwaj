"""CoinPaprika source implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from .base import BaseSource

log = get_logger("ingestion.coinpaprika")


class CoinPaprikaSource(BaseSource):
    """Fetches market data from CoinPaprika."""

    name = "coinpaprika"

    async def fetch(self) -> List[Dict[str, Any]]:
        url = "https://api.coinpaprika.com/v1/tickers"
        params: Dict[str, Any] = {}
        if settings.COINPAPRIKA_API_KEY:
            params["api_key"] = settings.COINPAPRIKA_API_KEY

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: List[Dict[str, Any]] = []
        for item in data:
            usd = item.get("quotes", {}).get("USD", {})
            ts = self._parse_timestamp(item.get("last_updated"))
            if not ts:
                continue
            results.append(
                {
                    "payload": item,
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "price_usd": usd.get("price"),
                    "market_cap_usd": usd.get("market_cap"),
                    "rank": item.get("rank"),
                    "source_updated_at": ts,
                }
            )
        log.info(f"Fetched {len(results)} records from CoinPaprika")
        return results

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            if isinstance(value, str):
                value = value.replace("Z", "+00:00")
                return datetime.fromisoformat(value).astimezone(timezone.utc)
            if isinstance(value, datetime):
                return value.astimezone(timezone.utc)
        except Exception:  # noqa: BLE001
            return None
        return None
