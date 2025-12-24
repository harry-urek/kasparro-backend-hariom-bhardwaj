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
    run_id: str
    source_name: str
    status: str
    records_processed: int
    error_message: str | None = None
    started_at: datetime
    ended_at: datetime | None

    class Config:
        from_attributes = True


class RawRecordOut(BaseModel):
    id: str
    payload: dict
    source_updated_at: datetime
    ingested_at: datetime

    class Config:
        from_attributes = True


class RawDataResponse(BaseModel):
    request_id: str
    source: str
    total_count: int
    data: list[RawRecordOut]


class ETLTriggerRequest(BaseModel):
    source: str


class ETLTriggerResponse(BaseModel):
    success: bool
    source: str
    records_processed: int
    error: str | None = None


class CheckpointOut(BaseModel):
    source_name: str
    last_updated_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DebugResponse(BaseModel):
    checkpoints: list[CheckpointOut]
    etl_runs_count: int
    normalized_count: int
    raw_coingecko_count: int
    raw_coinpaprika_count: int
    raw_csv_count: int
