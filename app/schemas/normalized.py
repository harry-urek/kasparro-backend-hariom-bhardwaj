"""Unified normalized data model"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NormalizedData(BaseModel):
    """Unified normalized data schema"""

    id: str
    source: str
    data_type: str
    content: dict
    created_at: datetime
    updated_at: Optional[datetime] = None
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True
