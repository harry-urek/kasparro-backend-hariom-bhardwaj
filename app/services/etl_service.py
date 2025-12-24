"""End-to-end ETL service for CoinGecko and CoinPaprika."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.api_source import CoinGeckoSource
from app.ingestion.runner import IngestionRunner
from app.ingestion.third_source import CoinPaprikaSource
from app.models.checkpoints import ETLCheckpoint
from app.models.normalized import NormalizedCryptoAsset
from app.models.raw import RawCoinGecko, RawCoinPaprika
from app.models.runs import ETLRun

log = get_logger("etl_service")

SourceName = Literal["coingecko", "coinpaprika"]


class ETLService:
    """Runs incremental, idempotent ETL for supported sources."""

    def __init__(self, db: Session):
        self.db = db

    async def run(self, source: SourceName) -> Dict[str, Any]:
        run = ETLRun(source_name=source, status="running", records_processed=0)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            last_checkpoint = self._load_checkpoint(source)
            log.info(f"Starting ETL for {source} | last_checkpoint={last_checkpoint}")

            raw_records = await self._fetch_source(source, last_checkpoint)
            fresh_records = raw_records

            if not fresh_records:
                log.info(f"No new records for {source}; checkpoint unchanged")
                run.status = "success"
                run.ended_at = datetime.now(timezone.utc)
                self.db.commit()
                return {"success": True, "records_processed": 0}

            self._persist_raw(source, fresh_records)
            normalized = self._normalize(fresh_records, source)
            self._upsert_normalized(normalized)
            self._advance_checkpoint(source, fresh_records)

            run.status = "success"
            run.records_processed = len(normalized)
            run.ended_at = datetime.now(timezone.utc)
            self.db.commit()

            log.info(f"ETL finished for {source} | processed={len(normalized)}")
            return {"success": True, "records_processed": len(normalized)}

        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            run.status = "failure"
            run.error_message = str(exc)
            run.ended_at = datetime.now(timezone.utc)
            self.db.add(run)
            self.db.commit()
            log.error(f"ETL failed for {source}: {exc}")
            raise

    # ---- Fetchers -----------------------------------------------------
    async def _fetch_source(self, source: SourceName, checkpoint: Optional[datetime]) -> List[Dict[str, Any]]:
        if source == "coingecko":
            runner = IngestionRunner([CoinGeckoSource()])
        elif source == "coinpaprika":
            runner = IngestionRunner([CoinPaprikaSource()])
        else:
            raise ValueError(f"Unsupported source: {source}")

        aggregated = await runner.run({source: checkpoint})
        return aggregated.get(source, [])

    # ---- Transform / Load --------------------------------------------
    def _persist_raw(self, source: SourceName, records: List[Dict[str, Any]]) -> None:
        table = RawCoinGecko if source == "coingecko" else RawCoinPaprika
        stmt = insert(table).values(
            [
                {
                    "payload": rec["payload"],
                    "source_updated_at": rec["source_updated_at"],
                }
                for rec in records
            ]
        )
        self.db.execute(stmt)

    def _normalize(self, records: List[Dict[str, Any]], source: SourceName) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for rec in records:
            symbol = (rec.get("symbol") or "").upper()
            if not symbol:
                continue
            asset_uid = symbol.lower()
            normalized.append(
                {
                    "asset_uid": asset_uid,
                    "symbol": symbol,
                    "name": rec.get("name") or symbol,
                    "price_usd": rec.get("price_usd"),
                    "market_cap_usd": rec.get("market_cap_usd"),
                    "rank": rec.get("rank"),
                    "source": source,
                    "source_updated_at": rec.get("source_updated_at"),
                }
            )
        return normalized

    def _upsert_normalized(self, rows: List[Dict[str, Any]]) -> None:
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

    def _advance_checkpoint(self, source: SourceName, records: List[Dict[str, Any]]) -> None:
        newest = max(rec["source_updated_at"] for rec in records)
        checkpoint = self.db.get(ETLCheckpoint, source)
        if not checkpoint:
            checkpoint = ETLCheckpoint(source_name=source, last_updated_at=newest)
        else:
            checkpoint.last_updated_at = newest
        self.db.add(checkpoint)

    def _load_checkpoint(self, source: SourceName) -> Optional[datetime]:
        checkpoint = self.db.get(ETLCheckpoint, source)
        return checkpoint.last_updated_at if checkpoint else None

    # ---- Helpers ------------------------------------------------------
