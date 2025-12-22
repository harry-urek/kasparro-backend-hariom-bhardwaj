"""Canonical table for API reads - idempotent with asset_uid = lower(symbol)"""

from sqlalchemy import DateTime, Numeric, String, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NormalizedCryptoAsset(Base):
    __tablename__ = "normalized_crypto_assets"

    # Stable cross-source ID (symbol-based)
    asset_uid: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    price_usd: Mapped[float] = mapped_column(Numeric, nullable=True)
    market_cap_usd: Mapped[float] = mapped_column(Numeric, nullable=True)

    rank: Mapped[int] = mapped_column(Integer, nullable=True)

    source: Mapped[str] = mapped_column(String, nullable=False)

    source_updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ingested_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
