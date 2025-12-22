from datetime import datetime
from pydantic import BaseModel


class CryptoAssetOut(BaseModel):
    asset_uid: str
    symbol: str
    name: str
    price_usd: float | None
    market_cap_usd: float | None
    rank: int | None
    source: str
    source_updated_at: datetime

    class Config:
        from_attributes = True


class DataResponse(BaseModel):
    request_id: str
    api_latency_ms: int
    data: list[CryptoAssetOut]


class HealthResponse(BaseModel):
    database: str
    last_etl_status: str | None


class StatsResponse(BaseModel):
    source_name: str
    last_status: str
    records_processed: int
    started_at: datetime
    ended_at: datetime | None
