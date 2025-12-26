"""Unified Asset Service for cross-source entity management.

This module combines asset mapping bootstrap, resolution, and CSV generation
into a single cohesive service that:
1. At startup: Fetches top 100 assets from CoinGecko & CoinPaprika, matches by symbol/rank
2. Every 20 mins: Fetches data from CoinCap API and generates CSV in data folder
3. During ETL: Provides normalization to unify all sources into canonical entities
"""

from __future__ import annotations

import asyncio
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.asset_mapping import AssetMapping, WELL_KNOWN_ASSETS

log = get_logger("asset_service")

# Configuration
TOP_ASSETS_COUNT = 100
CSV_OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "crypto_market.csv"


class AssetUnificationService:
    """Unified service for cross-source asset management.
    
    This service handles:
    1. Bootstrap: Discover and map assets from CoinGecko and CoinPaprika
    2. CSV Generation: Fetch from CoinCap API and create CSV every 20 mins
    3. Resolution: Resolve any asset to its canonical unified identifier
    
    Usage:
        # Initialize at startup (performs bootstrap)
        service = await AssetUnificationService.create(db)
        
        # Start background CSV updates
        service.start_csv_updater()
        
        # Resolve assets during normalization
        asset_uid, cg_id, cp_id = service.resolve("coingecko", "BTC", "Bitcoin", payload)
    """

    def __init__(self, db: Session):
        self.db = db
        self._cache: Dict[str, str] = {}  # source_key -> asset_uid
        self._csv_task: Optional[asyncio.Task] = None
        self._initialized = False

    @classmethod
    async def create(cls, db: Session) -> "AssetUnificationService":
        """Factory method to create and initialize the service.
        
        Performs the full bootstrap process:
        1. Fetches top 100 from CoinGecko and CoinPaprika
        2. Matches by symbol and validates by rank
        3. Creates unified asset mappings
        """
        service = cls(db)
        await service._bootstrap()
        service._initialized = True
        return service

    # =========================================================================
    # BOOTSTRAP - Runs at startup
    # =========================================================================
    async def _bootstrap(self) -> Dict[str, Any]:
        """Execute the bootstrap process to build asset mappings."""
        log.info("=" * 60)
        log.info("ASSET UNIFICATION SERVICE - BOOTSTRAP")
        log.info("=" * 60)
        
        start_time = datetime.now(timezone.utc)

        try:
            # Fetch data from both APIs in parallel
            log.info(f"Fetching top {TOP_ASSETS_COUNT} assets from CoinGecko and CoinPaprika...")
            
            coingecko_data, coinpaprika_data = await asyncio.gather(
                self._fetch_coingecko(),
                self._fetch_coinpaprika(),
                return_exceptions=True,
            )

            # Handle fetch errors
            if isinstance(coingecko_data, Exception):
                log.error(f"CoinGecko fetch failed: {coingecko_data}")
                coingecko_data = []
            if isinstance(coinpaprika_data, Exception):
                log.error(f"CoinPaprika fetch failed: {coinpaprika_data}")
                coinpaprika_data = []

            if not coingecko_data or not coinpaprika_data:
                log.warning("API fetch failed, seeding fallback mappings...")
                self._seed_fallback_mappings()
                return {"success": False, "error": "API fetch failed", "mappings_created": len(WELL_KNOWN_ASSETS)}

            log.info(f"✓ CoinGecko: {len(coingecko_data)} assets fetched")
            log.info(f"✓ CoinPaprika: {len(coinpaprika_data)} assets fetched")

            # Build symbol lookup tables
            cg_by_symbol = self._build_symbol_lookup(coingecko_data, "coingecko")
            cp_by_symbol = self._build_symbol_lookup(coinpaprika_data, "coinpaprika")

            # Match assets
            matches = self._match_assets(cg_by_symbol, cp_by_symbol)
            log.info(f"✓ Matched {len(matches)} assets across both sources")

            # Persist mappings
            created_count = self._persist_mappings(matches)

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

            log.info("=" * 60)
            log.info("BOOTSTRAP COMPLETE")
            log.info(f"  Total mappings: {created_count}")
            log.info(f"  Time elapsed: {elapsed:.2f}s")
            log.info("=" * 60)

            # Generate initial CSV
            log.info("Generating initial CSV from CoinCap API...")
            await self._generate_csv()

            return {"success": True, "mappings_created": created_count}

        except Exception as exc:
            log.exception(f"Bootstrap failed: {exc}")
            self._seed_fallback_mappings()
            return {"success": False, "error": str(exc)}

    async def _fetch_coingecko(self) -> List[Dict[str, Any]]:
        """Fetch top assets from CoinGecko API."""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": TOP_ASSETS_COUNT,
            "page": 1,
            "sparkline": "false",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        return [
            {
                "id": item.get("id"),
                "symbol": (item.get("symbol") or "").upper(),
                "name": item.get("name"),
                "market_cap": item.get("market_cap") or 0,
                "rank": item.get("market_cap_rank"),
            }
            for item in data
        ]

    async def _fetch_coinpaprika(self) -> List[Dict[str, Any]]:
        """Fetch top assets from CoinPaprika API."""
        url = "https://api.coinpaprika.com/v1/tickers"
        params: Dict[str, Any] = {}
        if settings.COINPAPRIKA_API_KEY:
            params["api_key"] = settings.COINPAPRIKA_API_KEY

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        # Sort by rank and take top N
        sorted_data = sorted(data, key=lambda x: x.get("rank") or 9999)[:TOP_ASSETS_COUNT]

        return [
            {
                "id": item.get("id"),
                "symbol": (item.get("symbol") or "").upper(),
                "name": item.get("name"),
                "market_cap": item.get("quotes", {}).get("USD", {}).get("market_cap") or 0,
                "rank": item.get("rank"),
            }
            for item in sorted_data
        ]

    def _build_symbol_lookup(self, data: List[Dict[str, Any]], source: str) -> Dict[str, Dict[str, Any]]:
        """Build a symbol -> asset data lookup table."""
        lookup: Dict[str, Dict[str, Any]] = {}
        for item in data:
            symbol = item.get("symbol", "").upper()
            if symbol and symbol not in lookup:
                lookup[symbol] = item
            elif symbol in lookup:
                if (item.get("market_cap") or 0) > (lookup[symbol].get("market_cap") or 0):
                    lookup[symbol] = item
        return lookup

    def _match_assets(
        self,
        cg_by_symbol: Dict[str, Dict[str, Any]],
        cp_by_symbol: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Match assets from both sources using symbol and rank validation."""
        matches: List[Dict[str, Any]] = []
        matched_symbols: set = set()

        log.info("-" * 50)
        log.info("MATCHING ASSETS BY SYMBOL AND RANK")
        log.info("-" * 50)

        # Direct symbol matching
        for symbol, cg_asset in cg_by_symbol.items():
            if symbol in cp_by_symbol:
                cp_asset = cp_by_symbol[symbol]
                
                cg_rank = cg_asset.get("rank") or 999
                cp_rank = cp_asset.get("rank") or 999
                rank_diff = abs(cg_rank - cp_rank)

                match = {
                    "asset_uid": cg_asset["id"],
                    "coingecko_id": cg_asset["id"],
                    "coinpaprika_id": cp_asset["id"],
                    "symbol": symbol,
                    "name": cg_asset.get("name") or cp_asset.get("name") or symbol,
                }
                matches.append(match)
                matched_symbols.add(symbol)

                if rank_diff <= 10:
                    log.debug(f"  ✓ {symbol}: CG[{cg_asset['id']}] ↔ CP[{cp_asset['id']}] (rank diff: {rank_diff})")
                else:
                    log.warning(f"  ⚠ {symbol}: Large rank diff ({rank_diff}) - CG:{cg_rank} vs CP:{cp_rank}")

        # Add unmatched CoinGecko assets
        for symbol in set(cg_by_symbol.keys()) - matched_symbols:
            cg_asset = cg_by_symbol[symbol]
            matches.append({
                "asset_uid": cg_asset["id"],
                "coingecko_id": cg_asset["id"],
                "coinpaprika_id": None,
                "symbol": symbol,
                "name": cg_asset.get("name") or symbol,
            })

        # Add unmatched CoinPaprika assets
        for symbol in set(cp_by_symbol.keys()) - matched_symbols:
            cp_asset = cp_by_symbol[symbol]
            matches.append({
                "asset_uid": cp_asset["id"],
                "coingecko_id": None,
                "coinpaprika_id": cp_asset["id"],
                "symbol": symbol,
                "name": cp_asset.get("name") or symbol,
            })

        # Log statistics
        full_matches = sum(1 for m in matches if m.get("coingecko_id") and m.get("coinpaprika_id"))
        log.info("-" * 50)
        log.info("MATCH RESULTS:")
        log.info(f"  Full matches (both APIs): {full_matches}")
        log.info(f"  CoinGecko only: {sum(1 for m in matches if m.get('coingecko_id') and not m.get('coinpaprika_id'))}")
        log.info(f"  CoinPaprika only: {sum(1 for m in matches if not m.get('coingecko_id') and m.get('coinpaprika_id'))}")
        log.info(f"  Total mappings: {len(matches)}")
        log.info("-" * 50)

        return matches

    def _persist_mappings(self, matches: List[Dict[str, Any]]) -> int:
        """Persist asset mappings to the database."""
        if not matches:
            return 0

        values = [
            {
                "asset_uid": m["asset_uid"],
                "coingecko_id": m.get("coingecko_id"),
                "coinpaprika_id": m.get("coinpaprika_id"),
                "symbol": m["symbol"],
                "name": m["name"],
            }
            for m in matches
        ]

        stmt = insert(AssetMapping).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AssetMapping.asset_uid],
            set_={
                "coingecko_id": stmt.excluded.coingecko_id,
                "coinpaprika_id": stmt.excluded.coinpaprika_id,
                "symbol": stmt.excluded.symbol,
                "name": stmt.excluded.name,
            },
        )
        
        self.db.execute(stmt)
        self.db.commit()
        return len(values)

    def _seed_fallback_mappings(self) -> None:
        """Seed fallback mappings if bootstrap fails."""
        if not WELL_KNOWN_ASSETS:
            return
        log.info(f"Seeding {len(WELL_KNOWN_ASSETS)} fallback asset mappings")
        stmt = insert(AssetMapping).values(WELL_KNOWN_ASSETS)
        stmt = stmt.on_conflict_do_nothing(index_elements=[AssetMapping.asset_uid])
        self.db.execute(stmt)
        self.db.commit()

    # =========================================================================
    # CSV GENERATION - Runs every 20 minutes
    # =========================================================================
    def start_csv_updater(self) -> None:
        """Start the background task that updates CSV every 20 minutes."""
        if self._csv_task is not None:
            log.warning("CSV updater already running")
            return
        self._csv_task = asyncio.create_task(self._csv_update_loop())
        log.info(f"Started CSV updater (interval: {settings.CSV_UPDATE_INTERVAL_SECONDS}s)")

    def stop_csv_updater(self) -> None:
        """Stop the CSV updater background task."""
        if self._csv_task:
            self._csv_task.cancel()
            self._csv_task = None
            log.info("Stopped CSV updater")

    async def _csv_update_loop(self) -> None:
        """Background loop that generates CSV every 20 minutes."""
        while True:
            try:
                await asyncio.sleep(settings.CSV_UPDATE_INTERVAL_SECONDS)
                log.info("Generating CSV from CoinCap API...")
                await self._generate_csv()
            except asyncio.CancelledError:
                log.info("CSV update loop cancelled")
                break
            except Exception as exc:
                log.exception(f"CSV generation failed: {exc}")

    async def _generate_csv(self) -> None:
        """Fetch data from CoinCap API and generate CSV file."""
        try:
            data = await self._fetch_coincap()
            if not data:
                log.warning("No data from CoinCap API, skipping CSV generation")
                return

            # Ensure data directory exists
            CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Write CSV
            with CSV_OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["symbol", "name", "price_usd", "market_cap_usd", "rank", "source_updated_at"],
                )
                writer.writeheader()
                
                timestamp = datetime.now(timezone.utc).isoformat()
                for item in data:
                    writer.writerow({
                        "symbol": item.get("symbol", ""),
                        "name": item.get("name", ""),
                        "price_usd": item.get("priceUsd", ""),
                        "market_cap_usd": item.get("marketCapUsd", ""),
                        "rank": item.get("rank", ""),
                        "source_updated_at": timestamp,
                    })

            log.info(f"✓ Generated CSV with {len(data)} assets at {CSV_OUTPUT_PATH}")

        except Exception as exc:
            log.exception(f"Failed to generate CSV: {exc}")

    async def _fetch_coincap(self) -> List[Dict[str, Any]]:
        """Fetch top assets from CoinCap API (third source for CSV)."""
        url = "https://api.coincap.io/v2/assets"
        params = {"limit": TOP_ASSETS_COUNT}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            result = resp.json()

        return result.get("data", [])

    # =========================================================================
    # RESOLUTION - Called during ETL normalization
    # =========================================================================
    def resolve(
        self,
        source: str,
        symbol: str,
        name: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, Optional[str], Optional[str]]:
        """Resolve an asset to its canonical unified identifier.
        
        This method is called during ETL normalization to unify data
        from CoinGecko, CoinPaprika, and CSV into a single canonical entity.
        
        Args:
            source: Source name ('coingecko', 'coinpaprika', 'csv')
            symbol: Trading symbol (e.g., 'BTC')
            name: Asset name (e.g., 'Bitcoin')
            payload: Raw payload for extracting source IDs
            
        Returns:
            Tuple of (asset_uid, coingecko_id, coinpaprika_id)
        """
        # Extract source-specific IDs from payload
        coingecko_id = None
        coinpaprika_id = None

        if payload:
            if source == "coingecko":
                coingecko_id = payload.get("id")
            elif source == "coinpaprika":
                coinpaprika_id = payload.get("id")

        # Build cache key
        cache_key = f"{source}|{symbol.upper()}|{coingecko_id or ''}|{coinpaprika_id or ''}"
        if cache_key in self._cache:
            cached_uid = self._cache[cache_key]
            return cached_uid, coingecko_id, coinpaprika_id

        # Strategy 1: Direct lookup by source-specific ID
        asset_uid = self._lookup_by_source_id(coingecko_id, coinpaprika_id)
        if asset_uid:
            self._cache[cache_key] = asset_uid
            return asset_uid, coingecko_id, coinpaprika_id

        # Strategy 2: Symbol + Name matching
        asset_uid = self._lookup_by_symbol_name(symbol, name)
        if asset_uid:
            self._update_mapping_source_id(asset_uid, coingecko_id, coinpaprika_id)
            self._cache[cache_key] = asset_uid
            return asset_uid, coingecko_id, coinpaprika_id

        # Strategy 3: Generate canonical ID for new asset
        asset_uid = self._generate_canonical_id(coingecko_id, coinpaprika_id, symbol, name)
        self._cache[cache_key] = asset_uid
        self._create_mapping(asset_uid, symbol, name, coingecko_id, coinpaprika_id)

        return asset_uid, coingecko_id, coinpaprika_id

    def _lookup_by_source_id(
        self,
        coingecko_id: Optional[str],
        coinpaprika_id: Optional[str],
    ) -> Optional[str]:
        """Look up asset_uid by source-specific identifier."""
        if coingecko_id:
            mapping = self.db.query(AssetMapping).filter(
                AssetMapping.coingecko_id == coingecko_id
            ).first()
            if mapping:
                return mapping.asset_uid

        if coinpaprika_id:
            mapping = self.db.query(AssetMapping).filter(
                AssetMapping.coinpaprika_id == coinpaprika_id
            ).first()
            if mapping:
                return mapping.asset_uid

        return None

    def _lookup_by_symbol_name(self, symbol: str, name: str) -> Optional[str]:
        """Look up asset_uid by symbol and name."""
        normalized_symbol = symbol.upper().strip()
        normalized_name = self._normalize_name(name)

        mappings = self.db.query(AssetMapping).filter(
            AssetMapping.symbol == normalized_symbol
        ).all()

        if not mappings:
            return None

        if len(mappings) == 1:
            return mappings[0].asset_uid

        # Multiple matches - use name similarity
        for mapping in mappings:
            if self._normalize_name(mapping.name) == normalized_name:
                return mapping.asset_uid

        return mappings[0].asset_uid

    def _normalize_name(self, name: str) -> str:
        """Normalize asset name for comparison."""
        normalized = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        return ' '.join(normalized.split())

    def _generate_canonical_id(
        self,
        coingecko_id: Optional[str],
        coinpaprika_id: Optional[str],
        symbol: str,
        name: str,
    ) -> str:
        """Generate a canonical asset_uid for a new asset."""
        if coingecko_id:
            return coingecko_id.lower()
        if coinpaprika_id:
            return coinpaprika_id.lower()
        canonical = self._normalize_name(name).replace(' ', '-')
        return canonical if canonical else symbol.lower()

    def _update_mapping_source_id(
        self,
        asset_uid: str,
        coingecko_id: Optional[str],
        coinpaprika_id: Optional[str],
    ) -> None:
        """Update an existing mapping with newly discovered source IDs."""
        mapping = self.db.get(AssetMapping, asset_uid)
        if not mapping:
            return

        updated = False
        if coingecko_id and not mapping.coingecko_id:
            mapping.coingecko_id = coingecko_id
            updated = True
        if coinpaprika_id and not mapping.coinpaprika_id:
            mapping.coinpaprika_id = coinpaprika_id
            updated = True

        if updated:
            self.db.add(mapping)

    def _create_mapping(
        self,
        asset_uid: str,
        symbol: str,
        name: str,
        coingecko_id: Optional[str],
        coinpaprika_id: Optional[str],
    ) -> None:
        """Create a new asset mapping."""
        stmt = insert(AssetMapping).values(
            asset_uid=asset_uid,
            symbol=symbol.upper(),
            name=name,
            coingecko_id=coingecko_id,
            coinpaprika_id=coinpaprika_id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AssetMapping.asset_uid],
            set_={
                "coingecko_id": stmt.excluded.coingecko_id,
                "coinpaprika_id": stmt.excluded.coinpaprika_id,
            },
        )
        self.db.execute(stmt)
        log.info(f"Created asset mapping: {asset_uid} ({symbol})")


# Global instance holder for the service
_asset_service: Optional[AssetUnificationService] = None


async def init_asset_service(db: Session) -> AssetUnificationService:
    """Initialize the global asset unification service.
    
    Called at application startup to bootstrap mappings and start CSV updater.
    """
    global _asset_service
    _asset_service = await AssetUnificationService.create(db)
    _asset_service.start_csv_updater()
    return _asset_service


def get_asset_service() -> Optional[AssetUnificationService]:
    """Get the global asset unification service instance."""
    return _asset_service


def shutdown_asset_service() -> None:
    """Shutdown the asset service and stop background tasks."""
    global _asset_service
    if _asset_service:
        _asset_service.stop_csv_updater()
        _asset_service = None
