"""Canonical table for API reads - unified entity with cross-source deterministic matching."""

from sqlalchemy import DateTime, Numeric, String, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NormalizedCryptoAsset(Base):
    """Unified cryptocurrency asset entity normalized across all sources.

    The asset_uid is a canonical identifier that deterministically maps
    the same asset across CoinGecko, CoinPaprika, and CSV sources.

    Cross-source matching is performed via:
    1. Source-specific ID lookup (coingecko_id, coinpaprika_id)
    2. Symbol + Name fuzzy matching
    3. Well-known asset mapping table
    """

    __tablename__ = "normalized_crypto_assets"

    # Canonical unified identifier (deterministic cross-source key)
    asset_uid: Mapped[str] = mapped_column(String(100), primary_key=True, index=True, comment="Canonical unified asset identifier from cross-source matching")

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    price_usd: Mapped[float] = mapped_column(Numeric, nullable=True)
    market_cap_usd: Mapped[float] = mapped_column(Numeric, nullable=True)

    rank: Mapped[int] = mapped_column(Integer, nullable=True)

    # Source tracking
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    # Source-specific identifiers for traceability
    coingecko_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True, comment="Original CoinGecko identifier")

    coinpaprika_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True, comment="Original CoinPaprika identifier")

    source_updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ingested_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
