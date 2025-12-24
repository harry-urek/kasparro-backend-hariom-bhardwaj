"""Data Service - Query logic for data endpoints with proper separation of concerns."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.checkpoints import ETLCheckpoint
from app.models.normalized import NormalizedCryptoAsset
from app.models.raw import RawCoinGecko, RawCoinPaprika, RawCSV
from app.models.runs import ETLRun

log = get_logger("data_service")

RawSourceType = Literal["coingecko", "coinpaprika", "csv"]


class DataService:
    """Handles all data query operations - reads from DB only, no writes."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------------
    # Normalized Data Queries
    # -------------------------------------------------------------------------
    def get_normalized_data(
        self,
        source: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[NormalizedCryptoAsset]:
        """Get normalized crypto assets with optional filtering."""
        stmt = select(NormalizedCryptoAsset)

        if source:
            stmt = stmt.where(NormalizedCryptoAsset.source == source)
        if symbol:
            stmt = stmt.where(NormalizedCryptoAsset.symbol.ilike(f"%{symbol}%"))

        stmt = stmt.order_by(NormalizedCryptoAsset.rank.asc().nullslast())
        stmt = stmt.limit(limit).offset(offset)

        return list(self.db.execute(stmt).scalars().all())

    def get_normalized_by_uid(self, asset_uid: str) -> Optional[NormalizedCryptoAsset]:
        """Get a single normalized asset by its UID."""
        return self.db.get(NormalizedCryptoAsset, asset_uid)

    def get_normalized_count(self, source: Optional[str] = None) -> int:
        """Get count of normalized records."""
        stmt = select(func.count()).select_from(NormalizedCryptoAsset)
        if source:
            stmt = stmt.where(NormalizedCryptoAsset.source == source)
        return self.db.execute(stmt).scalar() or 0

    # -------------------------------------------------------------------------
    # Raw Data Queries
    # -------------------------------------------------------------------------
    def _get_raw_table(self, source: RawSourceType):
        """Get the raw table class for a given source."""
        mapping = {
            "coingecko": RawCoinGecko,
            "coinpaprika": RawCoinPaprika,
            "csv": RawCSV,
        }
        return mapping.get(source)

    def get_raw_data(
        self,
        source: RawSourceType,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Any]:
        """Get raw records for a specific source."""
        table = self._get_raw_table(source)
        if not table:
            return []

        stmt = select(table).order_by(table.ingested_at.desc()).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    def get_raw_by_id(self, source: RawSourceType, record_id: str) -> Optional[Any]:
        """Get a single raw record by ID."""
        import uuid

        table = self._get_raw_table(source)
        if not table:
            return None
        try:
            uid = uuid.UUID(record_id)
            return self.db.get(table, uid)
        except ValueError:
            return None

    def get_raw_count(self, source: RawSourceType) -> int:
        """Get count of raw records for a source."""
        table = self._get_raw_table(source)
        if not table:
            return 0
        stmt = select(func.count()).select_from(table)
        return self.db.execute(stmt).scalar() or 0

    # -------------------------------------------------------------------------
    # ETL Runs & Checkpoints Queries
    # -------------------------------------------------------------------------
    def get_etl_runs(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> List[ETLRun]:
        """Get recent ETL runs with optional filtering."""
        stmt = select(ETLRun)

        if source:
            stmt = stmt.where(ETLRun.source_name == source)
        if status:
            stmt = stmt.where(ETLRun.status == status)

        stmt = stmt.order_by(ETLRun.started_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_latest_etl_run(self, source: Optional[str] = None) -> Optional[ETLRun]:
        """Get the most recent ETL run."""
        stmt = select(ETLRun)
        if source:
            stmt = stmt.where(ETLRun.source_name == source)
        stmt = stmt.order_by(ETLRun.started_at.desc()).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_checkpoints(self) -> List[ETLCheckpoint]:
        """Get all checkpoints."""
        stmt = select(ETLCheckpoint).order_by(ETLCheckpoint.source_name)
        return list(self.db.execute(stmt).scalars().all())

    def get_checkpoint(self, source: str) -> Optional[ETLCheckpoint]:
        """Get checkpoint for a specific source."""
        return self.db.get(ETLCheckpoint, source)

    # -------------------------------------------------------------------------
    # Aggregation / Debug Info
    # -------------------------------------------------------------------------
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information about system state."""
        return {
            "checkpoints": self.get_checkpoints(),
            "etl_runs_count": self.db.execute(
                select(func.count()).select_from(ETLRun)
            ).scalar() or 0,
            "normalized_count": self.get_normalized_count(),
            "raw_coingecko_count": self.get_raw_count("coingecko"),
            "raw_coinpaprika_count": self.get_raw_count("coinpaprika"),
            "raw_csv_count": self.get_raw_count("csv"),
        }

    def get_sources_summary(self) -> List[Dict[str, Any]]:
        """Get summary of data per source."""
        sources = ["coingecko", "coinpaprika", "csv"]
        summary = []

        for source in sources:
            checkpoint = self.get_checkpoint(source)
            latest_run = self.get_latest_etl_run(source)
            normalized_count = self.get_normalized_count(source)
            raw_count = self.get_raw_count(source)  # type: ignore[arg-type]

            summary.append({
                "source": source,
                "normalized_records": normalized_count,
                "raw_records": raw_count,
                "last_checkpoint": checkpoint.last_updated_at if checkpoint else None,
                "last_run_status": latest_run.status if latest_run else None,
                "last_run_at": latest_run.started_at if latest_run else None,
            })

        return summary
