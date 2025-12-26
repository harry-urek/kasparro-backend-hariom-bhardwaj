"""Cross-source asset mapping for deterministic entity unification.

This module provides canonical asset identification across multiple data sources
(CoinGecko, CoinPaprika, CSV) by maintaining a mapping table that links
source-specific identifiers to a unified asset_uid.

At startup, the bootstrap service fetches top 100 assets from both APIs,
matches them by market cap rank and symbol, and populates this table dynamically.
The FALLBACK_ASSETS below are used only if the bootstrap fails.
"""

from sqlalchemy import DateTime, String, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AssetMapping(Base):
    """Canonical mapping table for cross-source asset identification.

    This table is populated at startup by the bootstrap service which:
    1. Fetches top 100 assets from CoinGecko and CoinPaprika
    2. Matches them by market cap rank and validates by symbol
    3. Creates unified mappings with both source IDs

    Example mappings (dynamically discovered):
        - asset_uid: "bitcoin"
          coingecko_id: "bitcoin"
          coinpaprika_id: "btc-bitcoin"
          symbol: "BTC"

        - asset_uid: "ethereum"
          coingecko_id: "ethereum"
          coinpaprika_id: "eth-ethereum"
          symbol: "ETH"
    """

    __tablename__ = "asset_mappings"

    # Canonical unified identifier (primary key)
    asset_uid: Mapped[str] = mapped_column(String(100), primary_key=True, index=True, comment="Canonical unified asset identifier")

    # Source-specific identifiers
    coingecko_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True, comment="CoinGecko API identifier (e.g., 'bitcoin')")

    coinpaprika_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True, comment="CoinPaprika API identifier (e.g., 'btc-bitcoin')")

    # Common identifiers for fallback matching
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="Trading symbol (e.g., 'BTC', 'ETH')")

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="Canonical asset name")

    # Metadata
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (Index('ix_asset_mapping_symbol_name', 'symbol', 'name'),)


# Fallback cryptocurrency mappings used only if bootstrap fails
# These are automatically overwritten when bootstrap succeeds
WELL_KNOWN_ASSETS = [
    {"asset_uid": "bitcoin", "coingecko_id": "bitcoin", "coinpaprika_id": "btc-bitcoin", "symbol": "BTC", "name": "Bitcoin"},
    {"asset_uid": "ethereum", "coingecko_id": "ethereum", "coinpaprika_id": "eth-ethereum", "symbol": "ETH", "name": "Ethereum"},
    {"asset_uid": "tether", "coingecko_id": "tether", "coinpaprika_id": "usdt-tether", "symbol": "USDT", "name": "Tether"},
    {"asset_uid": "binancecoin", "coingecko_id": "binancecoin", "coinpaprika_id": "bnb-binance-coin", "symbol": "BNB", "name": "BNB"},
    {"asset_uid": "solana", "coingecko_id": "solana", "coinpaprika_id": "sol-solana", "symbol": "SOL", "name": "Solana"},
    {"asset_uid": "ripple", "coingecko_id": "ripple", "coinpaprika_id": "xrp-xrp", "symbol": "XRP", "name": "XRP"},
    {"asset_uid": "usd-coin", "coingecko_id": "usd-coin", "coinpaprika_id": "usdc-usd-coin", "symbol": "USDC", "name": "USD Coin"},
    {"asset_uid": "cardano", "coingecko_id": "cardano", "coinpaprika_id": "ada-cardano", "symbol": "ADA", "name": "Cardano"},
    {"asset_uid": "dogecoin", "coingecko_id": "dogecoin", "coinpaprika_id": "doge-dogecoin", "symbol": "DOGE", "name": "Dogecoin"},
    {"asset_uid": "avalanche-2", "coingecko_id": "avalanche-2", "coinpaprika_id": "avax-avalanche", "symbol": "AVAX", "name": "Avalanche"},
    {"asset_uid": "tron", "coingecko_id": "tron", "coinpaprika_id": "trx-tron", "symbol": "TRX", "name": "TRON"},
    {"asset_uid": "polkadot", "coingecko_id": "polkadot", "coinpaprika_id": "dot-polkadot", "symbol": "DOT", "name": "Polkadot"},
    {"asset_uid": "chainlink", "coingecko_id": "chainlink", "coinpaprika_id": "link-chainlink", "symbol": "LINK", "name": "Chainlink"},
    {"asset_uid": "matic-network", "coingecko_id": "matic-network", "coinpaprika_id": "matic-polygon", "symbol": "MATIC", "name": "Polygon"},
    {"asset_uid": "litecoin", "coingecko_id": "litecoin", "coinpaprika_id": "ltc-litecoin", "symbol": "LTC", "name": "Litecoin"},
    {"asset_uid": "shiba-inu", "coingecko_id": "shiba-inu", "coinpaprika_id": "shib-shiba-inu", "symbol": "SHIB", "name": "Shiba Inu"},
    {"asset_uid": "wrapped-bitcoin", "coingecko_id": "wrapped-bitcoin", "coinpaprika_id": "wbtc-wrapped-bitcoin", "symbol": "WBTC", "name": "Wrapped Bitcoin"},
    {"asset_uid": "uniswap", "coingecko_id": "uniswap", "coinpaprika_id": "uni-uniswap", "symbol": "UNI", "name": "Uniswap"},
    {"asset_uid": "stellar", "coingecko_id": "stellar", "coinpaprika_id": "xlm-stellar", "symbol": "XLM", "name": "Stellar"},
    {"asset_uid": "cosmos", "coingecko_id": "cosmos", "coinpaprika_id": "atom-cosmos", "symbol": "ATOM", "name": "Cosmos"},
]
