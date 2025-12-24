"""End-to-end ETL service for all data sources (CoinGecko, CoinPaprika, CSV)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.api_source import CoinGeckoSource
from app.ingestion.csv_source import CSVSource
from app.ingestion.runner import IngestionRunner
from app.ingestion.third_source import CoinPaprikaSource
from app.models.checkpoints import ETLCheckpoint
from app.models.normalized import NormalizedCryptoAsset
from app.models.raw import RawCoinGecko, RawCoinPaprika, RawCSV
from app.models.runs import ETLRun

log = get_logger("etl_service")

SourceName = Literal["coingecko", "coinpaprika", "csv"]

# Default CSV path (can be overridden)
DEFAULT_CSV_PATH = Path(__file__).parent.parent.parent / "data" / "crypto_market.csv"


class ETLService:
    """Runs incremental, idempotent ETL for supported sources.
    
    Responsibilities:
    - Orchestrate data ingestion from multiple sources
    - Store raw payloads for auditability/replay
    - Normalize data into unified schema
    - Track ETL runs and checkpoints
    - Handle failures gracefully
    """

    def __init__(self, db: Session, csv_path: Optional[Path] = None):
        self.db = db
        self.csv_path = csv_path or DEFAULT_CSV_PATH

    async def run(self, source: SourceName) -> Dict[str, Any]:
        """Run ETL for a single source."""
        run = ETLRun(source_name=source, status="running", records_processed=0)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            last_checkpoint = self._load_checkpoint(source)
            log.info(f"Starting ETL for {source} | last_checkpoint={last_checkpoint}")

            # Fetch and filter records
            raw_records = await self._fetch_source(source, last_checkpoint)

            if not raw_records:
                log.info(f"No new records for {source}; checkpoint unchanged")
                run.status = "success"
                run.ended_at = datetime.now(timezone.utc)
                self.db.commit()
                return {"success": True, "records_processed": 0, "source": source}

            # Persist raw data
            self._persist_raw(source, raw_records)

            # Normalize and upsert
            normalized = self._normalize(raw_records, source)
            self._upsert_normalized(normalized)

            # Advance checkpoint
            self._advance_checkpoint(source, raw_records)

            # Mark run as success
            run.status = "success"
            run.records_processed = len(normalized)
            run.ended_at = datetime.now(timezone.utc)
            self.db.commit()

            log.info(f"ETL finished for {source} | processed={len(normalized)}")
            return {"success": True, "records_processed": len(normalized), "source": source}

        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            run.status = "failure"
            run.error_message = str(exc)
            run.ended_at = datetime.now(timezone.utc)
            self.db.add(run)
            self.db.commit()
            log.error(f"ETL failed for {source}: {exc}")
            raise

    async def run_all(self) -> Dict[str, Any]:
        """Run ETL for all configured sources."""
        sources: List[SourceName] = ["coingecko", "coinpaprika"]
        
        # Only include CSV if file exists
        if self.csv_path.exists():
            sources.append("csv")

        results: Dict[str, Any] = {}
        for source in sources:
            try:
                results[source] = await self.run(source)
            except Exception as exc:  # noqa: BLE001
                log.error(f"Failed to run ETL for {source}: {exc}")
                results[source] = {"success": False, "error": str(exc), "source": source}

        return results

    # -------------------------------------------------------------------------
    # Fetchers
    # -------------------------------------------------------------------------
    async def _fetch_source(
        self, source: SourceName, checkpoint: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Fetch data from source with incremental filtering."""
        if source == "coingecko":
            runner = IngestionRunner([CoinGeckoSource()])
        elif source == "coinpaprika":
            runner = IngestionRunner([CoinPaprikaSource()])
        elif source == "csv":
            runner = IngestionRunner([CSVSource(str(self.csv_path))])
        else:
            raise ValueError(f"Unsupported source: {source}")

        aggregated = await runner.run({source: checkpoint})
        return aggregated.get(source, [])

    # -------------------------------------------------------------------------
    # Raw Data Persistence
    # -------------------------------------------------------------------------
    def _persist_raw(self, source: SourceName, records: List[Dict[str, Any]]) -> None:
        """Persist raw records to source-specific table."""
        if source == "coingecko":
            self._persist_raw_coingecko(records)
        elif source == "coinpaprika":
            self._persist_raw_coinpaprika(records)
        elif source == "csv":
            self._persist_raw_csv(records)

    def _persist_raw_coingecko(self, records: List[Dict[str, Any]]) -> None:
        stmt = insert(RawCoinGecko).values([
            {
                "payload": rec["payload"],
                "source_updated_at": rec["source_updated_at"],
            }
            for rec in records
        ])
        self.db.execute(stmt)

    def _persist_raw_coinpaprika(self, records: List[Dict[str, Any]]) -> None:
        stmt = insert(RawCoinPaprika).values([
            {
                "payload": rec["payload"],
                "source_updated_at": rec["source_updated_at"],
            }
            for rec in records
        ])
        self.db.execute(stmt)

    def _persist_raw_csv(self, records: List[Dict[str, Any]]) -> None:
        stmt = insert(RawCSV).values([
            {
                "filename": str(self.csv_path.name),
                "payload": rec["payload"],
                "source_updated_at": rec["source_updated_at"],
            }
            for rec in records
        ])
        self.db.execute(stmt)

    # -------------------------------------------------------------------------
    # Normalization
    # -------------------------------------------------------------------------
    def _normalize(
        self, records: List[Dict[str, Any]], source: SourceName
    ) -> List[Dict[str, Any]]:
        """Normalize records into unified schema."""
        normalized: List[Dict[str, Any]] = []
        dedup: Dict[str, Dict[str, Any]] = {}

        for rec in records:
            symbol = (rec.get("symbol") or "").upper()
            if not symbol:
                log.warning(f"Skipping record without symbol: {rec.get('payload', {})}")
                continue

            # Create stable asset_uid from symbol
            asset_uid = symbol.lower()

            normalized_payload = {
                "asset_uid": asset_uid,
                "symbol": symbol,
                "name": rec.get("name") or symbol,
                "price_usd": self._safe_float(rec.get("price_usd")),
                "market_cap_usd": self._safe_float(rec.get("market_cap_usd")),
                "rank": self._safe_int(rec.get("rank")),
                "source": source,
                "source_updated_at": rec.get("source_updated_at"),
            }

            existing = dedup.get(asset_uid)
            incoming_ts = normalized_payload["source_updated_at"]
            if not existing:
                dedup[asset_uid] = normalized_payload
                continue

            existing_ts = existing.get("source_updated_at")
            if incoming_ts and (not existing_ts or incoming_ts > existing_ts):
                dedup[asset_uid] = normalized_payload

        normalized = list(dedup.values())
        if len(records) != len(normalized):
            log.debug(
                "Deduplicated normalized records for %s (input=%d output=%d)",
                source,
                len(records),
                len(normalized),
            )

        return normalized

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    # -------------------------------------------------------------------------
    # Normalized Data Upsert
    # -------------------------------------------------------------------------
    def _upsert_normalized(self, rows: List[Dict[str, Any]]) -> None:
        """Upsert normalized records (idempotent write)."""
        if not rows:
            return

        stmt = insert(NormalizedCryptoAsset).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[NormalizedCryptoAsset.asset_uid],
            set_={
                "symbol": stmt.excluded.symbol,
                "name": stmt.excluded.name,
                "price_usd": stmt.excluded.price_usd,
                "market_cap_usd": stmt.excluded.market_cap_usd,
                "rank": stmt.excluded.rank,
                "source": stmt.excluded.source,
                "source_updated_at": stmt.excluded.source_updated_at,
                "ingested_at": datetime.now(timezone.utc),
            },
        )
        self.db.execute(stmt)

    # -------------------------------------------------------------------------
    # Checkpoint Management
    # -------------------------------------------------------------------------
    def _advance_checkpoint(
        self, source: SourceName, records: List[Dict[str, Any]]
    ) -> None:
        """Update checkpoint to newest record timestamp."""
        if not records:
            return

        newest = max(rec["source_updated_at"] for rec in records)
        checkpoint = self.db.get(ETLCheckpoint, source)

        if not checkpoint:
            checkpoint = ETLCheckpoint(source_name=source, last_updated_at=newest)
        else:
            checkpoint.last_updated_at = newest

        self.db.add(checkpoint)

    def _load_checkpoint(self, source: SourceName) -> Optional[datetime]:
        """Load last checkpoint for a source."""
        checkpoint = self.db.get(ETLCheckpoint, source)
        return checkpoint.last_updated_at if checkpoint else None
