"""API response models"""

from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime


class DataResponse(BaseModel):
    """Response model for data endpoint"""

    id: str
    source: str
    content: dict
    created_at: datetime
    updated_at: Optional[datetime] = None


class DataListResponse(BaseModel):
    """Response model for data list"""

    total: int
    items: List[DataResponse]
    limit: int
    offset: int


class StatsResponse(BaseModel):
    """Response model for statistics"""

    total_records: int
    by_source: dict
    last_updated: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Response model for health check"""

    status: str
    timestamp: datetime
    details: Optional[dict] = None


class ETLStatusResponse(BaseModel):
    """Response model for ETL status"""

    success: bool
    records_processed: int
    timestamp: datetime
    errors: Optional[List[str]] = None
