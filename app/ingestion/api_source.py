"""CoinGecko source implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import get_logger
from .base import BaseSource

log = get_logger("ingestion.coingecko")


class CoinGeckoSource(BaseSource):
    """Fetches market data from CoinGecko."""

    name = "coingecko"

    async def fetch(self) -> List[Dict[str, Any]]:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: List[Dict[str, Any]] = []
        for item in data:
            ts = self._parse_timestamp(item.get("last_updated"))
            if not ts:
                continue
            results.append(
                {
                    "payload": item,
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "price_usd": item.get("current_price"),
                    "market_cap_usd": item.get("market_cap"),
                    "rank": item.get("market_cap_rank"),
                    "source_updated_at": ts,
                }
            )
        log.info(f"Fetched {len(results)} records from CoinGecko")
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
